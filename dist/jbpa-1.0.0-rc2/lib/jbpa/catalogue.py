"""Repository-controlled evidence, independently of runtime implementation."""

from .config import ROOT, validated_yaml
from .errors import FrameworkError


def load_catalogues():
    versions = validated_yaml(ROOT / "config/versions.yaml", "versions")
    support = validated_yaml(ROOT / "config/os-support.yaml", "os-support")
    if len(versions["versions"]) != versions["expected_pinned_count"]:
        raise FrameworkError("CONFIG_INVALID")
    packages = set()
    for logical, entry in versions["versions"].items():
        package = entry["package_version"]
        if package in packages or not package.startswith(logical + "."):
            raise FrameworkError("CONFIG_INVALID")
        packages.add(package)
        for artifact in entry["artifacts"]:
            if artifact["package_version"] != package or artifact["url"] != entry["url"]:
                raise FrameworkError("CONFIG_INVALID")
            if artifact["sha256"] and artifact["sha256"] != entry["integrity"]["sha256"]:
                raise FrameworkError("CONFIG_INVALID")
        if entry["filename"] != f"jitterbit-agent_{package}_amd64.deb":
            raise FrameworkError("CONFIG_INVALID")
        if not entry["url"].endswith("/" + entry["filename"]):
            raise FrameworkError("CONFIG_INVALID")
    for alias, target in versions["aliases"].items():
        if target not in versions["versions"]:
            raise FrameworkError("CONFIG_INVALID")
        if (
            alias in {"recommended", "latest-tested"}
            and versions["versions"][target]["qualification"]["overall"] != "TESTED_LIVE"
        ):
            raise FrameworkError("CONFIG_INVALID")
    return versions, support


def resolve(requested, versions):
    version = versions["aliases"].get(requested, requested)
    if version not in versions["versions"]:
        version = next(
            (v for v, e in versions["versions"].items() if e["package_version"] == requested), None
        )
    if version is None or version not in versions["versions"]:
        raise FrameworkError("VERSION_UNKNOWN")
    return version, versions["versions"][version]


def support_for(host, version, support):
    if host["os"] == "unknown" or host["version"] is None:
        return ("UNKNOWN" if host["system"] == "Linux" else "UNSUPPORTED"), None
    if not support["platforms"]:
        return "NOT_CONFIGURED", None
    for entry in support["platforms"]:
        if (
            host["system"] == "Linux"
            and entry["os_id"] == host["os"]
            and entry["os_version"] == host["version"]
            and entry["architecture"] == host["architecture"]
            and entry["package_kind"] == host["packageType"]
            and version in entry["agent_versions"]
        ):
            return "SUPPORTED", entry
    return "UNSUPPORTED", None


def readiness(config, version, entry, support):
    expected = config["agent"]["expected_os"]
    target = {
        "os": expected["id"],
        "version": expected["version"],
        "architecture": expected["architecture"],
        "system": "Linux",
        "packageType": config["agent"]["package_kind"],
    }
    supported, _ = support_for(target, version, support)
    matches = [
        a
        for a in entry["artifacts"]
        if (a["os_id"], a["os_version"], a["architecture"], a["package_kind"])
        == (target["os"], target["version"], target["architecture"], target["packageType"])
    ]
    if len(matches) > 1:
        raise FrameworkError("CONFIG_INVALID")
    artifact = matches[0] if matches else None
    return {
        "known": True,
        "supportedForTarget": supported == "SUPPORTED",
        "downloadConfigured": bool(artifact and artifact["url"] and artifact["package_version"]),
        "integrityConfigured": bool(artifact and artifact["sha256"]),
        "approved": entry["approval"] == "approved",
        "installable": bool(
            entry["approval"] == "approved"
            and artifact
            and artifact["url"]
            and artifact["sha256"]
            and artifact["adapter_profile"] == "native-deb-register-json"
        ),
    }
