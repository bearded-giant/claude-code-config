#!/usr/bin/env python3
"""SessionStart hook: ensure all harness memory md files are indexed in live.db.

Durability sweep. live_index.py catches memory writes during a session, but a
`giantmem index live` rebuild drops them (it rebuilds from .giantmem trees only),
and files written on another machine or before the hook existed are missed. This
upserts every ~/.claude/projects/*/memory/*.md into live.db, mtime-aware, so a
rebuild never permanently loses memory.

Reuses live_index.py helpers. Stdlib only. Writes nothing to stdout (stderr only)
so it never injects into the session context.
"""

import glob
import importlib.util
import os
import sys
from datetime import datetime, timezone

HOOK_DIR = os.path.dirname(os.path.abspath(__file__))
MEM_GLOB = os.path.expanduser("~/.claude/projects/*/memory/*.md")


def _load_live_index():
    path = os.path.join(HOOK_DIR, "live_index.py")
    spec = importlib.util.spec_from_file_location("live_index", path)
    if not spec or not spec.loader:
        raise ImportError("cannot load live_index.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def main():
    files = glob.glob(MEM_GLOB)
    if not files:
        return
    live_index = _load_live_index()
    db = live_index.open_db()
    try:
        existing = {
            row[0]: row[1]
            for row in db.execute(
                "SELECT path, mtime FROM live_docs WHERE dir_type='memory'"
            )
        }
        now = datetime.now(timezone.utc).isoformat(timespec="seconds")
        indexed = 0
        for path in files:
            try:
                mtime = int(os.path.getmtime(path))
            except OSError:
                continue
            if existing.get(path, -1) >= mtime:
                continue
            try:
                with open(path, encoding="utf-8", errors="replace") as fh:
                    content = fh.read()
            except OSError:
                continue
            project = live_index.project_from_memory_path(path)
            db.execute(
                """
                INSERT INTO live_docs (path, project, worktree_path, feature,
                    dir_type, session_id, git_sha, mtime, ingested_at, content)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(path) DO UPDATE SET
                    project=excluded.project,
                    dir_type=excluded.dir_type,
                    mtime=excluded.mtime,
                    ingested_at=excluded.ingested_at,
                    content=excluded.content
                """,
                (path, project, "", "", "memory", "", "", mtime, now, content),
            )
            indexed += 1
        db.commit()
        if indexed:
            print(
                f"giantmem: swept {indexed} memory file(s) into live.db",
                file=sys.stderr,
            )
    finally:
        try:
            db.close()
        except Exception:  # pylint: disable=broad-exception-caught
            pass


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:  # pylint: disable=broad-exception-caught
        print(f"memory_index_sweep skipped: {exc}", file=sys.stderr)
    sys.exit(0)
