"""Canonical bounded host readiness; no infrastructure or package mutation."""

import copy
import fcntl
import os
import shutil
import subprocess
from datetime import datetime, timezone
from urllib.parse import urlsplit

from .azure_identity import AzureKeyVaultSecretProvider, ManagedIdentity
from .catalogue import load_catalogues, resolve, support_for
from .errors import FrameworkError
from .local_secrets import LocalFileSecretProvider
from .platform import detect
from .uninstall import LocalUninstallBackend

GIB = 1024**3


def classify(snapshot):
    required = {
        "packageStatus",
        "rootPresent",
        "userPresent",
        "credentialsPresent",
        "registerPresent",
        "processCount",
        "postgresRuntimePresent",
        "postgresDataPresent",
        "commandPathsPresent",
        "startupPathsPresent",
    }
    if not isinstance(snapshot, dict) or not required <= set(snapshot):
        return "UNKNOWN_STATE"
    installed = (snapshot.get("packageStatus") or "").startswith("install ok installed|")
    if installed and snapshot.get("rootPresent") and snapshot.get("userPresent"):
        if snapshot.get("registerPresent"):
            return "PARTIAL_INSTALL"
        return (
            "AGENT_INSTALLED_REGISTERED"
            if snapshot.get("credentialsPresent")
            else "AGENT_INSTALLED_UNREGISTERED"
        )
    if snapshot.get("packageStatus") or any(
        snapshot.get(k)
        for k in (
            "rootPresent",
            "userPresent",
            "credentialsPresent",
            "registerPresent",
            "processCount",
            "postgresRuntimePresent",
            "postgresDataPresent",
            "commandPathsPresent",
            "startupPathsPresent",
        )
    ):
        return "PARTIAL_INSTALL"
    return "CLEAN_HOST"


