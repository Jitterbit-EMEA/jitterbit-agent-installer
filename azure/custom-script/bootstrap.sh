#!/usr/bin/env bash
set -euo pipefail
umask 077

if (( $# < 4 || $# > 5 )); then
  printf '%s\n' 'Usage: bootstrap.sh BUNDLE BUNDLE_SHA256 CONFIG RESULT_FILE [INSTALL_ROOT]' >&2
  exit 2
fi

bundle="$1"
expected_hash="$2"
config="$3"
result_file="$4"
install_root="${5:-/opt/jbpa}"

if [[ ! "$expected_hash" =~ ^[a-fA-F0-9]{64}$ || ! -f "$bundle" || ! -f "$config" ]]; then
  printf '%s\n' 'Bootstrap input is invalid' >&2
  exit 2
fi

actual_hash="$(sha256sum "$bundle")"
actual_hash="${actual_hash%% *}"
normalized_hash="$(printf '%s' "$expected_hash" | tr 'A-F' 'a-f')"
if [[ "$actual_hash" != "$normalized_hash" ]]; then
  printf '%s\n' 'Framework bundle integrity check failed' >&2
  exit 21
fi

install -d -m 0700 "$install_root" "$(dirname "$result_file")"
release="$install_root/releases/$normalized_hash"
if [[ ! -d "$release" ]]; then
  install -d -m 0700 "$install_root/releases"
  stage="$(mktemp -d "$install_root/releases/.stage.XXXXXXXX")"
  trap 'rm -rf -- "$stage"' EXIT
  python3 - "$bundle" "$stage" <<'PY'
import pathlib
import sys
import tarfile

archive = pathlib.Path(sys.argv[1])
destination = pathlib.Path(sys.argv[2])
with tarfile.open(archive, "r:gz") as tar:
    members = tar.getmembers()
    for member in members:
        path = pathlib.PurePosixPath(member.name)
        if path.is_absolute() or ".." in path.parts or not (member.isfile() or member.isdir()):
            raise SystemExit("Framework bundle contains an unsafe entry")
    tar.extractall(destination, members=members)
PY
  if [[ ! -x "$stage/bin/jbpa-bootstrap" || ! -f "$stage/requirements.txt" || ! -d "$stage/wheels" ]]; then
    printf '%s\n' 'Framework bundle is incomplete' >&2
    exit 23
  fi
  python3 -m venv "$stage/.venv"
  "$stage/.venv/bin/python" -m pip install --disable-pip-version-check --no-index \
    --find-links "$stage/wheels" -r "$stage/requirements.txt"
  mv -- "$stage" "$release"
  trap - EXIT
fi

JBPA_PYTHON="$release/.venv/bin/python" \
  "$release/bin/jbpa-bootstrap" --config "$config" --result-file "$result_file" --non-interactive
