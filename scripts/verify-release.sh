#!/usr/bin/env bash
set -euo pipefail
root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
export PYTHONPATH="$root/src"
exec "${JBPA_PYTHON:-$root/.venv/bin/python}" -m jbpa.release verify "$@"
