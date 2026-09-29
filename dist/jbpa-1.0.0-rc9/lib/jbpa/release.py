"""Controlled release staging and bounded archive verification."""

import argparse
import hashlib
import json
import re
import shutil
import tarfile
from pathlib import Path, PurePosixPath

from . import __version__
from .catalogue import load_catalogues
from .config import ROOT, load_config, load_yaml, validate_schema, validated_yaml
from .errors import FrameworkError

SCHEMA_VERSIONS = {
    "config": "1.0",
    "result": "1.0",
    "catalogue": "2.0",
    "runtimeContract": "1.0",
    "artifactManifest": "1.0",
}
REQUIRED_FILES = {
    "bin/jbpa",
    "lib/jbpa/__init__.py",
    "lib/jbpa/release_cli.py",
    "config/versions.yaml",
    "config/os-support.yaml",
    "config/schemas/rc-result.schema.json",
    "contracts/12.10.1.1.yaml",
    "contracts/12.9.2.2.yaml",
    "README.md",
    "requirements.txt",
    "release-manifest.json",
    "SHA256SUMS",
}
FORBIDDEN = {"credentials.txt", "register.json", "evidence", "__pycache__", ".venv", ".git"}


def digest(path):
    with Path(path).open("rb") as stream:
        hasher = hashlib.sha256()
        while block := stream.read(1024 * 1024):
            hasher.update(block)
        return hasher.hexdigest()


def validate_source():
    catalogue, _ = load_catalogues()
    if len(catalogue["versions"]) != catalogue["expected_pinned_count"] or set(
        catalogue["dynamic_sources"]
    ) != {"latest"}:
        raise FrameworkError("CONFIG_INVALID")
    for entry in catalogue["versions"].values():
        if (
            entry["qualification"]["overall"] == "TESTED_LIVE"
            and not (ROOT / "contracts" / (entry["package_version"] + ".yaml")).is_file()
        ):
            raise FrameworkError("CONFIG_INVALID")
    for path in (ROOT / "contracts").glob("*.yaml"):
        contract = validated_yaml(path, "runtime-contract")
        if path.stem != contract["package_version"]:
            raise FrameworkError("CONFIG_INVALID")
        for ref in contract["evidence_refs"]:
            if not (ROOT / ref).is_file():
                raise FrameworkError("CONFIG_INVALID")
    for path in (ROOT / "config/examples").glob("*.yaml"):
        if path.name == "azure-deployment.example.yaml":
            validated_yaml(path, "azure-deployment")
        else:
            load_config(path)
    validate_schema(manifest_for(catalogue), "release-manifest")
    return catalogue


def manifest_for(catalogue):
    tested = [
        entry["package_version"]
        for entry in catalogue["versions"].values()
        if entry["qualification"]["overall"] == "TESTED_LIVE"
    ]
    platforms = []
    for package in tested:
        platform = load_yaml(ROOT / "contracts" / (package + ".yaml"))["platform"]
        value = {
            "os": platform["os"],
            "version": platform["version"],
            "architecture": platform["architecture"],
        }
        if value not in platforms:
            platforms.append(value)
    return {
        "schemaVersion": "1.0",
        "jbpaVersion": __version__,
        "releaseStatus": "RELEASE_CANDIDATE_QA",
        "schemaVersions": SCHEMA_VERSIONS,
        "recommendedPA": catalogue["aliases"]["recommended"],
        "latestTestedPA": catalogue["aliases"]["latest-tested"],
        "latestAvailablePinnedPA": catalogue["aliases"]["latest-available-pinned"],
        "testedPackages": tested,
        "testedPlatforms": platforms,
        "runtimeScopes": {
            v: e["qualification"]
            for v, e in catalogue["versions"].items()
            if e["qualification"]["overall"] == "TESTED_LIVE"
        },
        "productionApproved": False,
        "pythonRequirement": ">=3.10",
        "files": {},
        "capabilities": [
            "INSTALL",
            "REINSTALL",
            "UPGRADE",
            "UNINSTALL",
            "HEALTH",
            "DIAGNOSTICS",
            "ENTERPRISE_CONFIGURE",
            "ARTIFACT_VERIFY",
            "VALIDATE",
            "VERSIONS",
            "CUSTOMER_LAUNCHER",
        ],
    }


