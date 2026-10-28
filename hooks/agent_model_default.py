#!/usr/bin/env python3
"""PreToolUse(Agent): default model for agent types that would inherit the session model."""

import json
import sys

# Explore ignores CLAUDE_CODE_SUBAGENT_MODEL (built-in model: inherit), so the env var can't do this
DEFAULTS = {"Explore": "haiku", "general-purpose": "sonnet"}


def rewrite(tool_input):
    if tool_input.get("model"):
        return None
    model = DEFAULTS.get(tool_input.get("subagent_type") or "general-purpose")
    if not model:
        return None
    return {**tool_input, "model": model}


def main():
    try:
        data = json.load(sys.stdin)
    except ValueError:
        return
    updated = rewrite(data.get("tool_input") or {})
    if updated is None:
        return
    print(
        json.dumps(
            {
                "hookSpecificOutput": {
                    "hookEventName": "PreToolUse",
                    "updatedInput": updated,
                }
            }
        )
    )


if __name__ == "__main__":
    main()
