#!/usr/bin/env bash
set -euo pipefail
root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$root"
export PYTHONDONTWRITEBYTECODE=1
export PYTHONPATH="$root/src:$root"
exec "${JBPA_PYTHON:-$root/.venv/bin/python}" -m unittest discover -s tests/unit -v