def scan_bundle(root):
    for path in root.rglob("*"):
        relative = path.relative_to(root)
        if (
            path.is_symlink()
            or any(part in FORBIDDEN for part in relative.parts)
            or path.suffix in {".deb", ".pem", ".key", ".pyc", ".log"}
        ):
            raise FrameworkError("RELEASE_INVALID")
        if not path.is_file():
            continue
        raw = path.read_bytes()
        if len(raw) > 2 * 1024 * 1024:
            raise FrameworkError("RELEASE_INVALID")
        text = raw.decode("utf-8")
        if re.search(
            r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----\s*\n[A-Za-z0-9+/]{20}", text
        ):
            raise FrameworkError("RELEASE_INVALID")
        if re.search(r"https?://[^\s]+[?&](?:sig|token|password)=[^\s]+", text, re.I):
            raise FrameworkError("RELEASE_INVALID")


def build(output):
    catalogue = validate_source()
    output = Path(output).resolve()
    output.mkdir(parents=True, exist_ok=True)
    name = "jbpa-" + __version__
    stage = output / name
    if stage.exists():
        raise FrameworkError("RELEASE_INVALID")
    stage.mkdir(mode=0o755)
    shutil.copytree(
        ROOT / "src/jbpa", stage / "lib/jbpa", ignore=shutil.ignore_patterns("__pycache__", "*.pyc")
    )
    (stage / "bin").mkdir()
    shutil.copy2(ROOT / "bin/jbpa", stage / "bin/jbpa")
    shutil.copy2(ROOT / "bin/jbpa-customer", stage / "bin/jbpa-customer")
    shutil.copy2(ROOT / "bin/jbpa-install", stage / "bin/jbpa-install")
    (stage / "azure/custom-script").mkdir(parents=True)
    for filename in ("release-bootstrap.sh", "settings.example.json"):
        shutil.copy2(
            ROOT / "azure/custom-script" / filename, stage / "azure/custom-script" / filename
        )
    (stage / "config").mkdir()
    for file in ("versions.yaml", "os-support.yaml"):
        shutil.copy2(ROOT / "config" / file, stage / "config" / file)
    shutil.copytree(
        ROOT / "config/examples",
        stage / "config/examples",
        ignore=shutil.ignore_patterns("azure-deployment.example.yaml"),
    )
    shutil.copytree(
        ROOT / "config/schemas",
        stage / "config/schemas",
        ignore=shutil.ignore_patterns("azure-deployment.schema.json"),
    )
    shutil.copytree(
        ROOT / "config/schemas",
        stage / "schemas",
        ignore=shutil.ignore_patterns("azure-deployment.schema.json"),
    )
    shutil.copytree(ROOT / "contracts", stage / "contracts")
    for file in ("README.md", "requirements.txt"):
        shutil.copy2(ROOT / file, stage / file)
    (stage / "config/agent.example.yaml").write_bytes(
        (ROOT / "config/examples/azure-production.example.yaml").read_bytes()
    )
    product_docs = [
        "README.md",
        "customer-quickstart.md",
        "customer-start-here.md",
        "customer-install-runbook.md",
        "architecture.md",
        "configuration.md",
        "health-contract.md",
        "preflight-contract.md",
        "pre-provisioned-host-contract.md",
        "external-orchestrator-contract.md",
        "lifecycle-management.md",
        "security-review.md",
        "azure-ai-agent-contract.md",
        "azure-bootstrap.md",
        "release-notes.md",
        "production-readiness.md",
        "version-qualification-matrix.md",
        "errors.md",
    ]
    (stage / "docs").mkdir()
    for filename in product_docs:
        shutil.copy2(ROOT / "docs" / filename, stage / "docs" / filename)
    shutil.copytree(ROOT / "docs/runbooks", stage / "docs/runbooks")
    # Historical evidence belongs to the source repository, not the deployable bundle.
    for document in [stage / "README.md", *(stage / "docs").rglob("*.md")]:
        text = document.read_text().replace("src/jbpa/__init__.py", "lib/jbpa/__init__.py")

        def link(match, parent=document.parent):
            label, target = match.groups()
            if (
                "://" in target
                or target.startswith("#")
                or (parent / target.split("#")[0]).exists()
            ):
                return match.group(0)
            return label + " (source repository)"

        document.write_text(re.sub(r"\[([^\]]+)\]\(([^)]+)\)", link, text))
    scan_bundle(stage)
    manifest = manifest_for(catalogue)
    for path in sorted(stage.rglob("*")):
        if path.is_file():
            manifest["files"][path.relative_to(stage).as_posix()] = digest(path)
    validate_schema(manifest, "release-manifest")
    (stage / "release-manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n"
    )
    sums = {**manifest["files"], "release-manifest.json": digest(stage / "release-manifest.json")}
    (stage / "SHA256SUMS").write_text(
        "".join(f"{hash_value}  {filename}\n" for filename, hash_value in sorted(sums.items()))
    )
    archive = output / (name + ".tar.gz")

    def archive_metadata(member):
        member.uid = member.gid = 0
        member.uname = member.gname = "root"
        member.mode = (
            0o755
            if member.isdir() or member.name.endswith(("/bin/jbpa", "/bin/jbpa-customer"))
            else 0o644
        )
        return member

    with tarfile.open(archive, "w:gz") as tar:
        tar.add(stage, arcname=name, filter=archive_metadata)
    hash_value = digest(archive)
    archive.with_name(archive.name + ".sha256").write_text(f"{hash_value}  {archive.name}\n")
    verify(archive, hash_value)
    return {
        "archive": str(archive),
        "sha256": hash_value,
        "manifest": str(stage / "release-manifest.json"),
        "status": "VERIFIED",
    }


