"""Bounded metadata intake. Packages are inspected, never executed or extracted."""

import hashlib
import json
import os
import re
import subprocess
import tempfile
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from email.message import Message
from pathlib import Path
from urllib.parse import urlsplit

import yaml

from .catalogue import load_catalogues, resolve
from .config import ROOT, validate_schema
from .errors import FrameworkError
from .results import write_result

MAX_BYTES = 2 * 1024 * 1024 * 1024
MAX_SECONDS = 600


def checked_url(url):
    parsed = urlsplit(url)
    if (
        parsed.scheme != "https"
        or parsed.hostname not in {"download.jitterbit.com", "login.jitterbit.com"}
        or parsed.username
        or parsed.password
        or parsed.fragment
        or (parsed.query and parsed.query != "architecture=x64")
        or parsed.port not in {None, 443}
    ):
        raise FrameworkError("ARTIFACT_URL_REJECTED")
    return url


class SafeRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        checked_url(newurl)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def download(url, destination, opener=None, max_bytes=MAX_BYTES):
    checked_url(url)
    opener = opener or urllib.request.build_opener(SafeRedirect())
    start = time.monotonic()
    digest = hashlib.sha256()
    size = 0
    try:
        with opener.open(
            urllib.request.Request(url, headers={"User-Agent": "JBPA-artifact-intake"}), timeout=60
        ) as source:
            if source.status != 200:
                raise FrameworkError("DOWNLOAD_FAILED")
            final = checked_url(source.geturl())
            disposition = Message()
            disposition["Content-Disposition"] = source.headers.get("Content-Disposition", "")
            filename = disposition.get_filename()
            if filename and not re.fullmatch(r"jitterbit-agent_[0-9.]+_amd64\.deb", filename):
                raise FrameworkError("ARTIFACT_NOT_DEBIAN_PACKAGE")
            first = source.read(8)
            if first != b"!<arch>\n":
                raise FrameworkError("ARTIFACT_NOT_DEBIAN_PACKAGE")
            fd = os.open(destination, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
            with os.fdopen(fd, "wb") as output:
                block = first
                while block:
                    size += len(block)
                    if size > max_bytes or time.monotonic() - start > MAX_SECONDS:
                        raise FrameworkError("DOWNLOAD_FAILED")
                    output.write(block)
                    digest.update(block)
                    block = source.read(1024 * 1024)
                output.flush()
                os.fsync(output.fileno())
            return {
                "effective_url": final,
                "content_disposition_filename": filename,
                "content_type": source.headers.get("Content-Type", ""),
                "byte_size": size,
                "sha256": digest.hexdigest(),
            }
    except urllib.error.HTTPError as exc:
        raise FrameworkError(
            "ARTIFACT_AUTH_REQUIRED" if exc.code in {401, 403} else "DOWNLOAD_FAILED"
        ) from None
    except (OSError, urllib.error.URLError, TimeoutError):
        raise FrameworkError("DOWNLOAD_FAILED") from None


def package_fields(path):
    fields = {}
    for field in ("Package", "Version", "Architecture", "Depends"):
        try:
            result = subprocess.run(
                ["dpkg-deb", "--field", str(path), field],
                capture_output=True,
                text=True,
                timeout=30,
                check=False,
            )
        except FileNotFoundError:
            raise FrameworkError("ARTIFACT_INSPECTOR_UNAVAILABLE") from None
        except (OSError, subprocess.TimeoutExpired):
            raise FrameworkError("ARTIFACT_NOT_DEBIAN_PACKAGE") from None
        if result.returncode or len(result.stdout) > 65536:
            raise FrameworkError("ARTIFACT_NOT_DEBIAN_PACKAGE")
        fields[field] = result.stdout.strip()
    if (
        fields["Package"] != "jitterbit-agent"
        or fields["Architecture"] != "amd64"
        or not re.fullmatch(r"\d+(?:\.\d+){3}", fields["Version"])
    ):
        raise FrameworkError("ARTIFACT_METADATA_MISMATCH")
    return fields


def inspect(
    requested,
    directory,
    *,
    catalogue=None,
    downloader=download,
    inspector=package_fields,
    local_file=None,
):
    versions = catalogue or load_catalogues()[0]
    dynamic = requested == "latest"
    logical, entry = (None, None) if dynamic else resolve(requested, versions)
    url = versions["dynamic_sources"]["latest"]["url"] if dynamic else entry["url"]
    path = Path(directory) / "package.deb"
    if local_file is not None:
        if dynamic:
            raise FrameworkError("CONFIG_INVALID")
        source = Path(local_file)
        if source.is_symlink() or not source.is_file():
            raise FrameworkError("CONFIG_INVALID")
        hasher = hashlib.sha256()
        size = 0
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
        with os.fdopen(fd, "wb") as output, source.open("rb") as stream:
            while block := stream.read(1024 * 1024):
                size += len(block)
                if size > MAX_BYTES:
                    raise FrameworkError("DOWNLOAD_FAILED")
                hasher.update(block)
                output.write(block)
        with path.open("rb") as stream:
            if stream.read(8) != b"!<arch>\n":
                raise FrameworkError("ARTIFACT_NOT_DEBIAN_PACKAGE")
        transport = {
            "effective_url": None,
            "content_disposition_filename": None,
            "content_type": "",
            "byte_size": size,
            "sha256": hasher.hexdigest(),
        }
    else:
        transport = downloader(url, str(path))
    fields = inspector(path)
    package = fields["Version"]
    if not dynamic and package != entry["package_version"]:
        raise FrameworkError("ARTIFACT_METADATA_MISMATCH")
    if dynamic:
        logical = next(
            (v for v, e in versions["versions"].items() if e["package_version"] == package), None
        )
        entry = versions["versions"].get(logical)
    expected = entry["integrity"]["sha256"] if entry else None
    recorded = ROOT / "artifacts/metadata" / (package + ".yaml")
    if recorded.is_file():
        previous = yaml.safe_load(recorded.read_text())
        validate_schema(previous, "artifact-manifest")
        if previous["sha256"] != transport["sha256"]:
            raise FrameworkError("ARTIFACT_CHANGED")
    if expected and transport["sha256"] != expected:
        raise FrameworkError("ARTIFACT_CHANGED")
    filename = f"jitterbit-agent_{package}_amd64.deb"
    if transport.get("content_disposition_filename") not in {None, filename}:
        raise FrameworkError("ARTIFACT_METADATA_MISMATCH")
    manifest = {
        "schema_version": "1.0",
        "requested_version": requested,
        "logical_version": logical,
        "package_version": package,
        "filename": filename,
        "source_type": "DYNAMIC_MUTABLE" if dynamic else "PINNED",
        "request_url": url,
        **transport,
        "package_metadata": fields,
        "inspector": "dpkg-deb",
        "retrieval": "LOCAL_FILE" if local_file is not None else "HTTPS_DOWNLOAD",
        "integrity": "LOCALLY_CALCULATED",
        "artifact_status": "METADATA_VERIFIED",
        "production_approved": False,
        "runtime_qualification": entry["qualification"]["overall"]
        if entry
        else "AVAILABLE_UNQUALIFIED",
        "catalogue_match": entry is not None,
        "observed_at": datetime.now(timezone.utc).isoformat(),
    }
    validate_schema(manifest, "artifact-manifest")
    return manifest, path


def save_metadata(manifest, directory):
    """No automatic catalogue/hash/alias promotion. New observations are immutable."""
    directory = Path(directory)
    directory.mkdir(mode=0o700, parents=True, exist_ok=True)
    target = directory / (manifest["package_version"] + ".yaml")
    if target.exists():
        old = yaml.safe_load(target.read_text())
        if old["sha256"] != manifest["sha256"]:
            raise FrameworkError("ARTIFACT_CHANGED")
        return str(target)
    write_result(target, yaml.safe_dump(manifest, sort_keys=False))
    return str(target)


def latest_change(manifest, observation_file):
    """Optional protected local observation; change is informational for mutable latest."""
    target = Path(observation_file)
    changed = False
    if target.exists() or target.is_symlink():
        if (
            target.is_symlink()
            or target.stat().st_uid != os.getuid()
            or target.stat().st_mode & 0o077
            or target.stat().st_size > 4096
        ):
            raise FrameworkError("CONFIG_INVALID")
        old = json.loads(target.read_text())
        changed = (old["package_version"], old["sha256"]) != (
            manifest["package_version"],
            manifest["sha256"],
        )
        if (
            target.is_symlink()
            or target.stat().st_uid != os.getuid()
            or target.stat().st_mode & 0o077
        ):
            raise FrameworkError("CONFIG_INVALID")
        target.unlink()
    write_result(
        target,
        json.dumps({"package_version": manifest["package_version"], "sha256": manifest["sha256"]}),
    )
    return "LATEST_RESOLUTION_CHANGED" if changed else "LATEST_RESOLUTION_OBSERVED"


def intake_all(directory, catalogue=None, inspect_fn=inspect):
    catalogue = catalogue or load_catalogues()[0]
    results = []
    for version, entry in catalogue["versions"].items():
        if entry["qualification"]["overall"] != "AVAILABLE_UNQUALIFIED":
            continue
        try:
            with tempfile.TemporaryDirectory(prefix="jbpa-intake-") as temporary:
                manifest, _ = inspect_fn(version, temporary, catalogue=catalogue)
                save_metadata(manifest, directory)
                results.append(
                    {
                        "version": version,
                        "status": "METADATA_VERIFIED",
                        "sha256": manifest["sha256"],
                    }
                )
        except FrameworkError as exc:
            results.append({"version": version, "status": "FAILED", "error": exc.as_dict()})
    return results


def cache_artifact(manifest, source, directory):
    directory = Path(directory)
    directory.mkdir(parents=True, mode=0o700, exist_ok=True)
    for parent in (directory, *directory.parents):
        if parent.is_symlink():
            raise FrameworkError("CONFIG_INVALID")
    if directory.stat().st_uid != os.getuid() or directory.stat().st_mode & 0o022:
        raise FrameworkError("CONFIG_INVALID")
    digest = manifest["sha256"]
    package = manifest["package_version"]
    if not re.fullmatch(r"[a-f0-9]{64}", digest) or not re.fullmatch(r"\d+(?:\.\d+){3}", package):
        raise FrameworkError("CONFIG_INVALID")
    destination = directory / f"{package}-{digest}.deb"
    if destination.exists() or destination.is_symlink():
        if (
            destination.is_symlink()
            or not destination.is_file()
            or destination.stat().st_uid != os.getuid()
        ):
            raise FrameworkError("CONFIG_INVALID")
        with destination.open("rb") as stream:
            hasher = hashlib.sha256()
            while block := stream.read(1024 * 1024):
                hasher.update(block)
            actual = hasher.hexdigest()
        if actual != digest:
            raise FrameworkError("ARTIFACT_CHANGED")
        return destination
    fd = os.open(destination, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    try:
        with os.fdopen(fd, "wb") as output, Path(source).open("rb") as stream:
            digest_check = hashlib.sha256()
            while block := stream.read(1024 * 1024):
                output.write(block)
                digest_check.update(block)
            if digest_check.hexdigest() != digest:
                raise FrameworkError("ARTIFACT_CHANGED")
            output.flush()
            os.fsync(output.fileno())
    except Exception:
        destination.unlink(missing_ok=True)
        raise
    return destination
