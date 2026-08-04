#!/usr/bin/env python3
"""UserPromptSubmit hook: re-inject standing user constraints every prompt.

Prints config/standing-constraints.md verbatim so scope / artifact-vs-execution
invariants land late in context each turn and survive project-level instruction
conflicts. Best-effort: missing file or any error prints nothing.
"""

import os
from pathlib import Path

CONSTRAINTS = Path(__file__).resolve().parents[1] / "config" / "standing-constraints.md"


def main() -> None:
    override = os.environ.get("CLAUDE_STANDING_CONSTRAINTS")
    path = Path(os.path.expanduser(override)) if override else CONSTRAINTS
    try:
        content = path.read_text(encoding="utf-8").strip()
    except OSError:
        return
    if content:
        print(content)


if __name__ == "__main__":
    main()
