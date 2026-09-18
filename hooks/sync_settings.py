#!/usr/bin/env python3
"""Reconcile repo settings.json into live ~/.claude/settings.json.

Repo is authoritative for structural config (hooks/env/statusLine/mcpServers/
marketplaces/scalar flags). Home keeps runtime-mutated state. Plugins and the
permission lists are unioned so runtime additions survive. Writes home only;
the repo copy is never modified, so the git tree stays clean.

Reads the committed blob, not the working tree: syncing the tree shipped
half-finished edits to the live config on the next session start.
"""

import json
import os
import subprocess
import sys
from pathlib import Path

HOME_OWNED = {"model", "effortLevel", "theme", "feedbackSurveyState"}
UNION_DICTS = ["enabledPlugins"]
UNION_LISTS = [
    ("permissions", "allow"),
    ("permissions", "ask"),
    ("permissions", "deny"),
    ("permissions", "additionalDirectories"),
]

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


def load_repo_settings():
    try:
        result = subprocess.run(
            ["git", "-C", str(REPO_SETTINGS.parent), "show", "HEAD:settings.json"],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
        if result.returncode == 0 and result.stdout.strip():
            return json.loads(result.stdout)
        reason = (result.stderr or "").strip().splitlines()[:1]
        print(
            f"sync_settings: no committed settings.json ({reason or 'unknown'}), "
            "falling back to working tree",
            file=sys.stderr,
        )
    except (subprocess.SubprocessError, OSError, json.JSONDecodeError) as exc:
        print(
            f"sync_settings: committed read failed ({exc}), falling back to working tree",
            file=sys.stderr,
        )
    return load(REPO_SETTINGS)


def main():
    if REPO_SETTINGS.resolve() == HOME_SETTINGS.resolve():
        return
    repo = load_repo_settings()
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
