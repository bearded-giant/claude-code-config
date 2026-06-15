#!/usr/bin/env python3
import json
import os
import subprocess

LISTS_DIR = os.path.expanduser("~/.local/share/nvim/doit/lists")


def git_root(cwd: str) -> str:
    try:
        out = subprocess.run(
            ["git", "-C", cwd, "rev-parse", "--show-toplevel"],
            capture_output=True,
            text=True,
            timeout=2,
        )
        if out.returncode == 0 and out.stdout.strip():
            return out.stdout.strip()
    except Exception:
        pass
    return cwd


def active_feature(root: str):
    path = os.path.join(root, ".giantmem", "features", "features.json")
    try:
        with open(path) as fh:
            data = json.load(fh)
    except Exception:
        return None
    if not isinstance(data, dict):
        return None
    for name, meta in data.items():
        if isinstance(meta, dict) and meta.get("status") == "in_progress":
            return name
    return None


def main() -> None:
    cwd = os.environ.get("CLAUDE_PROJECT_DIR") or os.getcwd()
    root = git_root(cwd)
    leaf = os.path.basename(root)
    parent = os.path.basename(os.path.dirname(root))
    # parent ending -wt is the worktree container; fold it into the name so
    # parallel worktrees of the same repo don't collide on one list
    base = f"{parent}-{leaf}" if parent.endswith("-wt") else leaf
    feat = active_feature(root)
    name = f"{base}-{feat}" if feat else base

    exists = os.path.isfile(os.path.join(LISTS_DIR, f"{name}.json"))

    feat_note = f"feature: {feat}" if feat else "(no active feature)"
    exists_note = "yes" if exists else "no — create on first claude: assignment"
    lines = [
        "<system-reminder>",
        "doit session list (repo-qualified, worktree-aware):",
        f"  list: {name}   {feat_note}",
        f"  exists: {exists_note}",
        "Assign model work: prefix a doit todo `claude:`. Drain it: /burn. "
        "If the list exists, list_todos it (doit MCP) and surface pending claude: items.",
        "</system-reminder>",
    ]
    print("\n".join(lines))


if __name__ == "__main__":
    main()
