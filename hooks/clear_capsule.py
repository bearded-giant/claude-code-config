#!/usr/bin/env python3
"""SessionStart: after /clear, inject a short capsule of the session that was cleared."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

MARKER_DIR = Path("/tmp")
ASKS = 3
EDITED = 12
REPLY_CHARS = 700


def claude_proc() -> tuple[int, str] | None:
    pid = os.getpid()
    for _ in range(10):
        try:
            out = subprocess.run(
                ["ps", "-o", "ppid=,lstart=,comm=", "-p", str(pid)],
                capture_output=True,
                text=True,
                timeout=2,
                check=False,
            ).stdout.split()
        except (OSError, subprocess.SubprocessError):
            return None
        if len(out) < 7:
            return None
        ppid, lstart, comm = int(out[0]), " ".join(out[1:6]), " ".join(out[6:])
        if Path(comm).name == "claude":
            return pid, lstart
        if ppid <= 1:
            return None
        pid = ppid
    return None


def _texts(content):
    if isinstance(content, str):
        return [content]
    if not isinstance(content, list):
        return []
    return [
        b.get("text", "")
        for b in content
        if isinstance(b, dict) and b.get("type") == "text"
    ]


def capsule(sid: str, transcript_path: str) -> str:
    asks, edited, reply = [], [], ""
    try:
        lines = Path(os.path.expanduser(transcript_path)).read_text(
            encoding="utf-8", errors="replace"
        )
    except OSError:
        return ""
    for line in lines.splitlines():
        try:
            m = json.loads(line)
        except ValueError:
            continue
        if m.get("isSidechain") or m.get("isMeta"):
            continue
        msg = m.get("message") or {}
        if m.get("type") == "user":
            for t in _texts(msg.get("content")):
                t = t.strip()
                # command caveats, local stdout, and injected reminders are not asks
                if t and not t.startswith("<"):
                    asks.append(" ".join(t.split())[:200])
        elif m.get("type") == "assistant":
            content = msg.get("content") or []
            text = "\n".join(_texts(content)).strip()
            if text:
                reply = text
            for b in content:
                if not isinstance(b, dict) or b.get("type") != "tool_use":
                    continue
                path = (b.get("input") or {}).get("file_path")
                if (
                    b.get("name") in ("Edit", "Write", "MultiEdit", "NotebookEdit")
                    and path
                    and path not in edited
                ):
                    edited.append(path)
    if not asks and not reply:
        return ""
    out = [
        "<system-reminder>",
        (
            f"/clear capsule: this process just cleared session {sid}. Its transcript is intact: "
            f"`claude --resume {sid}` restores the full context."
        ),
        "Background only: pick it up only when the next ask continues that work.",
    ]
    if asks:
        out += ["", "last asks:"] + [f"- {a}" for a in asks[-ASKS:]]
    if edited:
        out += ["", "edited: " + ", ".join(edited[-EDITED:])]
    if reply:
        tail = reply[-REPLY_CHARS:]
        out += [
            "",
            "last reply" + (" (tail):" if len(reply) > REPLY_CHARS else ":"),
            tail,
        ]
    out.append("</system-reminder>")
    return "\n".join(out)


def main() -> None:
    if os.environ.get("CLAUDE_CODE_ENTRYPOINT", "cli").startswith("sdk"):
        return
    try:
        data = json.load(sys.stdin)
    except ValueError:
        return
    proc = claude_proc()
    if proc is None:
        return
    pid, lstart = proc
    marker = MARKER_DIR / f"claude-clear-capsule-{pid}.json"
    try:
        prev = json.loads(marker.read_text())
    except (OSError, ValueError):
        prev = {}
    sid = data.get("session_id", "")
    try:
        marker.write_text(
            json.dumps(
                {
                    "session_id": sid,
                    "transcript_path": data.get("transcript_path", ""),
                    "lstart": lstart,
                }
            )
        )
    except OSError:
        pass
    # a reused pid leaves a marker from a dead process; its start time differs
    if data.get("source") != "clear" or prev.get("lstart") != lstart:
        return
    if prev.get("session_id") in (None, "", sid):
        return
    text = capsule(prev["session_id"], prev.get("transcript_path", ""))
    if text:
        print(text)


if __name__ == "__main__":
    main()
