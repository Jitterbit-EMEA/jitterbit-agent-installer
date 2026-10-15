"""One-shot, integrity-checked in-memory collectors over existing pinned SSH."""

import hashlib
import json
import math
import time
from pathlib import Path

from .customer_remote import MAX_OUTPUT, RemoteError

ROOT = Path(__file__).resolve().parents[2]
PYTHON = "/opt/jbpa/releases/jbpa-1.0.0-rc9/.venv/bin/python"
COLLECTORS = {
    "inspect_trandb": ROOT / "scripts/management/inspect-trandb.py",
    "trandb_reporting": ROOT / "scripts/management/trandb_reporting.py",
    "validate": ROOT / "scripts/management/validate-trandb-reporting.py",
}

# Executed with -B: no staging files, bytecode cache, persistent process or new listener.
BOOTSTRAP = r"""
import contextlib,hashlib,io,json,sys,time,types
start=time.monotonic()
raw=sys.stdin.buffer.read(262145)
if len(raw)>262144 or hashlib.sha256(raw).hexdigest()!=sys.argv[1]:
    raise SystemExit("COLLECTOR_INTEGRITY_FAILED")
bundle=json.loads(raw)
if set(bundle)!={"inspect_trandb","trandb_reporting","validate"}:
    raise SystemExit("COLLECTOR_MANIFEST_INVALID")
for name,source in bundle.items():
    if not isinstance(source,str):raise SystemExit("COLLECTOR_MANIFEST_INVALID")
    compile(source,"/__jbpa_stream__/"+name+".py","exec")
mode=sys.argv[2]
limit=int(sys.argv[3])
if mode not in ("profile","reporting","running","active","errors","definitions","backlog","identity") or not 1<=limit<=2000:
    raise SystemExit("INVALID_READ_SELECTION")
for name in ("inspect_trandb","trandb_reporting"):
    module=types.ModuleType(name)
    module.__file__="/__jbpa_stream__/"+name+".py"
    sys.modules[name]=module
    exec(compile(bundle[name],module.__file__,"exec"),module.__dict__)
output=io.StringIO()
with contextlib.redirect_stdout(output):
    if mode=="profile":
        sys.argv=["inspect_trandb.py","--profile"]
        sys.modules["inspect_trandb"].main()
    else:
        sys.argv=["validate.py","--mode",mode,"--limit",str(limit)]
        exec(compile(bundle["validate"],"/__jbpa_stream__/validate.py","exec"),{"__name__":"__main__","__file__":"/__jbpa_stream__/validate.py"})
result=json.loads(output.getvalue())
result["timings"]={"remoteElapsedMs":round((time.monotonic()-start)*1000,2),
    "queryElapsedMs":sum(q["elapsedMs"] for q in result["queries"])}
print(json.dumps(result,separators=(",",":"),default=str))
"""


def capture(ssh, mode, limit):
    # Validate locally as well as at the privilege boundary, before any SSH call.
    from scripts.management.trandb_reporting import MODES

    if mode not in (*MODES, "profile") or type(limit) is not int or not 1 <= limit <= 2000:
        raise RemoteError("INVALID_READ_SELECTION")
    start = time.monotonic()
    payload = json.dumps({k: p.read_text() for k, p in COLLECTORS.items()}, separators=(",", ":"))
    if len(payload.encode()) > 262144:
        raise RemoteError("COLLECTOR_BUNDLE_TOO_LARGE")
    digest = hashlib.sha256(payload.encode()).hexdigest()
    prepared = time.monotonic()
    code, raw = ssh.run(
        ["sudo", "-n", PYTHON, "-B", "-c", BOOTSTRAP, digest, mode, str(limit)],
        timeout=300,
        input_text=payload,
    )
    finished = time.monotonic()
    if code:
        raise RemoteError("ASSESSMENT_FAILED_PRIVATE_OUTPUT_WITHHELD")
    if len(raw.encode()) > MAX_OUTPUT:
        raise RemoteError("REMOTE_OUTPUT_TOO_LARGE")
    try:
        data = json.loads(raw)
        if (
            not isinstance(data, dict)
            or data.get("readOnlyEnforced") is not True
            or not isinstance(data.get("queries"), list)
        ):
            raise ValueError()
        remote = float(data["timings"]["remoteElapsedMs"])
        if not math.isfinite(remote) or remote < 0:
            raise ValueError()
    except (ValueError, KeyError, TypeError):
        raise RemoteError("READ_ONLY_EVIDENCE_MISSING") from None
    roundtrip = (finished - prepared) * 1000
    data["timings"].update(
        clientPreparationMs=round((prepared - start) * 1000, 2),
        sshRoundTripMs=round(roundtrip, 2),
        sshAndStartupOverheadMs=round(max(0, roundtrip - remote), 2),
        totalMs=round((finished - start) * 1000, 2),
        sshInvocations=1,
        collectorBytes=len(payload.encode()),
        responseBytes=len(raw.encode()),
    )
    return data
