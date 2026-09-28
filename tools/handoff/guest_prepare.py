"""External SSH caller's framework delivery step, executed on a prepared guest.

No Private Agent or infrastructure actions occur here. The RC3 archive stays immutable.
"""

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import tarfile
import tempfile
from pathlib import Path, PurePosixPath

RC3 = "1.0.0-rc3"
EXPECTED_SHA = "4b06e3715cb5faf3472354934fc12c04b54c7febe25d98f47bf1f038075ad90e"
MAX_ARCHIVE = 33554432
MAX_UNPACKED = 33554432


class DeliveryError(Exception):
    pass


def digest(path):
    value = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1048576), b""):
            value.update(block)
    return value.hexdigest()


def _check_parent(path):
    parent = path.parent
    while parent != parent.parent:
        info = parent.lstat()
        if parent.is_symlink() or not parent.is_dir() or info.st_uid != 0 or info.st_mode & 0o022:
            raise DeliveryError("UNSAFE_DESTINATION")
        parent = parent.parent


def _private_copy(source, destination):
    _check_parent(destination)
    fd = os.open(destination, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, "wb") as output, Path(source).open("rb") as incoming:
        shutil.copyfileobj(incoming, output)


def verify_installed(release, archive):
    _check_parent(release / "placeholder")
    if release.is_symlink() or archive.is_symlink():
        raise DeliveryError("UNSAFE_DESTINATION")
    if digest(archive) != EXPECTED_SHA:
        raise DeliveryError("JBPA_RELEASE_HASH_MISMATCH")
    with tarfile.open(archive, "r:gz") as tar:
        member = tar.extractfile(f"jbpa-{RC3}/release-manifest.json")
        if member is None:
            raise DeliveryError("RELEASE_MANIFEST_INVALID")
        trusted_manifest = member.read(1048577)
    if len(trusted_manifest) > 1048576:
        raise DeliveryError("RELEASE_MANIFEST_INVALID")
    if (release / "release-manifest.json").read_bytes() != trusted_manifest:
        raise DeliveryError("RELEASE_MANIFEST_INVALID")
    manifest = json.loads(trusted_manifest)
    if manifest["jbpaVersion"] != RC3 or "REINSTALL" not in manifest["capabilities"]:
        raise DeliveryError("RELEASE_MANIFEST_INVALID")
    for name, expected in manifest["files"].items():
        name_path = PurePosixPath(name)
        if name_path.is_absolute() or ".." in name_path.parts or not name_path.parts:
            raise DeliveryError("RELEASE_MANIFEST_INVALID")
        file = release / name
        if (
            file.is_symlink()
            or not file.is_file()
            or any(
                (release / PurePosixPath(*name_path.parts[:index])).is_symlink()
                for index in range(1, len(name_path.parts))
            )
            or digest(file) != expected
        ):
            raise DeliveryError("RELEASE_FILE_HASH_MISMATCH")
    return manifest


