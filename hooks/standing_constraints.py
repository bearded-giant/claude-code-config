#!/usr/bin/env python3
"""UserPromptSubmit hook: re-inject standing user constraints.

Prints config/standing-constraints.md so scope / artifact-vs-execution
invariants land late in context. CLAUDE.md already carries these in the system
prompt for the whole session; what erodes them is compaction, not turn count,
so this fires on the first prompt, after each compact, and every REINJECT_EVERY
prompts as a drift backstop. Best-effort: any error prints nothing.
"""

import json
import os
import sys
from pathlib import Path

CONSTRAINTS = Path(__file__).resolve().parents[1] / "config" / "standing-constraints.md"
STATE_DIR = Path(os.environ.get("TMPDIR", "/tmp")) / "claude-standing-constraints"
REINJECT_EVERY = 25


def _compact_stamp(session_id: str) -> str:
    try:
        return Path(f"/tmp/claude-compact-ts-{session_id}").read_text().strip()
    except OSError:
        return ""


def _should_inject(session_id: str) -> bool:
    if not session_id:
        return True
    state_file = STATE_DIR / f"{session_id}.json"
    try:
        state = json.loads(state_file.read_text())
    except (OSError, ValueError):
        state = {}

    count = int(state.get("count", 0)) + 1
    last = int(state.get("last_inject", 0))
    stamp = _compact_stamp(session_id)
    inject = (
        count == 1
        or stamp != state.get("compact_seen", "")
        or count - last >= REINJECT_EVERY
    )

    try:
        STATE_DIR.mkdir(parents=True, exist_ok=True)
        state_file.write_text(
            json.dumps(
                {
                    "count": count,
                    "last_inject": count if inject else last,
                    "compact_seen": stamp,
                }
            )
        )
    except OSError:
        pass
    return inject


def main() -> None:
    session_id = ""
    try:
        session_id = (json.load(sys.stdin) or {}).get("session_id", "")
    except (ValueError, OSError):
        pass

    if not _should_inject(session_id):
        return

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
