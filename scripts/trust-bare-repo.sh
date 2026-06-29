#!/usr/bin/env bash
# Mark a git bare-repo path as trusted in ~/.claude.json so Claude Code honors
# permissions.allow from worktree .claude/settings.json. New CC keys worktree
# trust on the common/bare repo root, not the worktree path.
set -euo pipefail

if [[ $# -ne 1 ]]; then
  echo "usage: $(basename "$0") <bare-repo-path>" >&2
  exit 2
fi

target=$(python3 -c 'import os,sys; print(os.path.realpath(os.path.expanduser(sys.argv[1])))' "$1")

CLAUDE_JSON="${CLAUDE_JSON:-$HOME/.claude.json}"

python3 - "$CLAUDE_JSON" "$target" <<'PY'
import json, sys
path, target = sys.argv[1], sys.argv[2]
with open(path) as f:
    d = json.load(f)
proj = d.setdefault("projects", {}).setdefault(target, {})
was = proj.get("hasTrustDialogAccepted")
proj["hasTrustDialogAccepted"] = True
with open(path, "w") as f:
    json.dump(d, f, indent=2)
print(f"trusted: {target} (was hasTrustDialogAccepted={was})")
PY
