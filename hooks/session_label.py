#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import random
import re
import subprocess
import sys
from pathlib import Path

STATE_DIR = Path(os.environ.get("TMPDIR", "/tmp")) / "claude-session-label"
COLORS = ("red", "blue", "green", "yellow", "purple", "orange", "pink", "cyan")
FEATURE_CMD = re.compile(r"^\s*/(?:new|start|reopen)-feature\s+([A-Za-z0-9][\w.-]*)")


def active_feature(root):
    try:
        data = json.loads(
            (Path(root) / ".giantmem" / "features" / "features.json").read_text()
        )
    except (OSError, ValueError):
        return None
    if isinstance(data, dict) and isinstance(data.get("features"), (dict, list)):
        data = data["features"]
    if isinstance(data, dict):
        pairs = list(data.items())
    elif isinstance(data, list):
        pairs = [(None, row) for row in data]
    else:
        return None
    for key, row in pairs:
        if isinstance(row, dict) and row.get("status") == "in_progress":
            return row.get("name") or key
    return None


def read_bytes(path):
    try:
        return Path(path).read_bytes()
    except (OSError, TypeError):
        return b""


def last_row(data, kind):
    marker = f'"type":"{kind}"'.encode()
    end = len(data)
    while True:
        i = data.rfind(marker, 0, end)
        if i == -1:
            return None
        start = data.rfind(b"\n", 0, i) + 1
        stop = data.find(b"\n", i)
        try:
            row = json.loads(data[start : stop if stop != -1 else len(data)])
        except ValueError:
            row = None
        if isinstance(row, dict) and row.get("type") == kind:
            return row
        end = start


def load(sid):
    try:
        state = json.loads((STATE_DIR / f"{sid}.json").read_text())
    except (OSError, ValueError):
        return {}
    return state if isinstance(state, dict) else {}


def save(sid, state):
    try:
        STATE_DIR.mkdir(parents=True, exist_ok=True)
        (STATE_DIR / f"{sid}.json").write_text(json.dumps(state))
    except OSError:
        pass


def send_color(pane, color):
    # no hook output sets the color; /color is an immediate command, so typed into the pane it runs mid-turn and never reaches the model
    # the sleep lets the submitted prompt clear the input box first
    subprocess.Popen(  # pylint: disable=consider-using-with
        [
            "sh",
            "-c",
            'sleep 0.4; tmux send-keys -t "$1" -l "/color $2" && tmux send-keys -t "$1" Enter',
            "sh",
            pane,
            color,
        ],
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
    )


def decide(data, state, feature):
    if data.get("hook_event_name") == "SessionStart":
        if data.get("source") in ("startup", "clear"):
            state["feature"] = feature
            return feature, None
        state.setdefault("feature", feature)
        return None, None

    transcript = None
    title = None
    match = FEATURE_CMD.match(data.get("prompt") or "")
    if match:
        title = match.group(1)
    elif feature and feature != state.get("feature"):
        title = feature
    elif not state.get("title"):
        transcript = read_bytes(data.get("transcript_path"))
        named = last_row(transcript, "custom-title")
        if named and named.get("customTitle"):
            state["title"] = named["customTitle"]
        else:
            ai = last_row(transcript, "ai-title") or {}
            title = feature or ai.get("aiTitle")
    state["feature"] = feature
    return title, transcript


def main():
    try:
        data = json.load(sys.stdin)
    except ValueError:
        return
    if not isinstance(data, dict):
        return
    if os.environ.get("CLAUDE_CODE_ENTRYPOINT", "cli") != "cli":
        return
    sid = re.sub(r"[^A-Za-z0-9_-]", "", data.get("session_id") or "")
    if not sid:
        return

    root = os.environ.get("CLAUDE_PROJECT_DIR") or data.get("cwd") or os.getcwd()
    state = load(sid)
    title, transcript = decide(data, state, active_feature(root))

    pane = os.environ.get("TMUX_PANE")
    if (
        data.get("hook_event_name") == "UserPromptSubmit"
        and pane
        and not state.get("colored")
    ):
        if transcript is None:
            transcript = read_bytes(data.get("transcript_path"))
        if not last_row(transcript, "agent-color"):
            # seeded by the claude pid so a /clear in the same process re-sends the same color
            seed = os.environ.get("CLAUDE_PID") or sid
            send_color(pane, random.Random(seed).choice(COLORS))
        state["colored"] = True

    if title and title != state.get("title"):
        state["title"] = title
        print(
            json.dumps(
                {
                    "hookSpecificOutput": {
                        "hookEventName": data.get("hook_event_name"),
                        "sessionTitle": title,
                    }
                }
            )
        )
    save(sid, state)


if __name__ == "__main__":
    main()
