#!/usr/bin/env python3
"""
Debug Stop Check Hook for Claude Code
Hook: Stop

Checks for active (unresolved) debug files in .giantmem/debug/.
If found, blocks Claude from stopping until the debug file's
next_action is updated or the file is moved to resolved/.

Prevents context loss during debug sessions by ensuring the
persistent debug state is current before the session ends.

NOTE: Uses only Python standard library (no external dependencies)
"""

import sys
import json
import os
import re
from pathlib import Path


def find_workspace_dir(cwd: str) -> Path | None:
    path = Path(cwd)
    giantmem = path / ".giantmem"
    if giantmem.exists():
        return giantmem
    return None


def find_active_feature(workspace_dir: Path) -> str | None:
    features_json = workspace_dir / "features" / "features.json"
    if not features_json.exists():
        return None
    try:
        data = json.loads(features_json.read_text())
        for name, feat in data.items():
            if feat.get("status") == "in_progress":
                return name
    except (json.JSONDecodeError, OSError):
        pass
    return None


def find_debug_dirs(workspace_dir: Path) -> list[Path]:
    dirs = []
    # top-level debug dir
    top = workspace_dir / "debug"
    if top.exists():
        dirs.append(top)
    # feature-scoped debug dirs
    features_dir = workspace_dir / "features"
    if features_dir.exists():
        for feature_dir in features_dir.iterdir():
            if feature_dir.is_dir():
                debug_dir = feature_dir / "debug"
                if debug_dir.exists():
                    dirs.append(debug_dir)
    return dirs


def has_unresolved_debug(debug_dir: Path) -> list[str]:
    unresolved = []
    for md_file in debug_dir.glob("*.md"):
        # skip resolved directory
        if "resolved" in md_file.parts:
            continue
        try:
            content = md_file.read_text()
            # check if resolution section has actual content
            resolution_match = re.search(
                r'^## Resolution\s*\n(.*?)(?=^## |\Z)',
                content, re.MULTILINE | re.DOTALL
            )
            if resolution_match:
                body = resolution_match.group(1).strip()
                # if resolution has real content (not just template placeholders), it's resolved
                if body and not body.startswith("root_cause:") or "root_cause: " in body:
                    # has filled resolution -- check if it's just the template
                    lines = [l.strip() for l in body.split("\n") if l.strip()]
                    filled = any(
                        ":" in l and not l.endswith(":")
                        and l.split(":", 1)[1].strip()
                        for l in lines
                    )
                    if filled:
                        continue
            # no resolution or empty resolution -- this is active
            unresolved.append(md_file.stem)
        except OSError:
            continue
    return unresolved


def main():
    try:
        input_data = json.load(sys.stdin)

        # don't block if we're already continuing from a stop hook
        if input_data.get("stop_hook_active", False):
            return

        cwd = os.getenv("CLAUDE_PROJECT_DIR") or input_data.get("cwd", os.getcwd())
        workspace_dir = find_workspace_dir(cwd)
        if not workspace_dir:
            return

        debug_dirs = find_debug_dirs(workspace_dir)
        if not debug_dirs:
            return

        all_unresolved = []
        for d in debug_dirs:
            all_unresolved.extend(has_unresolved_debug(d))

        if not all_unresolved:
            return

        names = ", ".join(all_unresolved[:3])
        suffix = f" (+{len(all_unresolved) - 3} more)" if len(all_unresolved) > 3 else ""

        result = {
            "decision": "block",
            "reason": f"Active debug session(s): {names}{suffix}. Update next_action in the debug file or move to debug/resolved/ before stopping."
        }
        print(json.dumps(result))

    except Exception:
        # never crash -- let claude stop normally on error
        pass


if __name__ == "__main__":
    main()
