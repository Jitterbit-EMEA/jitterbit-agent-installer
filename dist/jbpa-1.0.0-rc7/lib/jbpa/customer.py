"""Small customer-facing launcher over the governed JBPA commands.

This module uses only the Python standard library so it can prepare the release
venv before the framework's pinned dependencies are available.
"""

from __future__ import annotations

import argparse
import getpass
import json
import os
import platform
import re
import subprocess
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[2]
CONFIG = Path("/etc/jbpa/agent.yaml")
SECRETS = Path("/etc/jbpa/secrets")
RESULTS = Path("/var/lib/jbpa/results")
SECRET_NAMES = (
    "pa-registration-token",
    "pa-cloud-url",
    "pa-agent-group-id",
    "pa-agent-name-prefix",
    "pa-deregister-on-drainstop",
    "pa-retry-count",
    "pa-retry-interval-seconds",
)
FIXED = {
    "pa-deregister-on-drainstop": "false",
    "pa-retry-count": "10",
    "pa-retry-interval-seconds": "5",
}


class CustomerError(Exception):
    pass


def say(message=""):
    sys.stdout.write(message + "\n")
    sys.stdout.flush()


def require_root():
    if os.geteuid() != 0:
        raise CustomerError("Run this launcher with sudo, for example: sudo ./bin/jbpa-customer")


def require_qa_host():
    try:
        fields = dict(
            line.split("=", 1)
            for line in Path("/etc/os-release").read_text().splitlines()
            if "=" in line
        )
    except OSError as exc:
        raise CustomerError("Cannot identify this Linux host") from exc
    if (
        fields.get("ID", "").strip('"') != "ubuntu"
        or fields.get("VERSION_ID", "").strip('"') != "24.04"
        or platform.machine() != "x86_64"
    ):
        raise CustomerError("RC6 guided setup is qualified only for Ubuntu 24.04 amd64 QA")


def command(argv, *, capture=False, visible_stderr=False):
    try:
        return subprocess.run(
            argv,
            check=False,
            text=True,
            stdout=subprocess.PIPE if capture else None,
            stderr=None if visible_stderr or not capture else subprocess.PIPE,
        )
    except OSError as exc:
        raise CustomerError(f"Could not run {argv[0]}") from exc


def ensure_runtime():
    python = ROOT / ".venv/bin/python"
    ready = (
        python.is_file()
        and command([str(python), "-c", "import yaml,jsonschema"], capture=True).returncode == 0
    )
    if ready:
        return
    require_qa_host()
    say("Preparing the tool's Python environment. This can take a few minutes...")
    for argv in (
        ["apt-get", "update"],
        ["apt-get", "install", "-y", "python3-venv", "python3-pip"],
        ["python3", "-m", "venv", str(ROOT / ".venv")],
        [str(python), "-m", "pip", "install", "-r", str(ROOT / "requirements.txt")],
    ):
        if command(argv).returncode:
            raise CustomerError(f"Preparation failed while running {argv[0]}; see output above")


def private_directory(path):
    if path.is_symlink():
        raise CustomerError(f"Unsafe symbolic-link directory: {path}")
    path.mkdir(parents=True, exist_ok=True, mode=0o700)
    if path.stat().st_uid != 0:
        raise CustomerError(f"Directory must be root-owned: {path}")
    os.chmod(path, 0o700)


def write_private(path, value, *, replace=False):
    if path.is_symlink() or (path.exists() and not replace):
        raise CustomerError(f"Existing file was not changed: {path.name}")
    if path.exists() and (not path.is_file() or path.stat().st_uid != os.geteuid()):
        raise CustomerError(f"Unsafe existing file: {path.name}")
    staged = path.with_name(".jbpa-" + uuid.uuid4().hex)
    try:
        descriptor = os.open(staged, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
        with os.fdopen(descriptor, "w", encoding="utf-8") as output:
            output.write(value)
            output.flush()
            os.fsync(output.fileno())
        os.chmod(staged, 0o600)
        if replace:
            os.replace(staged, path)
        else:
            os.link(staged, path, follow_symlinks=False)
    finally:
        staged.unlink(missing_ok=True)


def prompt_details():
    if not sys.stdin.isatty():
        raise CustomerError(
            "A terminal is required to enter Harmony details; or stage private files"
        )
    say("Enter Harmony registration details. The token will not be displayed.")
    token = getpass.getpass("Registration credential (hidden): ")
    cloud = input("Harmony cloud URL (https://...): ").strip()
    group = input("Numeric agent group ID: ").strip()
    prefix = input("Agent name prefix: ").strip()
    url = urlsplit(cloud)
    if (
        not token
        or any(ord(char) < 32 or ord(char) == 127 for char in token)
        or url.scheme != "https"
        or not url.hostname
        or url.username
        or url.password
        or url.query
        or url.fragment
        or not group.isascii()
        or not group.isdecimal()
        or int(group) < 1
        or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}", prefix)
    ):
        raise CustomerError("The Harmony details are invalid; no credential files were changed")
    return {
        "pa-registration-token": token,
        "pa-cloud-url": cloud,
        "pa-agent-group-id": group,
        "pa-agent-name-prefix": prefix,
    }


