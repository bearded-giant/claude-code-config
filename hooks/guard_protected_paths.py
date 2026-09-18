#!/usr/bin/env python3
"""
PreToolUse Guard Hook for Claude Code
Hook: PreToolUse (matcher: Write, Edit, MultiEdit)

Blocks writes to vendored or reference-only trees. Bash is not covered by the
matcher, so this is a guard against tool-driven edits, not a security boundary.

NOTE: Uses only Python standard library (no external dependencies)
"""

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
