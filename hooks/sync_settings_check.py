#!/usr/bin/env python3
"""Regression checks for sync_settings.py write decisions.

Run by hand: python3 hooks/sync_settings_check.py
Not a registered hook.
"""

import importlib.util
import json
import os
import sys
import tempfile
from pathlib import Path
from typing import Any

HERE = os.path.dirname(os.path.abspath(__file__))
spec = importlib.util.spec_from_file_location(
    "ss", os.path.join(HERE, "sync_settings.py")
)
assert spec is not None and spec.loader is not None
ss: Any = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ss)

REPO = {
    "statusLine": {"type": "command", "command": "x"},
    "permissions": {"allow": ["Bash(ls:*)"], "defaultMode": "bypassPermissions"},
    "enabledPlugins": {"a@m": True},
}


def run(home_text):
    tmp = Path(tempfile.mkdtemp())
    home = tmp / "settings.json"
    if home_text is not None:
        home.write_text(home_text)
    ss.HOME_SETTINGS = home
    ss.load_repo_settings = lambda: json.loads(json.dumps(REPO))
    ss.main()
    return home, home.with_suffix(".json.sync.bak").exists()


def main():
    # home already equals the merge, but key order and indent differ: no write
    live = ss.merge(REPO, {"model": "opus", "effortLevel": "high"})
    reordered = json.dumps(dict(reversed(list(live.items()))), indent=4)
    home, backed_up = run(reordered)
    assert home.read_text() == reordered, "reordered-only file was rewritten"
    assert not backed_up, "backup written for reordered-only file"

    # repo-owned key drifted in home: write and back up
    drifted = dict(live, statusLine={"type": "command", "command": "old"})
    home, backed_up = run(json.dumps(drifted))
    assert json.loads(home.read_text())["statusLine"]["command"] == "x"
    assert backed_up, "no backup on a real change"

    # home-owned key survives the write
    assert json.loads(home.read_text())["model"] == "opus"

    # no home file: seeded, nothing to back up
    home, backed_up = run(None)
    assert json.loads(home.read_text()) == ss.merge(REPO, {})
    assert not backed_up

    print("sync_settings checks passed")


if __name__ == "__main__":
    try:
        main()
    except AssertionError:
        print("sync_settings checks FAILED", file=sys.stderr)
        raise