def configure(*, replace=False):
    require_qa_host()
    private_directory(CONFIG.parent)
    private_directory(SECRETS)
    private_directory(RESULTS)
    if not CONFIG.exists():
        template = ROOT / "config/examples/local-file-qa.example.yaml"
        if not template.is_file():
            raise CustomerError("Local-file config template is missing from this release")
        write_private(CONFIG, template.read_text())
        say(f"Created {CONFIG} from the Ubuntu 24.04 template")
    elif CONFIG.is_symlink() or not CONFIG.is_file():
        raise CustomerError("Existing configuration path is unsafe")
    required = SECRET_NAMES[:4]
    existing = [name for name in required if (SECRETS / name).exists()]
    if existing and len(existing) != len(required) and not replace:
        raise CustomerError(
            "Some Harmony files already exist. Use setup --reconfigure to replace all four"
        )
    if replace or not existing:
        values = prompt_details()
        for name in required:
            write_private(SECRETS / name, values[name], replace=replace)
        say("Harmony details stored in root-only local files; values were not displayed")
    else:
        say("Using existing Harmony files; no token was displayed or changed")
    for name, value in FIXED.items():
        if not (SECRETS / name).exists():
            write_private(SECRETS / name, value)
    say(f"Configuration ready at {CONFIG}")


def jbpa(argv):
    ensure_runtime()
    result = command([str(ROOT / "bin/jbpa"), *argv], capture=True, visible_stderr=True)
    try:
        data = json.loads(result.stdout)
    except (ValueError, TypeError) as exc:
        raise CustomerError(
            "JBPA returned invalid JSON; inspect the local release and logs"
        ) from exc
    if result.returncode or data.get("status") != "SUCCESS":
        error = data.get("error") or {}
        name = error.get("name", "UNKNOWN_ERROR")
        raise CustomerError(f"JBPA stopped: {name}. Inspect the result file or run diagnostics")
    return data


def result_file(action):
    private_directory(RESULTS)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return RESULTS / f"customer-{action}-{stamp}-{uuid.uuid4().hex[:8]}.json"


def agent_installed():
    result = command(["dpkg-query", "-W", "-f=${Status}", "jitterbit-agent"], capture=True)
    return result.returncode == 0 and result.stdout.strip() == "install ok installed"


def show_versions():
    data = jbpa(["versions"])["details"]
    say("PA versions in the governed catalogue (listing is not approval):")
    for row in data["versions"]:
        say(
            f"  {row['version']:7} build {row['packageVersion']:11} "
            f"{row['approval']} / {row['qualification']}"
        )
    say("  latest  current vendor endpoint, inspected when selected")


def preflight(version=None):
    argv = ["validate", "--config", str(CONFIG), "--controlled-test"]
    if version:
        argv.extend(["--version", version])
    data = jbpa(argv)
    result = data["details"]["status"]
    say(f"Preflight: {result}")
    if result not in {"PASS", "PASS_WITH_WARNINGS"}:
        raise CustomerError("Preflight did not pass")
    if result == "PASS_WITH_WARNINGS":
        for name, check in data["details"]["preflight"]["checks"].items():
            if check["status"] == "WARN":
                say(f"  Warning: {name} ({check['reason']})")


def choose_version(provided=None):
    if provided:
        return provided
    show_versions()
    if not sys.stdin.isatty():
        return "latest"
    return input("PA version to use [latest]: ").strip() or "latest"


