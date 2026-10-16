#!/usr/bin/env python3
"""
SessionStart hook: prime Claude with workspace context.

Calls `giantmem prime --json` for the current project dir, wraps the result in
a <system-reminder> tag, and prints it to stdout. Claude reads SessionStart
hook stdout as injected context, so this becomes invisible to the user but
visible to Claude.

Stdlib only. Fails silently if giantmem is missing.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess


def main() -> None:
    cwd = os.environ.get("CLAUDE_PROJECT_DIR") or os.getcwd()

    binary = shutil.which("giantmem") or os.path.expanduser("~/.local/bin/giantmem")
    if not os.path.isfile(binary):
        return

    try:
        out = subprocess.run(
            [binary, "prime", "--json", cwd],
            capture_output=True,
            text=True,
            timeout=8,
            check=False,
        )
    except subprocess.TimeoutExpired:
        return
    except (OSError, ValueError):
        return

    if out.returncode != 0 or not out.stdout.strip():
        return

    try:
        data = json.loads(out.stdout)
    except json.JSONDecodeError:
        return

    text = render(data)
    if text:
        print(text)


def render(data: dict) -> str | None:
    if not (
        data.get("active_feature") or data.get("recent_docs") or data.get("open_mrs")
    ):
        return None

    lines = ["<system-reminder>", "giantmem prime: workspace context"]
    lines.append(f"project: {data.get('project','?')}")
    if data.get("worktree_path"):
        lines.append(f"worktree: {data['worktree_path']}")
    if data.get("active_feature"):
        lines.append(f"active feature: {data['active_feature']}")

    if data.get("recent_docs"):
        lines.append("")
        lines.append("recent .giantmem/ writes:")
        for d in data["recent_docs"]:
            tag = d.get("dir_type") or ""
            feat = f" [{d['feature']}]" if d.get("feature") else ""
            lines.append(f"  - {tag}{feat} {d['path']}")

    if data.get("open_mrs"):
        lines.append("")
        lines.append(
            "open MRs from this project's sessions (giantmem mr list for more):"
        )
        for m in data["open_mrs"]:
            state = m.get("state") or "?"
            if m.get("cached"):
                state += " (cached)"
            opener = m.get("opener") or "-"
            if m.get("role") == "touched":
                opener += " (first touched)"
            lines.append(
                f"  - {m.get('label','?')}  {state}  {opener}  {m.get('url','')}"
            )

    lines.append("</system-reminder>")
    return "\n".join(lines)


if __name__ == "__main__":
    main()
