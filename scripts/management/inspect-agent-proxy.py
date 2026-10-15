#!/usr/bin/env python3
"""Read-only proxy diagnostics; emit only allowlisted non-credential settings."""

import configparser
import json
import re
import shlex
import subprocess
import urllib.parse
from datetime import datetime, timezone
from pathlib import Path

ALLOWED = {
    "http.proxyHost",
    "http.proxyPort",
    "http.nonProxyHosts",
    "https.proxyHost",
    "https.proxyPort",
    "socksProxyHost",
    "socksProxyPort",
    "socksNonProxyHosts",
    "java.net.useSystemProxies",
}


def origin(value):
    try:
        u = urllib.parse.urlsplit(value if "://" in value else "http://" + value)
        return {
            "host": u.hostname,
            "port": u.port,
            "credentialsPresent": bool(u.username or u.password),
        }
    except ValueError:
        return {"configured": bool(value), "parseable": False}


def properties(text):
    result = {}
    for line in text.splitlines():
        key, sep, value = line.partition("=")
        if sep and key in ALLOWED:
            result[key] = (
                origin(value) if key.endswith("proxyHost") or key == "socksProxyHost" else value
            )
    return result


def java_flags(tokens):
    return properties("\n".join(t[2:] for t in tokens if t.startswith("-D")))


def main():
    result = {
        "observedAtUtc": datetime.now(timezone.utc).isoformat(),
        "jvms": [],
        "configuration": {},
        "scope": "Allowlisted JVM proxy properties/flags and process proxy environment; raw arguments, other properties and proxy credential values withheld",
    }
    package = subprocess.run(
        ["dpkg-query", "-W", "-f=${Version}", "jitterbit-agent"],
        capture_output=True,
        text=True,
        timeout=10,
    )
    result["installedVersion"] = package.stdout if package.returncode == 0 else None
    cfg = configparser.ConfigParser(interpolation=None, strict=False)
    cfg.read("/opt/jitterbit/jitterbit.conf")
    for section in cfg.sections():
        if section.lower() not in ("proxy", "httpproxy"):
            continue
        rows = {}
        for key, value in cfg.items(section):
            if key.lower() in {
                "enabled",
                "enable",
                "useproxy",
                "host",
                "server",
                "proxyhost",
                "port",
                "proxyport",
                "nonproxyhosts",
                "proxyexceptions",
                "exceptions",
                "exclude",
                "nonproxyhost",
            }:
                rows[key] = (
                    origin(value)
                    if key.lower() in {"host", "server", "proxyhost"} and value
                    else value
                )
        result["configuration"][section] = rows
    for entry in Path("/proc").iterdir():
        if not entry.name.isdigit():
            continue
        try:
            exe = (entry / "exe").resolve()
            argv = (entry / "cmdline").read_bytes().decode(errors="replace").split("\0")
            if exe.name != "java" or not any(
                "jitterbit" in a.lower() or "catalina" in a.lower() for a in argv
            ):
                continue
            env = dict(
                v.split("=", 1)
                for v in (entry / "environ").read_bytes().decode(errors="replace").split("\0")
                if "=" in v
            )
            row = {
                "pid": int(entry.name),
                "role": "tomcat" if any("catalina" in a.lower() for a in argv) else "agent-java",
                "startupProxyProperties": java_flags(argv),
                "proxyEnvironment": {},
                "effectivePropertiesAvailable": False,
            }
            for name in [
                "http_proxy",
                "https_proxy",
                "all_proxy",
                "HTTP_PROXY",
                "HTTPS_PROXY",
                "ALL_PROXY",
                "NO_PROXY",
                "no_proxy",
            ]:
                if name in env:
                    row["proxyEnvironment"][name] = (
                        env[name] if name.lower() == "no_proxy" else origin(env[name])
                    )
            row["environmentJavaProxyFlags"] = {}
            for name in ["JAVA_TOOL_OPTIONS", "JDK_JAVA_OPTIONS", "_JAVA_OPTIONS", "JAVA_OPTS"]:
                if name in env:
                    try:
                        row["environmentJavaProxyFlags"][name] = java_flags(shlex.split(env[name]))
                    except ValueError:
                        row["environmentJavaProxyFlags"][name] = {"parseable": False}
            jcmd = exe.parent / "jcmd"
            if jcmd.is_file():
                # Attach as process owner, retaining root only for reading process metadata.
                uid = entry.stat().st_uid
                try:
                    p = subprocess.run(
                        [str(jcmd), entry.name, "VM.system_properties"],
                        capture_output=True,
                        text=True,
                        timeout=15,
                        user=uid,
                    )
                    row["effectivePropertiesAvailable"] = p.returncode == 0
                    row["effectiveProxyProperties"] = (
                        properties(p.stdout) if p.returncode == 0 else None
                    )
                except (OSError, subprocess.TimeoutExpired):
                    row["effectiveProxyProperties"] = None
            result["jvms"].append(row)
        except (OSError, ValueError):
            continue
    # Safe environment/launch files only; extract proxy property assignments, never raw lines.
    result["launchFileProxyProperties"] = {}
    for name in [
        "/etc/default/jitterbit",
        "/etc/sysconfig/jitterbit",
        "/opt/jitterbit/tomcat/bin/setenv.sh",
    ]:
        p = Path(name)
        if p.is_file():
            raw = p.read_text(errors="replace")
            matches = re.findall(
                r'-D([A-Za-z.]+)=(?:"([^"\n]*)"|\x27([^\x27\n]*)\x27|([^\s"\x27]+))', raw
            )
            extracted = properties(
                "\n".join(k + "=" + (a or b or c) for k, a, b, c in matches if k in ALLOWED)
            )
            result["launchFileProxyProperties"][name] = extracted
    print(json.dumps(result))


if __name__ == "__main__":
    main()
