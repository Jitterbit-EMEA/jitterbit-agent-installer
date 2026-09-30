#!/usr/bin/env bash
set -euo pipefail

if [[ $# -ne 1 ]]; then
  printf 'Usage: %s /path/to/ai-project\n' "$0" >&2
  exit 2
fi

root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
project="$(cd -- "$1" && pwd)"
if [[ ! -e "$project/.git" || ! -f "$project/integrations/jbpa/bin/jbpa-remote" ]]; then
  printf '%s\n' 'Expected a Git project with JBPA at integrations/jbpa.' >&2
  exit 2
fi

for agent in codex claude; do
  source_file="$root/.$agent/skills/jbpa/SKILL.md"
  destination="$project/.$agent/skills/jbpa/SKILL.md"
  if [[ -L "$destination" ]]; then
    printf 'Refusing a linked skill destination: %s\n' "$destination" >&2
    exit 2
  fi
  if [[ -e "$destination" ]] && ! cmp -s "$source_file" "$destination"; then
    printf 'Existing skill differs; review it before replacing: %s\n' "$destination" >&2
    exit 2
  fi
done

for agent in codex claude; do
  destination="$project/.$agent/skills/jbpa/SKILL.md"
  install -d -m 0755 "$(dirname -- "$destination")"
  install -m 0644 "$root/.$agent/skills/jbpa/SKILL.md" "$destination"
  printf 'Installed %s\n' "$destination"
done
