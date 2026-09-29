#!/usr/bin/env bash
set -Eeuo pipefail
umask 077
if (( $# < 4 || $# > 7 )); then
  printf '%s\n' 'Usage: release-bootstrap.sh HTTPS_URL_OR_ARCHIVE SHA256 CONFIG RESULT_FILE [INSTALL_ROOT] [production|controlled-test] [false|true]' >&2
  exit 2
fi
source_bundle="$1"
expected_hash="$2"
config="$3"
result_file="$4"
install_root="${5:-/opt/jbpa}"
mode="${6:-production}"
allow_unqualified="${7:-false}"
if [[ "$allow_unqualified" != false && "$allow_unqualified" != true ]]; then
  printf '%s\n' '{"status":"FAILED","category":"CONFIGURATION_ERROR","error":"INVALID_QUALIFICATION_OVERRIDE"}'
  exit 2
fi
if [[ "$allow_unqualified" == true && "$mode" != controlled-test ]]; then
  printf '%s\n' '{"status":"FAILED","category":"CONFIGURATION_ERROR","error":"UNQUALIFIED_REQUIRES_CONTROLLED_TEST"}'
  exit 2
fi
if [[ ! "$expected_hash" =~ ^[a-f0-9]{64}$ || ! -f "$config" || "$mode" != production && "$mode" != controlled-test ]]; then
  printf '%s\n' '{"status":"FAILED","category":"CONFIGURATION_ERROR","error":"INVALID_BOOTSTRAP_INPUT"}'
  exit 2
fi
failure() {
  status="$1"
  trap - ERR
  python3 - "$status" "$result_file" <<'PYFAIL'
import json
import os
import pathlib
import sys
import uuid
code = int(sys.argv[1])
error = {"name": "RELEASE_BOOTSTRAP_FAILED", "exitCode": code, "message": "Framework bootstrap failed before JBPA invocation", "phase": "RELEASE", "retryable": False, "category": "RELEASE_ERROR"}
result = {"schemaVersion": "1.0", "runId": "jbpa-bootstrap-" + uuid.uuid4().hex, "operation": "RELEASE_BOOTSTRAP", "status": "FAILED", "state": "FAILED", "versions": {"jbpa": None, "requestedPA": None, "resolvedPA": None}, "artifact": {}, "platform": {}, "registration": {}, "health": {}, "enterpriseConfiguration": {}, "error": error, "category": "RELEASE_ERROR", "details": {}}
text = json.dumps(result) + "\n"
path = pathlib.Path(sys.argv[2])
try:
    parent = path.parent
    metadata = parent.stat()
    if parent.is_symlink() or metadata.st_uid != os.getuid() or metadata.st_mode & 0o022:
        raise OSError()
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, 'w') as stream:
        stream.write(text)
except OSError:
    pass
sys.stdout.write(text)
PYFAIL
  exit "$status"
}
trap 'failure "$?"' ERR
install -d -m 0700 "$install_root/releases" "$(dirname -- "$result_file")"
stage="$(mktemp -d "$install_root/releases/.stage.XXXXXXXX")"
trap 'rm -rf -- "$stage"' EXIT
archive="$stage/release.tar.gz"
if [[ "$source_bundle" == https://* ]]; then
  python3 - "$source_bundle" <<'PY'
import sys
from urllib.parse import urlsplit
value = urlsplit(sys.argv[1])
if not value.hostname or value.username or value.password or value.query or value.fragment:
    raise SystemExit(2)
PY
  curl --fail --silent --show-error --proto '=https' --proto-redir '=https' --location --max-redirs 3 --max-time 300 --max-filesize 33554432 --output "$archive" "$source_bundle"
else
  cp -- "$source_bundle" "$archive"
fi
python3 - "$archive" "$expected_hash" "$stage" <<'PY'
import hashlib
import pathlib
import sys
import tarfile
archive, expected, stage = sys.argv[1:]
with open(archive, 'rb') as stream:
    digest = hashlib.sha256()
    for block in iter(lambda: stream.read(1048576), b''):
        digest.update(block)
    if digest.hexdigest() != expected:
        raise SystemExit(21)
with tarfile.open(archive, 'r:gz') as tar:
    members = tar.getmembers()
    total = 0
    seen = set()
    root = None
    if len(members) > 1000:
        raise SystemExit(81)
    for member in members:
        path = pathlib.PurePosixPath(member.name)
        if not path.parts or path.is_absolute() or '..' in path.parts or not (member.isfile() or member.isdir()) or member.name in seen:
            raise SystemExit(81)
        root = root or path.parts[0]
        if path.parts[0] != root or not root.startswith('jbpa-'):
            raise SystemExit(81)
        if member.uid != 0 or member.gid != 0 or member.mode & 0o022:
            raise SystemExit(81)
        if member.name.endswith('/bin/jbpa') and not member.mode & 0o111:
            raise SystemExit(81)
        seen.add(member.name)
        total += member.size
        if member.size > 2097152 or total > 33554432:
            raise SystemExit(81)
    tar.extractall(stage, members=members)
pathlib.Path(stage, 'root-name').write_text(root)
PY
release_name="$(cat "$stage/root-name")"
release="$stage/$release_name"
python3 -m venv "$release/.venv"
"$release/.venv/bin/python" -m pip install --disable-pip-version-check -r "$release/requirements.txt" > "$stage/runtime-setup.log" 2>&1
PYTHONPATH="$release/lib" "$release/.venv/bin/python" -m jbpa.release verify "$archive" --sha256 "$expected_hash" > "$stage/verification.json"
destination="$install_root/releases/$expected_hash"
if [[ -e "$destination" ]]; then
  printf '%s\n' '{"status":"FAILED","category":"RELEASE_ERROR","error":"RELEASE_DESTINATION_EXISTS"}'
  exit 81
fi
mv -- "$release" "$destination"
# Venv entry scripts contain the temporary path. Use its interpreter directly.
args=(install --config "$config" --result-file "$result_file" --non-interactive)
if [[ "$mode" == controlled-test ]]; then args+=(--controlled-test); fi
if [[ "$allow_unqualified" == true ]]; then args+=(--allow-unqualified); fi
trap - ERR
JBPA_PYTHON="$destination/.venv/bin/python" "$destination/bin/jbpa" "${args[@]}"
