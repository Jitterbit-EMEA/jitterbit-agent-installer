"""Read-only host observations. Fixtures enter through Python injection, never CLI."""

import os
import platform as native
import re
import shlex
import shutil
from pathlib import Path


def normalize_arch(value):
    return {"amd64": "x86_64", "x86_64": "x86_64", "arm64": "aarch64", "aarch64": "aarch64"}.get(
        value.lower(), value.lower()
    )


def parse_os_release(text):
    result = {}
    for line in text.splitlines():
        if not line.strip() or line.startswith("#"):
            continue
        key, sep, raw = line.partition("=")
        if not sep or not re.fullmatch(r"[A-Z_]+", key) or key in result:
            raise ValueError("Invalid os-release")
        parts = shlex.split(raw, comments=True)
        if len(parts) != 1:
            raise ValueError("Invalid os-release")
        result[key] = parts[0]
    return result


def detect(os_release=Path("/etc/os-release"), system=None, machine=None):
    system = system or native.system()
    info = {}
    if system == "Linux":
        try:
            info = parse_os_release(Path(os_release).read_text())
        except (OSError, ValueError, UnicodeError):
            info = {}
    distro = info.get("ID", "unknown") if system == "Linux" else system.lower()
    # Recognizing a package family does not imply vendor support.
    manager, kind = {
        "ubuntu": ("apt", "deb"),
        "debian": ("apt", "deb"),
        "rhel": ("dnf", "rpm"),
        "amzn": ("dnf", "rpm"),
    }.get(distro, (None, None))
    memory = None
    if system == "Linux":
        try:
            match = re.search(r"^MemTotal:\s+(\d+)\s+kB$", Path("/proc/meminfo").read_text(), re.M)
            memory = int(match[1]) * 1024 if match else None
        except OSError:
            pass
    disk = shutil.disk_usage("/")
    return {
        "os": distro,
        "version": info.get("VERSION_ID"),
        "architecture": normalize_arch(machine or native.machine()),
        "system": system,
        "kernel": native.release(),
        "codename": info.get("VERSION_CODENAME"),
        "hostname": native.node() or "unknown",
        "packageManager": manager,
        "packageType": kind,
        "cpuCount": os.cpu_count(),
        "memoryBytes": memory,
        "diskTotalBytes": disk.total,
        "diskAvailableBytes": disk.free,
    }
