#!/usr/bin/env python3
import datetime as dt
import json
import os
import re
import sys
from pathlib import Path
from zoneinfo import ZoneInfo

VAULT = Path(os.environ.get("OBSIDIAN_VAULT", "~/Recharge-Notes")).expanduser()
ET = ZoneInfo("America/New_York")
FRONTMATTER = re.compile(r"\A---\n(.*?\n)---\n", re.DOTALL)


def handoff_path(data):
    if data.get("tool_name") not in ("Write", "Edit", "MultiEdit"):
        return None
    raw = (data.get("tool_input") or {}).get("file_path") or ""
    path = Path(raw).expanduser()
    try:
        rel = path.resolve().relative_to((VAULT / "areas").resolve())
    except (OSError, ValueError):
        return None
    if rel.suffix != ".md" or "handoffs" not in rel.parts:
        return None
    return path


def value_of(text, key):
    m = FRONTMATTER.match(text or "")
    if not m:
        return None
    for line in m.group(1).splitlines():
        if line.startswith(f"{key}:"):
            return line.split(":", 1)[1].strip().strip("'\"") or None
    return None


def as_et(value):
    try:
        parsed = dt.datetime.fromisoformat(value or "")
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return None
    return parsed.astimezone(ET).isoformat(timespec="seconds")


def stamp(text, original, now):
    m = FRONTMATTER.match(text)
    if not m:
        return None
    current, prior = value_of(text, "created"), value_of(original, "created")
    created = (
        now
        if original is None
        else as_et(prior) or as_et(current) or current or prior or now
    )
    lines = m.group(1).splitlines()
    for key, value in (("created", created), ("updated", now)):
        hit = [i for i, line in enumerate(lines) if line.startswith(f"{key}:")]
        if hit:
            lines[hit[0]] = f"{key}: {value}"
        else:
            lines.append(f"{key}: {value}")
    return "---\n" + "\n".join(lines) + "\n---\n" + text[m.end() :]


def main():
    try:
        data = json.load(sys.stdin)
    except ValueError:
        return
    if not isinstance(data, dict) or data.get("hook_event_name") != "PostToolUse":
        return
    path = handoff_path(data)
    if not path:
        return
    resp = data.get("tool_response")
    resp = resp if isinstance(resp, dict) else {}
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return
    original = resp.get("originalFile")
    if resp.get("type") == "create":
        original = None
    elif not isinstance(original, str):
        original = text
    now = dt.datetime.now(ET).isoformat(timespec="seconds")
    stamped = stamp(text, original, now)
    if not stamped or stamped == text:
        return
    path.write_text(stamped, encoding="utf-8")
    print(
        json.dumps(
            {
                "hookSpecificOutput": {
                    "hookEventName": "PostToolUse",
                    "additionalContext": f"handoff_stamp set created/updated (ET) in {path}; Read it before another Edit.",
                }
            }
        )
    )


if __name__ == "__main__":
    main()
