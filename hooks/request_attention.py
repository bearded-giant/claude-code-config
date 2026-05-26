#!/usr/bin/env python3
"""Mark the current session as paused-awaiting-user.

Called by an agent (e.g. /babysit) at a genuine pause point:
    python3 ~/.claude/hooks/request_attention.py "why I need you"

Writes a marker keyed by cwd. The Stop hook (notify_attention.py) reads it
and fires a notification; UserPromptSubmit (clear_attention.py) clears it
once you reply. Stdlib only; never raises.
"""

import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path

ATTENTION_DIR = Path.home() / ".claude" / "attention"


def _slug(cwd: str) -> str:
    return re.sub(r"[^A-Za-z0-9]+", "_", cwd).strip("_") or "root"


def _tmux(*args: str) -> str | None:
    if not os.getenv("TMUX"):
        return None
    try:
        out = subprocess.run(["tmux", *args], capture_output=True, text=True, timeout=3)
        return out.stdout.strip() if out.returncode == 0 else None
    except (OSError, subprocess.SubprocessError):
        return None


def main() -> None:
    try:
        reason = " ".join(sys.argv[1:]).strip() or "session paused — needs input"
        cwd = os.getenv("CLAUDE_PROJECT_DIR") or os.getcwd()
        ATTENTION_DIR.mkdir(parents=True, exist_ok=True)
        marker = ATTENTION_DIR / f"{_slug(cwd)}.json"

        window_id = _tmux("display-message", "-p", "#{window_id}")
        window_name = _tmux("display-message", "-p", "#{window_name}")
        auto_rename = _tmux("display-message", "-p", "#{automatic-rename}")

        marker.write_text(
            json.dumps(
                {
                    "reason": reason,
                    "cwd": cwd,
                    "ts": time.time(),
                    "tmux_window": window_id,
                    "tmux_window_name": window_name,
                    "tmux_auto_rename": auto_rename,
                }
            )
        )
        # drop any stale notified sentinel so this new pause re-notifies
        sentinel = marker.with_suffix(".notified")
        if sentinel.exists():
            sentinel.unlink()
        print(f"attention marker set: {marker}")
    except Exception:
        pass


if __name__ == "__main__":
    main()
