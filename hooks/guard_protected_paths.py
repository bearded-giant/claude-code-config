#!/usr/bin/env python3
"""
PreToolUse Guard Hook for Claude Code
Hook: PreToolUse (matcher: Write, Edit, MultiEdit)

Blocks writes to vendored or reference-only trees. Bash is not covered by the
matcher, so this is a guard against tool-driven edits, not a security boundary.

NOTE: Uses only Python standard library (no external dependencies)
"""

from __future__ import annotations

import sys
import json
import os

PROTECTED_ROOTS = [
    # plugin code is re-downloaded on update; edits here vanish silently
    "~/.claude/plugins",
    # gitignored reference copies, not live config
    "~/dev/claude-code-config/archive",
]

PROTECTED_SUBSTRINGS = ["/node_modules/"]

# symlink view of repo .giantmem dirs (giantmem_vault.py); writes through it skip the .giantmem path hooks
GIANTMEM_VIEW = "~/giantmem-vault"


def view_target(file_path: str, cwd: str) -> str | None:
    path = os.path.normpath(os.path.join(cwd, os.path.expanduser(file_path)))
    root = os.path.expanduser(GIANTMEM_VIEW)
    if path.startswith(os.path.join(root, ".obsidian") + os.sep):
        return None
    if path == root or path.startswith(root + os.sep):
        return os.path.realpath(path)
    return None


def is_protected(file_path: str, cwd: str) -> str | None:
    if not os.path.isabs(file_path):
        file_path = os.path.join(cwd, file_path)
    real = os.path.realpath(file_path)

    for root in PROTECTED_ROOTS:
        root_real = os.path.realpath(os.path.expanduser(root))
        if real == root_real or real.startswith(root_real + os.sep):
            return root.replace("~", "")

    for pattern in PROTECTED_SUBSTRINGS:
        if pattern in real:
            return pattern.strip("/")
    return None


def main():
    try:
        input_data = json.load(sys.stdin)

        tool_input = input_data.get("tool_input", {})
        cwd = os.getenv("CLAUDE_PROJECT_DIR") or input_data.get("cwd", os.getcwd())

        file_path = tool_input.get("file_path", "")
        if not file_path:
            return

        target = view_target(file_path, cwd)
        if target:
            if target.startswith(os.path.expanduser(GIANTMEM_VIEW)):
                target = "the repo's own .giantmem path"
            result = {
                "decision": "block",
                "reason": f"{GIANTMEM_VIEW} is a read-only Obsidian view of repo .giantmem dirs. "
                f"Write {target} instead. 'The vault' means ~/Recharge-Notes.",
            }
            print(json.dumps(result))
            return

        protected = is_protected(file_path, cwd)
        if protected:
            # legacy top-level `decision` on purpose: permissionDecision values
            # are advisory under defaultMode bypassPermissions, this is not
            result = {
                "decision": "block",
                "reason": f"Protected path: {protected} is read-only. Do not modify files there.",
            }
            print(json.dumps(result))

    except Exception:
        pass


if __name__ == "__main__":
    main()
