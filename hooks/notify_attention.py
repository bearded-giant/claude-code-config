#!/usr/bin/env python3
"""Stop hook: notify when a session paused awaiting the user.

Fires ONLY if request_attention.py left a marker for this cwd. Normal stops
(no marker) are silent. Sends a macOS notification (osascript, no install)
and flags the tmux window in the status bar. Notifies once per pause; the
.notified sentinel guards against repeat Stop events. Stdlib only; never
blocks the stop, never raises.
"""

import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

ATTENTION_DIR = Path.home() / ".claude" / "attention"
WEZTERM_BUNDLE = "com.github.wez.wezterm"


def _slug(cwd: str) -> str:
    return re.sub(r"[^A-Za-z0-9]+", "_", cwd).strip("_") or "root"


def _tmux(*args: str) -> None:
    if not os.getenv("TMUX"):
        return
    try:
        subprocess.run(["tmux", *args], capture_output=True, text=True, timeout=3)
    except (OSError, subprocess.SubprocessError):
        pass


def _notify_mac(title: str, message: str, window_id: str | None) -> None:
    tn = shutil.which("terminal-notifier")
    if tn:
        # click focuses wezterm + jumps to the paused tmux window
        execute = "open -b %s" % WEZTERM_BUNDLE
        if window_id:
            execute = "tmux select-window -t %s; %s" % (window_id, execute)
        try:
            subprocess.run(
                [tn, "-title", title, "-message", message, "-sound", "Submarine", "-execute", execute],
                capture_output=True,
                timeout=4,
            )
            return
        except (OSError, subprocess.SubprocessError):
            pass
    safe_t = title.replace('"', "'")
    safe_m = message.replace('"', "'")
    script = f'display notification "{safe_m}" with title "{safe_t}" sound name "Submarine"'
    try:
        subprocess.run(["osascript", "-e", script], capture_output=True, timeout=3)
    except (OSError, subprocess.SubprocessError):
        pass


def main() -> None:
    try:
        input_data = json.load(sys.stdin)
        if input_data.get("stop_hook_active", False):
            return
        cwd = os.getenv("CLAUDE_PROJECT_DIR") or input_data.get("cwd", os.getcwd())
        marker = ATTENTION_DIR / f"{_slug(cwd)}.json"
        if not marker.exists():
            return
        sentinel = marker.with_suffix(".notified")
        if sentinel.exists():
            return

        data = json.loads(marker.read_text())
        reason = data.get("reason", "needs input")
        proj = Path(cwd).name
        win = data.get("tmux_window")
        name = data.get("tmux_window_name") or proj

        _notify_mac(f"Claude — {proj}", reason, win)

        if win and "[!" not in name:
            _tmux("set-window-option", "-t", win, "automatic-rename", "off")
            _tmux("rename-window", "-t", win, f"{name} [!NEEDS YOU]")
            _tmux("set-window-option", "-t", win, "monitor-bell", "on")

        sentinel.write_text("1")
    except Exception:
        pass


if __name__ == "__main__":
    main()
