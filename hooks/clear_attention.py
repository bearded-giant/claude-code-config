#!/usr/bin/env python3
"""UserPromptSubmit hook: clear a session's paused-awaiting-user marker.

When you reply, the session is no longer waiting. Restores the tmux window
name and removes the marker + sentinel left by request_attention.py /
notify_attention.py. Stdlib only; never blocks the prompt, never raises.
"""

import json
import os
import re
import subprocess
import sys
from pathlib import Path

ATTENTION_DIR = Path.home() / ".claude" / "attention"


def _slug(cwd: str) -> str:
    return re.sub(r"[^A-Za-z0-9]+", "_", cwd).strip("_") or "root"


def _tmux(*args: str) -> None:
    if not os.getenv("TMUX"):
        return
    try:
        subprocess.run(["tmux", *args], capture_output=True, text=True, timeout=3)
    except (OSError, subprocess.SubprocessError):
        pass


def main() -> None:
    try:
        input_data = json.load(sys.stdin)
        cwd = os.getenv("CLAUDE_PROJECT_DIR") or input_data.get("cwd", os.getcwd())
        marker = ATTENTION_DIR / f"{_slug(cwd)}.json"
        if not marker.exists():
            return

        data = json.loads(marker.read_text())
        win = data.get("tmux_window")
        name = data.get("tmux_window_name")
        if win and name:
            _tmux("rename-window", "-t", win, name)
            # restore the original automatic-rename state (1 -> on); leave off otherwise
            if data.get("tmux_auto_rename") == "1":
                _tmux("set-window-option", "-t", win, "automatic-rename", "on")

        marker.unlink(missing_ok=True)
        marker.with_suffix(".notified").unlink(missing_ok=True)
    except Exception:
        pass


if __name__ == "__main__":
    main()
