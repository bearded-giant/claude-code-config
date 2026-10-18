#!/usr/bin/env python3
import importlib.util
import json
import os
import sys
from pathlib import Path

BYPASS_ENV = "DOIT_ACTIVE_GATE"


def prime():
    spec = importlib.util.spec_from_file_location(
        "doit_session_prime", Path(__file__).with_name("doit_session_prime.py")
    )
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def check(p, cwd):
    root = p.git_root(cwd)
    name = p.list_name(root, p.active_feature(root))
    path = os.path.join(p.LISTS_DIR, f"{name}.json")
    if not os.path.isfile(path):
        return None
    # a list created mid-session missed the SessionStart link; daily stays, the user may have switched to it
    p.link_window(name, follow=("",))
    todos = p.load_todos(path) or []
    pending = [t for t in todos if isinstance(t, dict) and not t.get("done")]
    if not pending or any(t.get("in_progress") for t in pending):
        return None
    return name, len(pending)


def reason(name, count):
    return (
        f'doit_active_gate: nothing is in_progress on "{name}" ({count} pending), '
        "so the user's tmux chip cannot show what is next. Call start_todo "
        f'list="{name}" on the item that is next: the one you are working, else '
        "the one waiting on the user (owed, gate, decision), else the top pending "
        "item. Then end with one line naming it; do not repeat the report."
    )


def main():
    try:
        data = json.load(sys.stdin) or {}
    except ValueError:
        return
    # one block per stop, so a failing start_todo cannot loop the session
    if data.get("stop_hook_active") or os.environ.get(BYPASS_ENV, "").lower() == "off":
        return
    p = prime()
    if not p.interactive():
        return
    cwd = os.environ.get("CLAUDE_PROJECT_DIR") or data.get("cwd") or os.getcwd()
    found = check(p, cwd)
    if found:
        print(json.dumps({"decision": "block", "reason": reason(*found)}))


if __name__ == "__main__":
    main()
