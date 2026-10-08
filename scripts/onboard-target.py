#!/usr/bin/env python3
"""Prepare JBPA and protected Harmony settings for one saved SSH target."""

import argparse
import getpass
import json
import os
import re
import shlex
import subprocess
import sys
import tempfile
from pathlib import Path, PurePosixPath
from urllib.parse import urlsplit

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from tools.handoff import customer_remote as remote  # noqa: E402


def settings(cloud_url, group_id, name_prefix):
    url = urlsplit(cloud_url)
    if (
        url.scheme != "https"
        or not url.hostname
        or url.username
        or url.password
        or url.query
        or url.fragment
        or any(char.isspace() for char in cloud_url)
        or group_id <= 0
        or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}", name_prefix)
    ):
        raise remote.RemoteError("HARMONY_SETTINGS_INVALID")
    return {
        "schemaVersion": 1,
        "harmony": {"cloudUrl": cloud_url, "agentGroupId": group_id},
        "agent": {"namePrefix": name_prefix},
        "registration": {
            "deregisterOnDrainstop": False,
            "retryCount": 10,
            "retryIntervalSeconds": 5,
        },
    }


def save_inventory(path, document):
    if path.is_symlink() or not path.parent.is_dir():
        raise remote.RemoteError("INVENTORY_PATH_UNSAFE")
    with tempfile.NamedTemporaryFile(mode="w", dir=path.parent, delete=False) as stream:
        staging = Path(stream.name)
        try:
            os.chmod(staging, 0o600)
            json.dump(document, stream, indent=2)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        except BaseException:
            staging.unlink(missing_ok=True)
            raise
    try:
        os.replace(staging, path)
    finally:
        staging.unlink(missing_ok=True)


def open_terminal(args):
    """Launch the non-secret command in a user-controlled macOS Terminal."""
    if sys.platform != "darwin":
        raise remote.RemoteError("SETUP_TERMINAL_LAUNCH_UNSUPPORTED")
    command = shlex.join(
        [
            sys.executable,
            str(Path(__file__).resolve()),
            "--inventory",
            str(args.inventory.expanduser().resolve()),
            "--target",
            args.target,
            "--cloud-url",
            args.cloud_url,
            "--group-id",
            str(args.group_id),
            "--name-prefix",
            args.name_prefix,
        ]
    )
    script = (
        "on run argv\n"
        'tell application "Terminal"\n'
        "activate\n"
        "do script (item 1 of argv)\n"
        "end tell\n"
        "end run"
    )
    result = subprocess.run(
        ["osascript", "-e", script, "exec " + command],
        capture_output=True,
        timeout=30,
        check=False,
    )
    if result.returncode:
        raise remote.RemoteError("SETUP_TERMINAL_LAUNCH_FAILED")