def install(version=None, *, non_interactive=False):
    if agent_installed():
        raise CustomerError("A PA is already installed; choose upgrade or status")
    if not CONFIG.is_file() or any(not (SECRETS / name).is_file() for name in SECRET_NAMES):
        if non_interactive:
            raise CustomerError("Run setup or stage the protected files before unattended install")
        configure()
    selected = choose_version(version)
    preflight(selected)
    path = result_file("install")
    say(f"Installing PA {selected} in controlled QA mode...")
    mode = "--non-interactive" if non_interactive else "--interactive"
    data = jbpa(
        [
            "install",
            mode,
            "--config",
            str(CONFIG),
            "--version",
            selected,
            "--controlled-test",
            "--result-file",
            str(path),
        ]
    )
    say(
        f"Installed PA {data['versions']['resolvedPA']}; "
        f"Harmony registered: {data['registration']['harmonyRegistered']}"
    )
    say(f"Private result: {path}")


def upgrade(version=None, *, yes=False):
    if not CONFIG.is_file():
        raise CustomerError("Run setup first")
    selected = choose_version(version)
    if not yes:
        if not sys.stdin.isatty() or input("Type UPGRADE to proceed: ").strip() != "UPGRADE":
            raise CustomerError("Upgrade cancelled")
    path = result_file("upgrade")
    say(f"Checking upgrade to {selected} in controlled QA mode...")
    data = jbpa(
        [
            "upgrade",
            "--config",
            str(CONFIG),
            "--version",
            selected,
            "--non-interactive",
            "--controlled-test",
            "--result-file",
            str(path),
        ]
    )
    say(f"Upgrade: {data['state']}; package changed: {data['details']['changed']}")
    say(f"Private result: {path}")


def status():
    data = jbpa(["diagnostics"])["details"]
    say(f"Installed PA: {data.get('installedVersion') or 'none'}")
    say(f"Package state: {data.get('packageState')}")
    say(f"Agent connection check: {data.get('connectionCheck')}")
    say(f"Core services healthy: {data.get('coreServicesHealthy')}")
    say("This is diagnostic output; confirm the agent in Harmony Management Console.")


def menu():
    while True:
        say("\nJBPA customer launcher — controlled QA")
        say("1. Set up the tool and enter Harmony details")
        say("2. List available PA versions")
        say("3. Install PA")
        say("4. Upgrade PA")
        say("5. Check agent status")
        say("6. Change Harmony details")
        say("0. Exit")
        choice = input("Choose 0–6: ").strip()
        if choice == "0":
            return
        try:
            if choice == "1":
                ensure_runtime()
                configure()
                if agent_installed():
                    status()
                else:
                    preflight()
            elif choice == "2":
                show_versions()
            elif choice == "3":
                install()
            elif choice == "4":
                upgrade()
            elif choice == "5":
                status()
            elif choice == "6":
                configure(replace=True)
                if agent_installed():
                    status()
                else:
                    preflight()
            else:
                say("Choose one of the displayed numbers")
        except CustomerError as exc:
            say(f"Stopped: {exc}")


def main(argv=None):
    parser = argparse.ArgumentParser(description="Guided customer launcher for JBPA RC6 QA")
    sub = parser.add_subparsers(dest="action")
    setup = sub.add_parser("setup", help="Prepare Python, YAML and protected Harmony files")
    setup.add_argument("--reconfigure", action="store_true", help="Replace Harmony files")
    sub.add_parser("versions", help="List governed PA versions")
    installing = sub.add_parser("install", help="Preflight and install PA")
    installing.add_argument("--version")
    installing.add_argument("--non-interactive", action="store_true")
    upgrading = sub.add_parser("upgrade", help="Upgrade an existing PA")
    upgrading.add_argument("--version")
    upgrading.add_argument("--yes", action="store_true", help="Skip UPGRADE confirmation")
    sub.add_parser("status", help="Show installed package and diagnostic state")
    args = parser.parse_args(argv)
    try:
        require_root()
        if args.action is None:
            if not sys.stdin.isatty():
                raise CustomerError("The menu needs a terminal; use a named command for automation")
            menu()
        elif args.action == "setup":
            ensure_runtime()
            configure(replace=args.reconfigure)
            if agent_installed():
                status()
            else:
                preflight()
        elif args.action == "versions":
            show_versions()
        elif args.action == "install":
            install(args.version, non_interactive=args.non_interactive)
        elif args.action == "upgrade":
            upgrade(args.version, yes=args.yes)
        elif args.action == "status":
            status()
    except (CustomerError, EOFError, KeyboardInterrupt) as exc:
        say(f"Stopped: {exc or 'cancelled'}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
