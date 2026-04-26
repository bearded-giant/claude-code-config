#!/usr/bin/env python3
"""
PreCompact hook: snapshot scratch state before Claude compacts the context.

Writes ~/.giantmem-archive/precompact_<sessionid>_<ts>.md OR per-project under
.giantmem/history/precompact_<ts>.md if a worktree is detected.

Stdlib only. Silent on failure.
"""

import json
import os
import re
import sys
from datetime import datetime
from pathlib import Path


def detect_worktree(cwd: str) -> str:
    cur = Path(cwd).resolve()
    for p in [cur, *cur.parents]:
        if (p / ".git").exists():
            return str(p)
    return ""


def read_features_active(worktree: str) -> str:
    fp = Path(worktree) / ".giantmem" / "features" / "features.json"
    if not fp.exists():
        return ""
    try:
        data = json.loads(fp.read_text())
    except Exception:
        return ""
    feats = data.get("features", {})
    if isinstance(feats, dict):
        for name, f in feats.items():
            if isinstance(f, dict) and f.get("status") == "in_progress":
                return name
    elif isinstance(feats, list):
        for f in feats:
            if isinstance(f, dict) and f.get("status") == "in_progress":
                return f.get("name", "")
    return ""


def read_tail(path: Path, max_lines: int = 60) -> str:
    if not path.exists():
        return ""
    try:
        text = path.read_text(errors="replace")
    except Exception:
        return ""
    lines = text.splitlines()
    return "\n".join(lines[-max_lines:])


def main() -> None:
    try:
        data = json.load(sys.stdin)
    except Exception:
        return

    cwd = os.environ.get("CLAUDE_PROJECT_DIR") or data.get("cwd") or os.getcwd()
    sid = os.environ.get("CLAUDE_SESSION_ID", "")
    if not sid:
        tp = data.get("transcript_path", "")
        m = re.search(r"([0-9a-f-]{36})\.jsonl$", tp)
        if m:
            sid = m.group(1)

    wt = detect_worktree(cwd)
    if not wt:
        return

    target_dir = Path(wt) / ".giantmem" / "history"
    target_dir.mkdir(parents=True, exist_ok=True)

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    short = sid[:8] if sid else "unknown"
    out = target_dir / f"precompact_{ts}_{short}.md"

    feature = read_features_active(wt)
    plan_path = Path(wt) / ".giantmem" / "plans" / "current.md"
    if feature:
        feat_plan = Path(wt) / ".giantmem" / "features" / feature / "plans" / "current.md"
        if feat_plan.exists():
            plan_path = feat_plan
    plan_tail = read_tail(plan_path, 80)

    discoveries_path = Path(wt) / ".giantmem" / "context" / "discoveries.md"
    discoveries_tail = read_tail(discoveries_path, 40)

    # active session note from history (if it exists)
    history_path = Path(wt) / ".giantmem" / "history" / "sessions.md"
    history_tail = read_tail(history_path, 10)

    lines = [
        f"# precompact snapshot",
        f"",
        f"- session: `{sid}`",
        f"- captured: {datetime.now().isoformat(timespec='seconds')}",
        f"- worktree: `{wt}`",
        f"- active feature: `{feature or 'none'}`",
        f"",
    ]
    if plan_tail:
        lines += [f"## plan ({plan_path.name})", "", "```", plan_tail, "```", ""]
    if discoveries_tail:
        lines += ["## recent discoveries", "", "```", discoveries_tail, "```", ""]
    if history_tail:
        lines += ["## history tail", "", "```", history_tail, "```", ""]

    try:
        out.write_text("\n".join(lines))
    except Exception:
        pass


if __name__ == "__main__":
    main()