class Probe:
    def command(self, argv, timeout=10):
        try:
            result = subprocess.run(
                argv, capture_output=True, text=True, timeout=timeout, check=False
            )
            return result.returncode, result.stdout.strip()
        except (OSError, subprocess.TimeoutExpired):
            return None, ""

    def privilege(self):
        if os.geteuid() == 0:
            return "ROOT"
        code, _ = self.command(["sudo", "-n", "true"], 5)
        return "SUDO_AVAILABLE" if code == 0 else "NONE"

    def package(self):
        if (
            not shutil.which("dpkg")
            or not shutil.which("apt-get")
            or not os.access("/var/lib/dpkg/status", os.R_OK)
        ):
            return "PACKAGE_MANAGER_INCONSISTENT"
        code, audit = self.command(["dpkg", "--audit"])
        if code != 0 or audit:
            return "PACKAGE_MANAGER_INCONSISTENT" if code is not None else "UNCONFIRMED"
        for name in (
            "/var/lib/dpkg/lock",
            "/var/lib/dpkg/lock-frontend",
            "/var/lib/apt/lists/lock",
            "/var/cache/apt/archives/lock",
        ):
            try:
                fd = os.open(name, os.O_RDWR | os.O_NOFOLLOW)
            except FileNotFoundError:
                continue
            except OSError:
                return "UNCONFIRMED"
            try:
                fcntl.lockf(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                fcntl.lockf(fd, fcntl.LOCK_UN)
            except BlockingIOError:
                return "PACKAGE_MANAGER_BUSY"
            except OSError:
                return "UNCONFIRMED"
            finally:
                os.close(fd)
        return "PACKAGE_MANAGER_READY"

    def repository(self):
        # Simulation uses existing metadata; no update, upgrade or lock-file deletion.
        code, _ = self.command(
            [
                "apt-get",
                "-s",
                "-o",
                "Debug::NoLocking=1",
                "install",
                "odbcinst",
                "unixodbc",
                "unzip",
            ],
            30,
        )
        return "PASS" if code == 0 else "UNCONFIRMED" if code is None else "FAIL"

    def disk(self, path):
        info = os.statvfs(path)
        return {
            "totalBytes": info.f_blocks * info.f_frsize,
            "freeBytes": info.f_bfree * info.f_frsize,
            "availableBytes": info.f_bavail * info.f_frsize,
        }

    def dns(self, host):
        # Isolated resolver process has a hard deadline, including libc resolver stalls.
        import sys

        code, _ = self.command(
            [sys.executable, "-c", "import socket,sys; socket.getaddrinfo(sys.argv[1],443)", host],
            5,
        )
        return "PASS" if code == 0 else "UNCONFIRMED" if code is None else "FAIL"

    def network(self, url):
        code, output = self.command(
            [
                "curl",
                "--silent",
                "--head",
                "--output",
                "/dev/null",
                "--write-out",
                "%{http_code}",
                "--connect-timeout",
                "5",
                "--max-time",
                "10",
                "--proto",
                "=https",
                url,
            ],
            12,
        )
        if code == 0 and output.isdigit() and int(output) > 0:
            return (
                "PASS",
                "TLS_VERIFIED_HTTP_REACHABLE",
            )  # 401/403 still proves unauthenticated reachability.
        return (
            ("UNCONFIRMED", "NETWORK_TIMEOUT")
            if code is None
            else (
                "FAIL",
                {6: "DNS_FAILED", 7: "TCP_FAILED", 60: "TLS_VERIFICATION_FAILED"}.get(
                    code, "NETWORK_PREREQUISITE_FAILED"
                ),
            )
        )

    def time(self):
        code, output = self.command(
            ["timedatectl", "show", "--property=NTPSynchronized", "--value"], 5
        )
        if code == 0 and output == "yes":
            return "PASS", "TIME_SYNC_READY"
        if code == 0 and output == "no":
            return "FAIL", "TIME_SYNC_FAILED"
        return "UNCONFIRMED", "TIME_SYNC_UNCONFIRMED"

    def secrets(self, config):
        provider = (
            LocalFileSecretProvider(config["secrets"]["directory"])
            if config["secrets"]["provider"] == "local-file"
            else AzureKeyVaultSecretProvider(
                config["secrets"]["vault_uri"],
                ManagedIdentity(config["secrets"]["managed_identity_client_id"]),
            )
        )
        try:
            from .bootstrap import _resolve_registration_fields

            if config["secrets"].get("registration_field_refs"):
                _resolve_registration_fields(config, provider)
            for key in ("token_secret_ref", "username_secret_ref", "password_secret_ref"):
                ref = config["harmony"]["registration"].get(key)
                if ref:
                    provider.resolve(ref)
            return "PASS", "SECRET_PROVIDER_READY"
        except FrameworkError as exc:
            return "FAIL", exc.spec.name
        finally:
            provider.clear()

    def state(self):
        backend = LocalUninstallBackend()
        snapshot = backend.snapshot()
        snapshot["servicesRunning"] = None
        if snapshot["rootPresent"]:
            from .restart_health import core_services
            from .uninstall import JITTERBIT

            status = backend.command([str(JITTERBIT), "status"], timeout=30)
            if core_services(status.stdout, status.returncode):
                snapshot["servicesRunning"] = True
            elif status.returncode == 0 and "0 out of 4 services are running" in status.stdout:
                snapshot["servicesRunning"] = False
        return snapshot


def run(
    config,
    *,
    profile="INSTALL",
    controlled_test=False,
    dry_run=False,
    host=None,
    probe=None,
    catalogue=None,
    support=None,
    package_bytes=None,
):
    if profile not in {"INSTALL", "REINSTALL", "HEALTH", "UNINSTALL"}:
        raise FrameworkError("CONFIG_INVALID")
    config = copy.deepcopy(config)
    host = host or detect()
    probe = probe or Probe()
    if catalogue is None or support is None:
        catalogue, support = load_catalogues()
    logical, entry = (
        resolve(config["agent"]["version"], catalogue)
        if config["agent"]["version"] != "latest"
        else (
            catalogue["aliases"]["recommended"],
            catalogue["versions"][catalogue["aliases"]["recommended"]],
        )
    )
    _, policy = support_for(host, logical, support)
    checks = {}
    stamp = datetime.now(timezone.utc).isoformat()

    def add(name, status, reason, blocking=True, evidence=None):
        checks[name] = {
            "status": status,
            "blocking": blocking,
            "reason": reason,
            "provider": "host-readiness/" + name,
            "timestamp": stamp,
            "evidence": evidence or {},
        }

    expected = config["agent"]["expected_os"]
    os_ok = (
        host["system"] == "Linux"
        and host["os"] == expected["id"]
        and host["version"] == expected["version"]
        and policy is not None
    )
    add(
        "os",
        "PASS" if os_ok else "FAIL",
        "SUPPORTED_OS" if os_ok else "UNSUPPORTED_OS",
        evidence={k: host.get(k) for k in ("os", "version", "codename", "kernel")},
    )
    arch_ok = host["architecture"] == "x86_64" and host["architecture"] == expected["architecture"]
    add(
        "architecture",
        "PASS" if arch_ok else "FAIL",
        "SUPPORTED_ARCHITECTURE" if arch_ok else "UNSUPPORTED_ARCHITECTURE",
        evidence={"architecture": host["architecture"]},
    )
    privilege = probe.privilege()
    add(
        "privilege",
        "PASS" if privilege == "ROOT" else "WARN" if privilege == "SUDO_AVAILABLE" else "FAIL",
        "PRIVILEGE_READY"
        if privilege == "ROOT"
        else "INVOKE_JBPA_WITH_SUDO"
        if privilege == "SUDO_AVAILABLE"
        else "INSUFFICIENT_PRIVILEGE",
        evidence={"effectiveUid": os.geteuid(), "capability": privilege},
    )
    # Sudo capability is observed, but JBPA does not self-escalate for live mutations.
    if privilege == "SUDO_AVAILABLE" and not dry_run:
        add("privilege", "FAIL", "INSUFFICIENT_PRIVILEGE", evidence={"capability": privilege})
    minimum = policy["minimum"] if policy else {}
    for name, field, requirement in [
        ("cpu", "cpuCount", "cpu_count"),
        ("memory", "memoryBytes", "memory_bytes"),
        ("diskCapacity", "diskTotalBytes", "disk_total_bytes"),
    ]:
        value, limit = host.get(field), minimum.get(requirement)
        status = (
            "UNCONFIRMED"
            if value is None or limit is None
            else "PASS"
            if value >= limit
            else "FAIL"
        )
        exception = (
            name == "cpu"
            and controlled_test
            and logical == "12.10"
            and host["os"] == "ubuntu"
            and host["version"] == "24.04"
            and value == 2
        )
        add(
            name,
            "WARN" if exception else status,
            "QA_EXCEPTION" if exception else "RESOURCE_POLICY",
            blocking=not exception,
            evidence={"observed": value, "minimum": limit},
        )
    manager = probe.package()
    add(
        "packageManager",
        "PASS"
        if manager == "PACKAGE_MANAGER_READY"
        else "UNCONFIRMED"
        if manager == "UNCONFIRMED"
        else "FAIL",
        manager,
    )
    repo = probe.repository() if manager == "PACKAGE_MANAGER_READY" else "UNCONFIRMED"
    add("repository", repo, "EXISTING_METADATA_DEPENDENCY_SIMULATION")
    # Observed 12.10 archive size plus a 5x extraction allowance and 1 GiB evidence margin;
    # a 4 GiB floor is an operational bound, not a vendor production sizing assertion.
    if package_bytes is None:
        from .config import ROOT, load_yaml

        metadata = ROOT / "artifacts/metadata" / (entry["package_version"] + ".yaml")
        package_bytes = load_yaml(metadata).get("byte_size") if metadata.exists() else None
    if package_bytes is None and entry["package_version"] == "12.10.1.1":
        package_bytes = 660897206  # Preserved metadata observation; operational allowance only.
    required = max(4 * GIB, (package_bytes or 0) * 5 + GIB)
    for path in ("/", "/opt", "/var"):
        try:
            disk = probe.disk(path)
            add(
                "space:" + path,
                "PASS" if disk["availableBytes"] >= required else "FAIL",
                "OPERATIONAL_FREE_SPACE_THRESHOLD",
                evidence={**disk, "requiredBytes": required, "packageBytes": package_bytes},
            )
        except OSError:
            add("space:" + path, "UNCONFIRMED", "FILESYSTEM_UNOBSERVED")
    try:
        state = probe.state()
    except OSError:
        state = {}
    host_state = classify(state)
    state_ok = host_state == "CLEAN_HOST" or (
        profile in {"REINSTALL", "HEALTH", "UNINSTALL"}
        and host_state in {"AGENT_INSTALLED_REGISTERED", "AGENT_INSTALLED_UNREGISTERED"}
    )
    add("existingAgent", "PASS" if state_ok else "FAIL", host_state, evidence=state)
    time_status, reason = probe.time()
    add("time", time_status, reason)
    local_blocked = any(
        c["blocking"] and c["status"] not in {"PASS", "NOT_APPLICABLE"} for c in checks.values()
    )
    if local_blocked and not dry_run:
        add("secretProvider", "UNCONFIRMED", "LOCAL_PREREQUISITE_FAILED")
    elif dry_run:
        add("secretProvider", "UNCONFIRMED", "NOT_RUN_DRY_RUN", False)
    elif config["secrets"]["provider"] in {"azure-key-vault", "local-file"}:
        secret_status, reason = probe.secrets(config)
        add("secretProvider", secret_status, reason)
    else:
        add("secretProvider", "UNCONFIRMED", "SECRET_PROVIDER_UNAVAILABLE")
    urls = [
        a.get("url")
        for a in entry.get("artifacts", [])
        if a.get("os_id") == host["os"] and a.get("os_version") == host["version"]
    ]
    if config["harmony"].get("cloud_url"):
        urls.append(config["harmony"]["cloud_url"])
    else:
        add("harmonyEndpoint", "UNCONFIRMED", "CONFIGURED_ENDPOINT_UNRESOLVED", not dry_run)
    if config["secrets"].get("vault_uri"):
        urls.append(config["secrets"]["vault_uri"])
    for index, url in enumerate(dict.fromkeys(u for u in urls if u)):
        parsed = urlsplit(url)
        name = "endpoint:" + str(index)
        if parsed.scheme != "https" or not parsed.hostname or parsed.username:
            add(name, "FAIL", "NETWORK_PREREQUISITE_FAILED")
            continue
        if dry_run or local_blocked:
            add(
                name,
                "UNCONFIRMED",
                "NOT_RUN_DRY_RUN" if dry_run else "LOCAL_PREREQUISITE_FAILED",
                not dry_run,
            )
            continue
        dns = probe.dns(parsed.hostname)
        add(
            name + ":dns",
            dns,
            "DNS_READY" if dns == "PASS" else "DNS_FAILED",
            evidence={"host": parsed.hostname},
        )
        network, reason = (
            probe.network(url) if dns == "PASS" else ("UNCONFIRMED", "DNS_PREREQUISITE_FAILED")
        )
        add(name + ":tls", network, reason, evidence={"host": parsed.hostname})
    add("agentServices", "UNCONFIRMED", "PRODUCT_CONNECTION_CHECK_AFTER_REGISTRATION", False)
    blocked = any(
        c["blocking"] and c["status"] not in {"PASS", "NOT_APPLICABLE"} for c in checks.values()
    )
    warning = any(c["status"] in {"WARN", "UNCONFIRMED"} for c in checks.values())
    return {
        "profile": profile,
        "status": "FAIL" if blocked else "PASS_WITH_WARNINGS" if warning else "PASS",
        "checks": checks,
        "hostState": host_state,
        "platform": host,
        "mutationPerformed": False,
    }
