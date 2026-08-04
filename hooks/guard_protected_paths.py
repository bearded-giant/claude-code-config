#!/usr/bin/env python3
"""
PreToolUse Guard Hook for Claude Code
Hook: PreToolUse (matcher: Write, Edit, MultiEdit)

Blocks writes to protected directories that shouldn't be modified:
- archive/ (gitignored, reference only)
- plugins/marketplaces/ (third-party code)
- plugins/cache/ (downloaded plugin content)
- node_modules/ (anywhere)

Also ask-gates edits to team-shared agent config (git-tracked CLAUDE.md /
AGENTS.md / INSTRUCTIONS.md / checked-in .claude/**) outside personal repos —
the model must get explicit user approval instead of editing as a side effect.

NOTE: Uses only Python standard library (no external dependencies)
"""

import sys
import json
import os
import subprocess

PROTECTED_PATTERNS = [
    "/archive/",
    "/plugins/marketplaces/",
    "/plugins/cache/",
    "/node_modules/",
]

PERSONAL_ROOTS = [
    "~/dev/claude-code-config",
    "~/dotfiles",
    "~/.claude",
]

TEAM_SHARED_BASENAMES = {"CLAUDE.md", "AGENTS.md", "INSTRUCTIONS.md"}


def is_protected(file_path: str, cwd: str) -> str | None:
    # normalize to absolute
    if not os.path.isabs(file_path):
        file_path = os.path.join(cwd, file_path)
    file_path = os.path.normpath(file_path)

    for pattern in PROTECTED_PATTERNS:
        if pattern in file_path:
            return pattern.strip("/")
    return None


def is_team_shared_agent_config(file_path: str, cwd: str) -> bool:
    if not os.path.isabs(file_path):
        file_path = os.path.join(cwd, file_path)
    real = os.path.realpath(file_path)

    for root in PERSONAL_ROOTS:
        root_real = os.path.realpath(os.path.expanduser(root))
        if real == root_real or real.startswith(root_real + os.sep):
            return False

    if os.path.basename(real) not in TEAM_SHARED_BASENAMES and "/.claude/" not in real:
        return False

    # only git-tracked files count as team-shared; untracked/local stay editable
    try:
        result = subprocess.run(
            ["git", "-C", os.path.dirname(real), "ls-files", "--error-unmatch", real],
            capture_output=True,
            timeout=5,
        )
        return result.returncode == 0
    except Exception:
        return False


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
            result = {
                "decision": "block",
                "reason": f"Protected path: {protected}/ is read-only. Do not modify files in this directory.",
            }
            print(json.dumps(result))
            return

        if is_team_shared_agent_config(file_path, cwd):
            print(
                json.dumps(
                    {
                        "hookSpecificOutput": {
                            "hookEventName": "PreToolUse",
                            "permissionDecision": "ask",
                            "permissionDecisionReason": (
                                "Team-shared agent config (git-tracked). Proceed only if the user "
                                "explicitly directed this exact edit; otherwise propose the diff in chat."
                            ),
                        }
                    }
                )
            )

    except Exception:
        pass


if __name__ == "__main__":
    main()
