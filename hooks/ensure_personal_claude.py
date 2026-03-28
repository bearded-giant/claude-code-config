#!/usr/bin/env python3
"""
Ensure Personal CLAUDE.md Hook
Hook: SessionStart

Symlinks a personal CLAUDE.md into ~/.claude/projects/<id>/CLAUDE.md
so project-specific personal instructions load alongside the repo's CLAUDE.md.

Lookup order for personal CLAUDE.md source:
  1. <repo_root>/wt-bootstrap/CLAUDE.md  (worktree repos)
  2. <repo_root>/.claude.personal.md     (any repo)

For worktrees, repo_root is the bare repo parent (dirname of .bare).
Symlinks into both the bare project ID and the cwd-based project ID,
since Claude Code resolves the project ID from the working directory.

NOTE: Uses only Python standard library (no external dependencies)
"""

import json
import os
import subprocess
import sys


def get_git_common_dir(cwd: str) -> str | None:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--git-common-dir"],
            capture_output=True, text=True, cwd=cwd, timeout=5
        )
        if result.returncode == 0:
            raw = result.stdout.strip()
            if not os.path.isabs(raw):
                raw = os.path.normpath(os.path.join(cwd, raw))
            return raw
    except Exception:
        pass
    return None


def path_to_project_id(path: str) -> str:
    return path.replace("/", "-").replace(".", "-")


def find_personal_claude(repo_root: str) -> str | None:
    candidates = [
        os.path.join(repo_root, "wt-bootstrap", "CLAUDE.md"),
        os.path.join(repo_root, ".claude.personal.md"),
    ]
    for c in candidates:
        if os.path.isfile(c):
            return c
    return None


def ensure_symlink(claude_projects: str, project_id: str, source: str):
    target = os.path.join(claude_projects, project_id, "CLAUDE.md")
    if os.path.exists(target) or os.path.islink(target):
        return
    os.makedirs(os.path.dirname(target), exist_ok=True)
    os.symlink(source, target)


def main():
    try:
        data = json.loads(sys.stdin.read())
    except Exception:
        return

    cwd = data.get("cwd", os.getcwd())
    claude_projects = os.path.expanduser("~/.claude/projects")

    common_dir = get_git_common_dir(cwd)

    if common_dir:
        repo_root = os.path.dirname(common_dir)
    else:
        repo_root = cwd

    source = find_personal_claude(repo_root)
    if not source:
        return

    # always ensure symlink for the cwd-based project ID (what claude code uses)
    cwd_project_id = path_to_project_id(cwd)
    ensure_symlink(claude_projects, cwd_project_id, source)

    # for worktrees, also ensure the bare repo project ID has the symlink
    if common_dir:
        bare_project_id = path_to_project_id(common_dir)
        if bare_project_id != cwd_project_id:
            ensure_symlink(claude_projects, bare_project_id, source)


if __name__ == "__main__":
    main()
