#!/usr/bin/env bash
set -euo pipefail
root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$root"
export PYTHONDONTWRITEBYTECODE=1
export PYTHONPATH="$root/src:$root"
python="${JBPA_PYTHON:-$root/.venv/bin/python}"
"$python" -m ruff check src tests scripts azure/integration azure/provisioning tools/handoff
"$python" -m ruff format --check src tests scripts azure/integration azure/provisioning tools/handoff
"$python" -m yamllint config .yamllint.yaml
for file in bin/* scripts/*.sh azure/custom-script/*.sh; do bash -n "$file"; done
if command -v shellcheck >/dev/null 2>&1; then shellcheck bin/* scripts/*.sh azure/custom-script/*.sh; else printf '%s\n' 'SKIPPED shellcheck: not installed'; fi
if command -v shfmt >/dev/null 2>&1; then shfmt -d -i 2 bin/* scripts/*.sh azure/custom-script/*.sh; else printf '%s\n' 'SKIPPED shfmt: not installed'; fi
"$python" scripts/check_repository.py