def provision(ssh, document):
    """Deliver secrets privately; never print command output or credential values."""
    stage = ssh.require(
        ["mktemp", "-d", "/var/tmp/jbpa-onboard-XXXXXX"], "SETUP_STAGE_FAILED"
    ).strip()
    if not re.fullmatch(r"/var/tmp/jbpa-onboard-[A-Za-z0-9]+", stage):
        raise remote.RemoteError("SETUP_STAGE_FAILED")
    guest_file = PurePosixPath(stage) / "credentials.json"
    try:
        with tempfile.TemporaryDirectory(prefix="jbpa-onboard-") as directory:
            local = Path(directory) / "credentials.json"
            descriptor = os.open(local, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            with os.fdopen(descriptor, "w") as stream:
                json.dump(document, stream)
            ssh.copy(local, guest_file)
        # versions prepares the framework runtime but never installs the PA.
        ssh.require(
            ["sudo", "-n", str(remote.REMOTE_RELEASE / "bin/jbpa-customer"), "versions"],
            "SETUP_RUNTIME_FAILED",
            timeout=1800,
        )
        root = str(remote.REMOTE_RELEASE)
        ssh.require(
            [
                "sudo",
                "-n",
                "env",
                f"PYTHONPATH={root}/lib:{root}/src",
                str(remote.REMOTE_RELEASE / ".venv/bin/python"),
                "-c",
                "import sys; from jbpa.customer import configure; "
                "configure(credentials_file=sys.argv[1])",
                str(guest_file),
            ],
            "SETUP_CREDENTIAL_IMPORT_FAILED",
        )
        ssh.require(
            ["sudo", "-n", "test", "-f", "/etc/jbpa/credentials.json"],
            "SETUP_CREDENTIALS_MISSING",
        )
    finally:
        ssh.run(["rm", "-f", str(guest_file)])
        ssh.run(["rmdir", stage])


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--inventory", type=Path, default=Path.home() / "jbpa-vms.json")
    parser.add_argument("--target", required=True)
    parser.add_argument("--cloud-url", required=True)
    parser.add_argument("--group-id", type=int, required=True)
    parser.add_argument("--name-prefix", default="qa-agent")
    parser.add_argument(
        "--open-terminal",
        action="store_true",
        help="Launch the hidden-token setup in macOS Terminal",
    )
    args = parser.parse_args(argv)
    try:
        inventory = args.inventory.expanduser().resolve()
        if args.inventory.expanduser().is_symlink():
            raise remote.RemoteError("INVENTORY_PATH_UNSAFE")
        target = remote.load_target(inventory, args.target)
        document = settings(args.cloud_url, args.group_id, args.name_prefix)
        if args.open_terminal:
            open_terminal(args)
            print(
                json.dumps(
                    {
                        "status": "TERMINAL_STARTED",
                        "operation": "SETUP",
                        "target": args.target,
                        "setupComplete": False,
                        "nextStep": "Enter token in the terminal's hidden prompt",
                    }
                )
            )
            return 0
        ssh = remote.SSH(target)
        remote.preflight_transport(ssh)
        # A repeated setup must not overwrite credentials or another operator's config.
        code, _ = ssh.run(["sudo", "-n", "test", "-e", "/etc/jbpa/agent.yaml"])
        if code == 0:
            raise remote.RemoteError("SETUP_ALREADY_CONFIGURED_USE_SAVED_TARGET")
        if code != 1:
            raise remote.RemoteError("SETUP_HOST_CHECK_FAILED")
        code, _ = ssh.run(["sudo", "-n", "test", "-e", "/etc/jbpa/credentials.json"])
        if code == 0:
            raise remote.RemoteError("SETUP_EXISTING_CREDENTIALS_INSPECT_FIRST")
        if code != 1:
            raise remote.RemoteError("SETUP_HOST_CHECK_FAILED")
        if not sys.stdin.isatty():
            raise remote.RemoteError("SETUP_REQUIRES_USER_TERMINAL")
        # Fail closed instead of falling back to an echoed getpass prompt.
        import warnings

        with warnings.catch_warnings():
            warnings.simplefilter("error", getpass.GetPassWarning)
            token = getpass.getpass("Harmony registration token (hidden): ")
        if not token.strip():
            raise remote.RemoteError("SETUP_TOKEN_REQUIRED")
        document["harmony"]["registrationToken"] = token
        try:
            remote.deliver_release(ssh, remote.ARCHIVE)
            provision(ssh, document)
        finally:
            document["harmony"].pop("registrationToken", None)
            token = None
        stored = json.loads(inventory.read_text())
        # Imported credentials now live on the VM; a source path would trigger reimport.
        stored["targets"][args.target].pop("credentialsFile", None)
        save_inventory(inventory, stored)
        print(
            json.dumps(
                {
                    "status": "SUCCESS",
                    "operation": "SETUP",
                    "target": args.target,
                    "inventory": str(inventory),
                    "release": remote.RELEASE,
                    "credentialsPathOnVm": "/etc/jbpa/credentials.json",
                    "paInstallPerformed": False,
                }
            )
        )
        return 0
    except (remote.RemoteError, OSError, ValueError, getpass.GetPassWarning) as exc:
        reason = str(exc) if isinstance(exc, remote.RemoteError) else "SETUP_FAILED_INSPECT_HOST"
        print(json.dumps({"status": "FAILED", "operation": "SETUP", "reason": reason}))
        return 1
    except (KeyboardInterrupt, EOFError):
        print(json.dumps({"status": "FAILED", "operation": "SETUP", "reason": "SETUP_CANCELLED"}))
        return 1


if __name__ == "__main__":
    sys.exit(main())
