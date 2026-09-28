#!/usr/bin/env bash
set -euo pipefail
umask 077
root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
"$root/scripts/validate.sh"
export PYTHONPATH="$root/src"
exec "${JBPA_PYTHON:-$root/.venv/bin/python}" -m jbpa.release build "${1:-$root/dist}"
