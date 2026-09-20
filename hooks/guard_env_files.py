#!/usr/bin/env python3
"""
PreToolUse Guard Hook for Claude Code
Hook: PreToolUse (matcher: Read, Edit, Write, MultiEdit)

Gates .env-family files behind a prompt. Bash is not covered by the matcher, so
`cat .env` walks straight past this: a speed bump on tool-driven access, not a
security boundary.

MODE = "ask"   -> permissionDecision ask (a real prompt, if the harness honours
                  it under defaultMode bypassPermissions)
MODE = "block" -> legacy top-level decision, which bypassPermissions does not
                  override; use this if "ask" turns out to be advisory

NOTE: Uses only Python standard library (no external dependencies)
"""

import fnmatch
import json
import os
import sys

MODE = "ask"

ENV_PATTERNS = [".env", ".env.*", "*.env", ".envrc"]

# committed placeholders, secret-free by convention; prompting on them is noise
EXEMPT = {".env.example", ".env.sample", ".env.template", ".env.dist"}


def is_env_file(file_path: str) -> bool:
    name = os.path.basename(file_path)
    if name in EXEMPT:
        return False
    return any(fnmatch.fnmatch(name, pattern) for pattern in ENV_PATTERNS)


def payload(file_path: str) -> dict:
    reason = (
        f"{os.path.basename(file_path)} is an environment file and may hold "
        "secrets. Reading it puts its contents in the transcript."
    )
    if MODE == "block":
        return {"decision": "block", "reason": reason}
    return {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "ask",
            "permissionDecisionReason": reason,
        }
    }


def main():
    try:
        input_data = json.load(sys.stdin)

        tool_input = input_data.get("tool_input", {})
        file_path = tool_input.get("file_path", "")
        if not file_path:
            return

        if is_env_file(file_path):
            print(json.dumps(payload(file_path)))

    except Exception:  # pylint: disable=broad-exception-caught
        pass


if __name__ == "__main__":
    main()
