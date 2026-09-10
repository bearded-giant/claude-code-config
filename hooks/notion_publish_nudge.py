#!/usr/bin/env python3
import importlib.util
import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path

SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "md_to_notion.py"
# ponytail: the publish skill edits frontmatter right after a push; that write must not re-nudge
JUST_SYNCED_S = 300


def load_converter():
    spec = importlib.util.spec_from_file_location("md_to_notion", SCRIPT)
    if spec is None or spec.loader is None:
        raise ImportError(str(SCRIPT))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def just_synced(fm):
    synced = fm.get("notion_synced")
    if not synced:
        return False
    try:
        t = datetime.fromisoformat(synced.replace("Z", "+00:00")).timestamp()
    except ValueError:
        return False
    return time.time() - t < JUST_SYNCED_S


def emit(msg):
    sys.stdout.write(
        json.dumps(
            {
                "hookSpecificOutput": {
                    "hookEventName": "PostToolUse",
                    "additionalContext": msg,
                }
            }
        )
    )


def main():
    try:
        data = json.load(sys.stdin)
    except Exception:  # pylint: disable=broad-exception-caught
        return
    file_path = (data.get("tool_input") or {}).get("file_path") or ""
    if not file_path or "/.giantmem/" not in file_path or not file_path.endswith(".md"):
        return
    if not os.path.isabs(file_path):
        cwd = os.getenv("CLAUDE_PROJECT_DIR") or data.get("cwd") or os.getcwd()
        file_path = os.path.abspath(os.path.join(cwd, file_path))
    if not os.path.exists(file_path):
        return
    try:
        conv = load_converter()
        cfg = conv.load_config()
        fm, _ = conv.parse_frontmatter(
            Path(file_path).read_text(encoding="utf-8", errors="replace")
        )
        ok, _, rel, kind, cls = conv.gate(file_path, cfg, fm)
    except Exception:  # pylint: disable=broad-exception-caught
        return
    if not ok or cls != "auto" or just_synced(fm):
        return

    state = "update" if fm.get("notion") else "create"
    emit(
        f"publish now: {rel} (type {kind}, class auto, {state}). "
        f"Run the `notion-publish` skill on {file_path} before this turn ends. "
        f"Do not ask; the publish policy already decided."
    )


if __name__ == "__main__":
    main()
