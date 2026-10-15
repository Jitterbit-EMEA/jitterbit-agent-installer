#!/usr/bin/env python3
"""Opt-in bounded HotSpot Linux attach, same UID/PID namespace. No TCP/UDP or GC commands."""

import argparse
import json
import os
import pwd
import re
import signal
import socket
import stat
import time
from pathlib import Path


def capture(pid, jar, output):
    jar = jar.resolve(strict=True)
    output = output.parent.resolve(strict=True) / output.name
    if (
        not str(jar).startswith("/var/tmp/jbpa-noport-")
        or not str(output).startswith("/var/tmp/jbpa-noport-")
        or not re.fullmatch(r"metrics-" + str(pid) + r"-[a-f0-9]{32}\.json", output.name)
    ):
        raise ValueError("CONTROLLED_DIAGNOSTIC_PATH_REQUIRED")
    if output.exists() or output.is_symlink():
        raise ValueError("OUTPUT_MUST_BE_NEW")
    user = pwd.getpwnam("jitterbit")
    root = Path("/proc") / str(pid)
    if root.stat().st_uid != user.pw_uid or (root / "comm").read_text().strip() != "java":
        raise ValueError("NOT_PA_JVM")
    status = dict(
        line.split(":", 1) for line in (root / "status").read_text().splitlines() if ":" in line
    )
    if int(status.get("NSpid", str(pid)).split()[-1]) != pid:
        raise ValueError("NAMESPACED_ATTACH_NOT_QUALIFIED")
    if not (int(status["SigCgt"].strip(), 16) & (1 << (signal.SIGQUIT - 1))):
        raise ValueError("JVM_QUIT_HANDLER_NOT_CONFIRMED")
    marker = Path("/tmp") / (".attach_pid" + str(pid))
    sock_path = Path("/tmp") / (".java_pid" + str(pid))
    # All subsequent protocol/file actions execute as the JVM's own account.
    if os.geteuid() == 0:
        os.setgroups([])
        os.setgid(user.pw_gid)
        os.setuid(user.pw_uid)
    if os.geteuid() != user.pw_uid:
        raise ValueError("SAME_UID_REQUIRED")
    created = False
    try:
        if not sock_path.exists():
            fd = os.open(marker, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
            os.close(fd)
            created = True
            os.kill(pid, signal.SIGQUIT)
            deadline = time.monotonic() + 5
            while not sock_path.exists() and time.monotonic() < deadline:
                time.sleep(0.1)
        info = sock_path.lstat()
        if info.st_uid != user.pw_uid or not stat.S_ISSOCK(info.st_mode) or info.st_mode & 0o077:
            raise ValueError("UNTRUSTED_ATTACH_SOCKET")
        request = "\0".join(
            ["1", "load", "instrument", "false", str(jar) + "=" + str(output), ""]
        ).encode()
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as sock:
            sock.settimeout(5)
            sock.connect(str(sock_path))
            sock.sendall(request)
            raw = b""
            while len(raw) < 16384:
                chunk = sock.recv(4096)
                if not chunk:
                    break
                raw += chunk
        status_code, _, body = raw.partition(b"\n")
        if status_code != b"0" or b"return code: 0" not in body:
            raise ValueError("DIAGNOSTIC_AGENT_REJECTED")
        fd = os.open(output, os.O_RDONLY | os.O_NOFOLLOW)
        with os.fdopen(fd) as f:
            data = json.loads(f.read(65537))
        if data["pid"] != pid:
            raise ValueError("PID_IDENTITY_MISMATCH")
        return data
    finally:
        if created:
            marker.unlink(missing_ok=True)
        output.unlink(missing_ok=True)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--pid", type=int, required=True)
    p.add_argument("--jar", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    a = p.parse_args()
    if not str(a.jar).startswith("/var/tmp/jbpa-noport-") or not str(a.output).startswith(
        "/var/tmp/jbpa-noport-"
    ):
        p.error("Only controlled diagnostic staging paths accepted")
    try:
        print(json.dumps({"status": "AVAILABLE", "data": capture(a.pid, a.jar, a.output)}))
    except Exception as exc:
        print(json.dumps({"status": "UNAVAILABLE", "error": type(exc).__name__}))
        raise SystemExit(1) from None


if __name__ == "__main__":
    main()
