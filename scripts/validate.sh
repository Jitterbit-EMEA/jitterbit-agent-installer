#!/usr/bin/env bash
set -euo pipefail
root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
"$root/scripts/test.sh"
"$root/scripts/lint.sh"
export PYTHONPATH="$root/src"
"${JBPA_PYTHON:-$root/.venv/bin/python}" -m jbpa.release validate