def prepare(archive, config_source, config_target, install_root, result_parent):
    if os.geteuid() != 0:
        raise DeliveryError("INSUFFICIENT_PRIVILEGE")
    archive = Path(archive)
    if archive.stat().st_size > MAX_ARCHIVE or digest(archive) != EXPECTED_SHA:
        raise DeliveryError("JBPA_RELEASE_HASH_MISMATCH")
    target_root = Path(install_root)
    if not target_root.is_absolute() or target_root.is_symlink():
        raise DeliveryError("UNSAFE_DESTINATION")
    target_root.mkdir(parents=True, mode=0o700, exist_ok=True)
    _check_parent(target_root / "placeholder")
    releases = target_root / "releases"
    releases.mkdir(parents=True, mode=0o700, exist_ok=True)
    _check_parent(releases / "placeholder")
    destination = releases / EXPECTED_SHA
    if destination.exists() or destination.is_symlink():
        raise DeliveryError("RELEASE_DESTINATION_EXISTS")
    stage = Path(tempfile.mkdtemp(prefix=".stage-", dir=releases))
    try:
        with tarfile.open(archive, "r:gz") as tar:
            members = tar.getmembers()
            if len(members) > 1000:
                raise DeliveryError("RELEASE_MANIFEST_INVALID")
            total = 0
            names = set()
            for member in members:
                path = PurePosixPath(member.name)
                if (
                    not path.parts
                    or path.is_absolute()
                    or ".." in path.parts
                    or path.parts[0] != "jbpa-" + RC3
                    or member.name in names
                    or not (member.isfile() or member.isdir())
                    or member.uid
                    or member.gid
                    or member.mode & 0o022
                    or member.size > 2097152
                ):
                    raise DeliveryError("RELEASE_MANIFEST_INVALID")
                names.add(member.name)
                total += member.size
                if total > MAX_UNPACKED:
                    raise DeliveryError("RELEASE_MANIFEST_INVALID")
            tar.extractall(stage, members=members)
        release = stage / ("jbpa-" + RC3)
        # Verify every packaged byte before using bundled requirements or code.
        verify_installed(release, archive)
        venv = release / ".venv"
        subprocess.run(
            ["python3", "-m", "venv", str(venv)],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=120,
            check=True,
        )
        subprocess.run(
            [
                str(venv / "bin/python"),
                "-m",
                "pip",
                "install",
                "--disable-pip-version-check",
                "-r",
                str(release / "requirements.txt"),
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=600,
            check=True,
        )
        environment = {**os.environ, "PYTHONPATH": str(release / "lib")}
        subprocess.run(
            [
                str(venv / "bin/python"),
                "-m",
                "jbpa.release",
                "verify",
                str(archive),
                "--sha256",
                EXPECTED_SHA,
            ],
            env=environment,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=60,
            check=True,
        )
        release.rename(destination)
    finally:
        if stage.exists():
            shutil.rmtree(stage)
    config_target = Path(config_target)
    if not config_target.is_absolute() or ".." in config_target.parts:
        raise DeliveryError("UNSAFE_DESTINATION")
    config_target.parent.mkdir(parents=True, mode=0o700, exist_ok=True)
    _private_copy(config_source, config_target)
    result_parent = Path(result_parent)
    if not result_parent.is_absolute() or ".." in result_parent.parts:
        raise DeliveryError("UNSAFE_DESTINATION")
    result_parent.mkdir(parents=True, mode=0o700, exist_ok=True)
    _check_parent(result_parent / "placeholder")
    persisted = Path("/var/lib/jbpa/releases")
    persisted.mkdir(parents=True, mode=0o700, exist_ok=True)
    _private_copy(archive, persisted / (EXPECTED_SHA + ".tar.gz"))
    return {
        "status": "VERIFIED",
        "jbpaVersion": RC3,
        "sha256": EXPECTED_SHA,
        "release": str(destination),
        "config": str(config_target),
    }


def verify_existing(install_root):
    if os.geteuid() != 0:
        raise DeliveryError("INSUFFICIENT_PRIVILEGE")
    release = Path(install_root) / "releases" / EXPECTED_SHA
    archive = Path("/var/lib/jbpa/releases") / (EXPECTED_SHA + ".tar.gz")
    verify_installed(release, archive)
    return {
        "status": "VERIFIED",
        "jbpaVersion": RC3,
        "sha256": EXPECTED_SHA,
        "release": str(release),
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("operation", choices=["prepare", "verify"])
    parser.add_argument("--archive")
    parser.add_argument("--config-source")
    parser.add_argument("--config-target")
    parser.add_argument("--result-parent")
    parser.add_argument("--install-root", default="/opt/jbpa")
    args = parser.parse_args()
    try:
        if args.operation == "prepare":
            if not all((args.archive, args.config_source, args.config_target, args.result_parent)):
                raise DeliveryError("INVALID_DELIVERY_INPUT")
            result = prepare(
                args.archive,
                args.config_source,
                args.config_target,
                args.install_root,
                args.result_parent,
            )
        else:
            result = verify_existing(args.install_root)
    except (DeliveryError, OSError, ValueError, tarfile.TarError, subprocess.SubprocessError):
        result = {"status": "FAILED", "reason": "RELEASE_DELIVERY_FAILED"}
    print(json.dumps(result, sort_keys=True))
    return 0 if result["status"] == "VERIFIED" else 1


if __name__ == "__main__":
    raise SystemExit(main())
