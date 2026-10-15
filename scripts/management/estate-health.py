#!/usr/bin/env python3
"""Collect authorized inventory targets over SSH and assess estate health offline."""

import argparse
import base64
import gzip
import hashlib
import io
import json
import os
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT), str(ROOT / "src")]
from jbpa.estate_health import assess_estate, prometheus_metrics  # noqa: E402
from tools.handoff.customer_remote import SSH, load_target  # noqa: E402


def private_json(path, data):
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "w") as f:
        json.dump(data, f, indent=2, allow_nan=False)
        f.write("\n")


def collect(target, inventory, source, seconds, interval, hours, config):
    # load_target enforces pinned host keys; never export key/config/secret contents.
    ssh = SSH(load_target(inventory, target))
    config = dict(config)
    stage = None
    if config.get("localJvmProbeArtifact"):
        artifact = Path(config["localJvmProbeArtifact"])
        digest = config.get("localJvmProbeSha256")
        if not digest or hashlib.sha256(artifact.read_bytes()).hexdigest() != digest:
            raise RuntimeError("LOCAL_PROBE_ARTIFACT_DIGEST_MISMATCH")
        stage = ssh.require(
            ["mktemp", "-d", "/var/tmp/jbpa-noport-XXXXXX"], "PROBE_STAGE_FAILED"
        ).strip()
        if not stage.startswith("/var/tmp/jbpa-noport-") or stage.count("/") != 3:
            raise RuntimeError("INVALID_PROBE_STAGE")
        try:
            for local, name in [
                (artifact, "probe.jar"),
                (ROOT / "scripts/management/local-jvm-attach.py", "attach.py"),
            ]:
                ssh.copy(local, stage + "/" + name)
                if (
                    ssh.require(
                        ["sha256sum", stage + "/" + name], "PROBE_STAGE_INTEGRITY_FAILED"
                    ).split()[0]
                    != hashlib.sha256(local.read_bytes()).hexdigest()
                ):
                    raise RuntimeError("PROBE_STAGE_INTEGRITY_FAILED")
            setup = (
                "import os,pwd; from pathlib import Path; p=Path("
                + repr(stage)
                + ");u=pwd.getpwnam('jitterbit');os.chown(p,0,0);os.chmod(p,0o755);o=p/'output';o.mkdir(mode=0o700);os.chown(o,u.pw_uid,u.pw_gid);os.chown(p/'probe.jar',0,0);os.chmod(p/'probe.jar',0o444);os.chown(p/'attach.py',0,0);os.chmod(p/'attach.py',0o444)"
            )
            ssh.require(["sudo", "-n", "python3", "-c", setup], "PROBE_STAGE_PERMISSION_FAILED")
            config.update(
                {"localJvmProbeJar": stage + "/probe.jar", "localJvmHelper": stage + "/attach.py"}
            )
        except Exception:
            ssh.run(["sudo", "-n", "rm", "-rf", "--", stage], timeout=20)
            raise
    command = [
        "sudo",
        "-n",
        "/opt/jbpa/releases/jbpa-1.0.0-rc9/.venv/bin/python",
        "-c",
        source,
        "--seconds",
        str(seconds),
        "--interval",
        str(interval),
        "--window-hours",
        str(hours),
        "--compressed-output",
    ]
    for key, option in [
        ("apacheUrl", "--apache-url"),
        ("jmxUrl", "--jmx-url"),
        ("localJvmProbeJar", "--local-jvm-probe"),
        ("localJvmHelper", "--local-jvm-helper"),
        ("localJvmProbeSha256", "--local-jvm-probe-sha256"),
    ]:
        if config.get(key):
            command.extend([option, config[key]])
    try:
        code, raw = ssh.run(command, timeout=seconds + 240)
    finally:
        if stage:
            cleanup_code, _ = ssh.run(["sudo", "-n", "rm", "-rf", "--", stage], timeout=20)
            if cleanup_code:
                raise RuntimeError("PROBE_STAGE_CLEANUP_FAILED")
    if code:
        raise RuntimeError("NODE_CAPTURE_FAILED")
    with gzip.GzipFile(
        fileobj=io.BytesIO(base64.b64decode(raw.strip(), validate=True))
    ) as compressed:
        document = compressed.read(20 * 1024 * 1024 + 1)
    if len(document) > 20 * 1024 * 1024:
        raise RuntimeError("DECODED_NODE_CAPTURE_LIMIT")
    data = json.loads(document)
    if data.get("readOnly") is not True:
        raise RuntimeError("READ_ONLY_EVIDENCE_MISSING")
    return data


