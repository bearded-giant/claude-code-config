#!/usr/bin/env python3
import os
import shutil
import subprocess
import sys

WEZTERM_BUNDLE = "com.github.wez.wezterm"


def _tmux(*args: str) -> str | None:
    try:
        out = subprocess.run(
            ["tmux", *args], capture_output=True, text=True, timeout=3, check=False
        )
        return out.stdout.strip() if out.returncode == 0 else None
    except (OSError, subprocess.SubprocessError):
        return None


def _notify_mac(title: str, message: str, pane: str) -> None:
    tn = shutil.which("terminal-notifier")
    if tn:
        # click focuses wezterm + jumps to the paused tmux window
        execute = f"tmux select-window -t {pane}; open -b {WEZTERM_BUNDLE}"
        try:
            subprocess.run(
                [
                    tn,
                    "-title",
                    title,
                    "-message",
                    message,
                    "-sound",
                    "Submarine",
                    "-execute",
                    execute,
                ],
                capture_output=True,
                timeout=4,
                check=False,
            )
            return
        except (OSError, subprocess.SubprocessError):
            pass
    safe_t = title.replace('"', "'")
    safe_m = message.replace('"', "'")
    script = (
        f'display notification "{safe_m}" with title "{safe_t}" sound name "Submarine"'
    )
    try:
        subprocess.run(
            ["osascript", "-e", script], capture_output=True, timeout=3, check=False
        )
    except (OSError, subprocess.SubprocessError):
        pass


def main() -> None:
    pane = os.getenv("TMUX_PANE")
    if not pane:
        return
    if sys.argv[1:] == ["--clear"]:
        _tmux(
            "set-option",
            "-p",
            "-t",
            pane,
            "-u",
            "@claude_attention",
            ";",
            "set-option",
            "-p",
            "-t",
            pane,
            "-u",
            "@claude_attention_sent",
        )
        return
    reason = " ".join(sys.argv[1:]).strip() or "session paused, needs input"
    _tmux("set-option", "-p", "-t", pane, "@claude_attention", reason)
    # babysit re-raises on every /loop run while something is pending; only a new reason re-notifies
    if _tmux("show-option", "-pqv", "-t", pane, "@claude_attention_sent") == reason:
        return
    _tmux("set-option", "-p", "-t", pane, "@claude_attention_sent", reason)
    proj = (
        _tmux("display-message", "-p", "-t", pane, "#{b:pane_current_path}") or "claude"
    )
    _notify_mac(f"Claude — {proj}", reason, pane)


if __name__ == "__main__":
    main()