def verify(archive, expected=None):
    archive = Path(archive)
    expected = expected or archive.with_name(archive.name + ".sha256").read_text().split()[0]
    if not re.fullmatch(r"[a-f0-9]{64}", expected) or digest(archive) != expected:
        raise FrameworkError("RELEASE_INVALID")
    files = {}
    total = 0
    with tarfile.open(archive, "r:gz") as tar:
        members = tar.getmembers()
        if len(members) > 1000:
            raise FrameworkError("RELEASE_INVALID")
        prefix = None
        seen = set()
        for member in members:
            path = PurePosixPath(member.name)
            if (
                path.is_absolute()
                or ".." in path.parts
                or not path.parts
                or member.name in seen
                or not (member.isfile() or member.isdir())
            ):
                raise FrameworkError("RELEASE_INVALID")
            if member.uid != 0 or member.gid != 0 or member.mode & 0o022:
                raise FrameworkError("RELEASE_INVALID")
            if (
                member.name.endswith(("/bin/jbpa", "/bin/jbpa-customer"))
                and not member.mode & 0o111
            ):
                raise FrameworkError("RELEASE_INVALID")
            seen.add(member.name)
            prefix = prefix or path.parts[0]
            if path.parts[0] != prefix or any(p in FORBIDDEN for p in path.parts):
                raise FrameworkError("RELEASE_INVALID")
            if member.isfile():
                total += member.size
                if member.size > 2 * 1024 * 1024 or total > 32 * 1024 * 1024:
                    raise FrameworkError("RELEASE_INVALID")
                files[str(PurePosixPath(*path.parts[1:]))] = tar.extractfile(member).read()
    if not REQUIRED_FILES <= set(files):
        raise FrameworkError("RELEASE_INVALID")
    manifest = json.loads(files["release-manifest.json"])
    if (
        manifest["schemaVersion"] != "1.0"
        or manifest["jbpaVersion"]
        not in {"1.0.0-rc2", "1.0.0-rc3", "1.0.0-rc4", "1.0.0-rc5", "1.0.0-rc6", __version__}
        or manifest["schemaVersions"] != SCHEMA_VERSIONS
        or prefix != "jbpa-" + manifest["jbpaVersion"]
    ):
        raise FrameworkError("RELEASE_INVALID")
    if manifest["jbpaVersion"] == __version__ and not {
        "bin/jbpa-customer",
        "lib/jbpa/customer.py",
        "docs/customer-start-here.md",
    } <= set(files):
        raise FrameworkError("RELEASE_INVALID")
    if set(files) != set(manifest["files"]) | {"release-manifest.json", "SHA256SUMS"}:
        raise FrameworkError("RELEASE_INVALID")
    for filename, expected_hash in manifest["files"].items():
        if hashlib.sha256(files[filename]).hexdigest() != expected_hash:
            raise FrameworkError("RELEASE_INVALID")
    sums = {}
    for line in files["SHA256SUMS"].decode().splitlines():
        hash_value, filename = line.split("  ", 1)
        if filename in sums:
            raise FrameworkError("RELEASE_INVALID")
        sums[filename] = hash_value
    if set(sums) != set(files) - {"SHA256SUMS"} or any(
        hashlib.sha256(files[k]).hexdigest() != v for k, v in sums.items()
    ):
        raise FrameworkError("RELEASE_INVALID")
    if f'__version__ = "{manifest["jbpaVersion"]}"'.encode() not in files["lib/jbpa/__init__.py"]:
        raise FrameworkError("RELEASE_INVALID")
    import yaml
    from jsonschema import Draft202012Validator

    if not Draft202012Validator(
        json.loads(files["config/schemas/release-manifest.schema.json"])
    ).is_valid(manifest):
        raise FrameworkError("RELEASE_INVALID")
    catalogue = yaml.safe_load(files["config/versions.yaml"])
    schema = json.loads(files["config/schemas/versions.schema.json"])
    if (
        not Draft202012Validator(schema).is_valid(catalogue)
        or len(catalogue["versions"]) != catalogue["expected_pinned_count"]
        or set(catalogue["dynamic_sources"]) != {"latest"}
    ):
        raise FrameworkError("RELEASE_INVALID")
    if (
        catalogue["aliases"]["recommended"] != manifest["recommendedPA"]
        or catalogue["aliases"]["latest-tested"] != manifest["latestTestedPA"]
    ):
        raise FrameworkError("RELEASE_INVALID")
    for logical, entry in catalogue["versions"].items():
        if not entry["package_version"].startswith(logical + ".") or not entry["url"].endswith(
            "/" + entry["filename"]
        ):
            raise FrameworkError("RELEASE_INVALID")
    tested = [
        e["package_version"]
        for e in catalogue["versions"].values()
        if e["qualification"]["overall"] == "TESTED_LIVE"
    ]
    scopes = {
        v: e["qualification"]
        for v, e in catalogue["versions"].items()
        if e["qualification"]["overall"] == "TESTED_LIVE"
    }
    if (
        tested != manifest["testedPackages"]
        or scopes != manifest["runtimeScopes"]
        or catalogue["aliases"]["latest-available-pinned"] != manifest["latestAvailablePinnedPA"]
    ):
        raise FrameworkError("RELEASE_INVALID")
    for schema_name, field, expected_version in [
        ("agent", "schema_version", 1),
        ("rc-result", "schemaVersion", "1.0"),
        ("versions", "schema_version", 2),
        ("runtime-contract", "schema_version", "1.0"),
        ("artifact-manifest", "schema_version", "1.0"),
    ]:
        name = f"config/schemas/{schema_name}.schema.json"
        schema_data = json.loads(files[name])
        if (
            schema_data["properties"][field].get("const") != expected_version
            or files[name] != files["schemas/" + name.split("/")[-1]]
        ):
            raise FrameworkError("RELEASE_INVALID")
    contract_schema = json.loads(files["config/schemas/runtime-contract.schema.json"])
    for filename, raw in files.items():
        if filename.startswith("contracts/") and not Draft202012Validator(contract_schema).is_valid(
            yaml.safe_load(raw)
        ):
            raise FrameworkError("RELEASE_INVALID")
    return {
        "status": "VERIFIED",
        "sha256": expected,
        "files": len(files),
        "jbpaVersion": manifest["jbpaVersion"],
    }


def main():
    p = argparse.ArgumentParser()
    p.add_argument("action", choices=["validate", "build", "verify"])
    p.add_argument("path", nargs="?")
    p.add_argument("--sha256")
    args = p.parse_args()
    try:
        result = (
            {"status": "VALIDATED"}
            if args.action == "validate" and validate_source()
            else build(args.path or ROOT / "dist")
            if args.action == "build"
            else verify(args.path, args.sha256)
        )
        sys_output = json.dumps(result, indent=2) + "\n"
    except (FrameworkError, OSError, ValueError, KeyError, tarfile.TarError):
        sys_output = '{"status":"FAILED","error":"RELEASE_INVALID"}\n'
        import sys

        sys.stdout.write(sys_output)
        return 81
    import sys

    sys.stdout.write(sys_output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
