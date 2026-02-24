#!/usr/bin/env python3
"""
PreToolUse Guard Hook for Claude Code
Hook: PreToolUse (matcher: Write, Edit, MultiEdit)

Blocks writes to protected directories that shouldn't be modified:
- archive/ (gitignored, reference only)
- plugins/marketplaces/ (third-party code)
- plugins/cache/ (downloaded plugin content)
- node_modules/ (anywhere)

NOTE: Uses only Python standard library (no external dependencies)
"""

import sys
import json
import os
PROTECTED_PATTERNS = [
    "/archive/",
    "/plugins/marketplaces/",
    "/plugins/cache/",
    "/node_modules/",
]


def is_protected(file_path: str, cwd: str) -> str | None:
    # normalize to absolute
    if not os.path.isabs(file_path):
        file_path = os.path.join(cwd, file_path)
    file_path = os.path.normpath(file_path)

    for pattern in PROTECTED_PATTERNS:
        if pattern in file_path:
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
            result = {
                "decision": "block",
                "reason": f"Protected path: {protected}/ is read-only. Do not modify files in this directory."
            }
            print(json.dumps(result))

    except Exception:
        pass


if __name__ == "__main__":
    main()