def main():
    p = argparse.ArgumentParser(description=__doc__)
    sub = p.add_subparsers(dest="action", required=True)
    run = sub.add_parser("collect")
    run.add_argument("--inventory", type=Path, required=True)
    run.add_argument(
        "--target",
        action="append",
        help="Repeat target; omitted means all selected inventory targets",
    )
    run.add_argument("--profile", type=Path, help="Non-secret roster/context/endpoints/policy JSON")
    run.add_argument("--seconds", type=int, default=30)
    run.add_argument("--interval", type=int, default=5)
    run.add_argument("--window-hours", type=int, default=24)
    run.add_argument("--concurrency", type=int, default=2)
    run.add_argument("--output", type=Path, required=True)
    replay = sub.add_parser("assess")
    replay.add_argument("--bundle", type=Path, required=True)
    replay.add_argument("--output", type=Path, required=True)
    args = p.parse_args()
    if args.action == "assess":
        b = json.loads((args.bundle / "bundle.json").read_text())
        result = assess_estate(
            b["captures"],
            b["expectedTargets"],
            b.get("policy"),
            b.get("contexts"),
            b.get("rosterVerifiedAgainstHarmony", False),
        )
        private_json(args.output, result)
        print(
            json.dumps(
                {
                    "status": "COMPLETE",
                    "assessmentStatus": result["status"],
                    "output": str(args.output),
                }
            )
        )
        return
    if (
        not 5 <= args.seconds <= 300
        or not 1 <= args.interval <= 30
        or not 1 <= args.window_hours <= 24
        or not 1 <= args.concurrency <= 4
    ):
        p.error("Invalid sampling, concurrency or window bounds")
    inventory = json.loads(args.inventory.read_text())
    targets = list(dict.fromkeys(args.target or inventory["targets"]))
    if not targets:
        p.error("No targets selected")
    if any(t not in inventory["targets"] for t in targets):
        p.error("Selected target absent from private inventory")
    profile = json.loads(args.profile.read_text()) if args.profile else {}
    # A supplied expected roster is a completeness input, not permission to access new hosts.
    expected = profile.get("expectedTargets", targets)
    if not isinstance(expected, list) or not all(isinstance(x, str) for x in expected):
        p.error("Invalid expected roster")
    if set(targets) - set(expected):
        p.error("Selected targets absent from expected roster")
    args.output.mkdir(parents=True, mode=0o700, exist_ok=False)
    source = (ROOT / "scripts/management/collect-estate-node.py").read_text()
    bundle = {
        "schemaVersion": 1,
        "expectedTargets": expected,
        "captures": {},
        "collectionErrors": {},
        "contexts": profile.get("targets", {}),
        "policy": profile.get("policy", {}),
        # Live Harmony discovery not implemented: never assert roster verification from a flag.
        "rosterVerifiedAgainstHarmony": False,
    }
    with ThreadPoolExecutor(max_workers=args.concurrency) as executor:
        futures = {
            executor.submit(
                collect,
                t,
                args.inventory,
                source,
                args.seconds,
                args.interval,
                args.window_hours,
                profile.get("targets", {}).get(t, {}),
            ): t
            for t in targets
        }
        for future in as_completed(futures):
            target = futures[future]
            try:
                bundle["captures"][target] = future.result()
            except Exception as exc:
                bundle["collectionErrors"][target] = type(exc).__name__
    result = assess_estate(
        bundle["captures"], expected, bundle["policy"], bundle["contexts"], False
    )
    private_json(args.output / "bundle.json", bundle)
    private_json(args.output / "assessment.json", result)
    fd = os.open(args.output / "health.prom", os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "w") as f:
        f.write(prometheus_metrics(result))
    lines = [
        "# Estate health assessment",
        "",
        "Status: " + result["status"],
        "Coverage: " + result["coverage"],
        "",
        "| Target | Status | Coverage | Findings |",
        "| --- | --- | --- | --- |",
    ]
    for n in result["nodes"]:
        lines.append(
            "| "
            + " | ".join(
                [
                    n["targetId"].replace("|", "\\|"),
                    n["status"],
                    n["coverage"],
                    str(len(n["findings"])),
                ]
            )
            + " |"
        )
    for n in result["nodes"]:
        lines.extend(["", "## " + n["targetId"], ""])
        for f in n["findings"]:
            lines.extend(
                [
                    "- **" + f["severity"] + " / " + f["code"] + "**: " + f["message"],
                    "  Next action: " + f["nextAction"],
                ]
            )
        lines.append("Coverage gaps: " + ", ".join(n["coverageGaps"]))
    lines.extend(["", "## Estate limits", "", *["- " + s for s in result["limitations"]], ""])
    fd = os.open(args.output / "assessment.md", os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "w") as f:
        f.write("\n".join(lines))
    print(
        json.dumps(
            {
                "status": "COMPLETE",
                "assessmentStatus": result["status"],
                "coverage": result["coverage"],
                "expectedTargets": len(expected),
                "collectedTargets": len(bundle["captures"]),
                "output": str(args.output),
            }
        )
    )


if __name__ == "__main__":
    main()
