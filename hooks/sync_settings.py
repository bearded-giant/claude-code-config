#!/usr/bin/env python3
"""Reconcile repo settings.json into live ~/.claude/settings.json.

Repo is authoritative for structural config (hooks/env/statusLine/mcpServers/
marketplaces/scalar flags). Home keeps runtime-mutated state. Plugins and the
permission lists are unioned so runtime additions survive. Writes home only;
the repo copy is never modified, so the git tree stays clean.
"""

import json
import os
import sys
from pathlib import Path

HOME_OWNED = {"model", "effortLevel", "theme", "feedbackSurveyState"}
UNION_DICTS = ["enabledPlugins"]
UNION_LISTS = [("permissions", "allow"), ("permissions", "ask")]

REPO_SETTINGS = Path(__file__).resolve().parents[1] / "settings.json"
HOME_SETTINGS = Path.home() / ".claude" / "settings.json"


def load(path):
    try:
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def union_list(repo_list, home_list):
    out, seen = [], set()
    for item in list(repo_list) + list(home_list):
        key = json.dumps(item, sort_keys=True)
        if key not in seen:
            seen.add(key)
            out.append(item)
    return out


def merge(repo, home):
    merged = json.loads(json.dumps(repo))

    for key in HOME_OWNED:
        if key in home:
            merged[key] = home[key]

    for key in UNION_DICTS:
        combined = dict(repo.get(key, {}))
        combined.update(home.get(key, {}))
        if combined:
            merged[key] = combined

    for parent, child in UNION_LISTS:
        repo_list = repo.get(parent, {}).get(child, [])
        home_list = home.get(parent, {}).get(child, [])
        unioned = union_list(repo_list, home_list)
        if unioned:
            merged.setdefault(parent, {})[child] = unioned

    return merged


def main():
    if REPO_SETTINGS.resolve() == HOME_SETTINGS.resolve():
        return
    repo = load(REPO_SETTINGS)
    if not repo:
        return
    home = load(HOME_SETTINGS)
    merged = merge(repo, home)

    new_text = json.dumps(merged, indent=2) + "\n"
    if HOME_SETTINGS.exists() and HOME_SETTINGS.read_text() == new_text:
        return

    if HOME_SETTINGS.exists():
        backup = HOME_SETTINGS.with_suffix(".json.sync.bak")
        backup.write_text(HOME_SETTINGS.read_text())

    tmp = HOME_SETTINGS.with_suffix(".json.tmp")
    tmp.write_text(new_text)
    os.replace(tmp, HOME_SETTINGS)
    print("synced settings.json (repo -> ~/.claude)", file=sys.stderr)


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:  # pylint: disable=broad-exception-caught
        print(f"sync_settings skipped: {exc}", file=sys.stderr)
    sys.exit(0)
