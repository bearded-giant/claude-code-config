#!/usr/bin/env python3
"""
PostToolUse hook for Claude Code: index workspace + memory *.md writes into live.db.

Hook: PostToolUse (matcher: Write, Edit, MultiEdit)

Captures:
  - path, project (worktree-aware), worktree_path, feature (active in_progress),
    dir_type (research|plans|...|memory), session_id (from CLAUDE_SESSION_ID env or
    transcript path), git_sha (HEAD), mtime, content.

Filter: files under a `.giantmem/` directory, OR harness memory files under
`~/.claude/projects/<slug>/memory/`. Anything else is skipped fast. Memory files
are tagged dir_type=memory so giantmem_recall surfaces them cross-project.

Stdlib only. No external dependencies.

Live DB:  ~/giantmem_archive/live.db   (created on first hit)
"""

import json
import os
import re
import sqlite3
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ARCHIVE_BASE = Path(
    os.environ.get("GIANTMEM_ARCHIVE_BASE", os.path.expanduser("~/giantmem_archive"))
)
LIVE_DB = ARCHIVE_BASE / "live.db"

GIANTMEM_RE = re.compile(r"/\.giantmem/")
MEMORY_RE = re.compile(r"/\.claude/projects/[^/]+/memory/")


def detect_project(cwd: str, archive_base: Path) -> tuple[str, str]:
    """Return (project_name, worktree_path). Mirrors gm Go detector."""
    cur = Path(cwd).resolve()
    root = None
    git_is_file = False
    for p in [cur, *cur.parents]:
        gp = p / ".git"
        if gp.exists():
            root = p
            git_is_file = gp.is_file()
            break
    if root is None:
        return cur.name, str(cur)

    if git_is_file:
        # bare worktree: parent dir name is the project (e.g. chat-orchestrator-wt)
        return root.parent.name, str(root)

    project = root.name
    candidate = archive_base / f"{project}-wt"
    if candidate.is_dir():
        project = f"{project}-wt"
    return project, str(root)


def feature_from_giantmem(worktree_path: str) -> str:
    fp = Path(worktree_path) / ".giantmem" / "features" / "features.json"
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


def dir_type_from_path(path: str) -> str:
    m = GIANTMEM_RE.search(path)
    if not m:
        return ""
    rest = path[m.end() :]
    parts = rest.split("/", 1)
    if not parts or not parts[0]:
        return "root"
    head = parts[0]
    return head if "." not in head else "root"


def feature_from_path(path: str) -> str:
    idx = path.find("/.giantmem/features/")
    if idx < 0:
        return ""
    rest = path[idx + len("/.giantmem/features/") :]
    parts = rest.split("/", 1)
    return parts[0] if parts and parts[0] else ""


def project_from_memory_path(path: str) -> str:
    """Best-effort project label from a ~/.claude/projects/<slug>/memory/ path.

    Slugs encode the original cwd with '/' -> '-'. Names contain real dashes, so
    exact decode is ambiguous; strip the common home/dev prefix and keep the rest.
    """
    m = re.search(r"/projects/([^/]+)/memory/", path)
    if not m:
        return "memory"
    slug = m.group(1)
    for prefix in ("-Users-bryan-dev-", "-Users-bryan-"):
        if slug.startswith(prefix):
            return slug[len(prefix) :] or slug
    return slug.lstrip("-") or "memory"


def git_sha(worktree_path: str) -> str:
    try:
        r = subprocess.run(
            ["git", "-C", worktree_path, "rev-parse", "--short", "HEAD"],
            capture_output=True,
            text=True,
            timeout=2,
        )
        return r.stdout.strip()
    except Exception:
        return ""


def session_id_from_env(input_data: dict) -> str:
    sid = os.environ.get("CLAUDE_SESSION_ID", "")
    if sid:
        return sid
    # try transcript_path -> filename is <uuid>.jsonl
    tp = input_data.get("transcript_path", "")
    if tp:
        stem = Path(tp).stem
        if re.fullmatch(r"[0-9a-f-]{36}", stem):
            return stem
    return ""


SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS live_docs (
    path TEXT PRIMARY KEY,
    project TEXT NOT NULL,
    worktree_path TEXT,
    feature TEXT,
    dir_type TEXT,
    session_id TEXT,
    git_sha TEXT,
    mtime INTEGER NOT NULL,
    ingested_at TEXT NOT NULL,
    content TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_live_project ON live_docs(project);
CREATE INDEX IF NOT EXISTS idx_live_session ON live_docs(session_id);
CREATE INDEX IF NOT EXISTS idx_live_feature ON live_docs(feature);
CREATE VIRTUAL TABLE IF NOT EXISTS live_docs_fts USING fts5(
    path, project, feature, dir_type, content,
    tokenize='porter unicode61',
    content='live_docs', content_rowid='rowid'
);
CREATE TRIGGER IF NOT EXISTS live_docs_ai AFTER INSERT ON live_docs BEGIN
    INSERT INTO live_docs_fts(rowid, path, project, feature, dir_type, content)
    VALUES (new.rowid, new.path, new.project, COALESCE(new.feature,''), COALESCE(new.dir_type,''), new.content);
END;
CREATE TRIGGER IF NOT EXISTS live_docs_ad AFTER DELETE ON live_docs BEGIN
    INSERT INTO live_docs_fts(live_docs_fts, rowid, path, project, feature, dir_type, content)
    VALUES ('delete', old.rowid, old.path, old.project, COALESCE(old.feature,''), COALESCE(old.dir_type,''), old.content);
END;
CREATE TRIGGER IF NOT EXISTS live_docs_au AFTER UPDATE ON live_docs BEGIN
    INSERT INTO live_docs_fts(live_docs_fts, rowid, path, project, feature, dir_type, content)
    VALUES ('delete', old.rowid, old.path, old.project, COALESCE(old.feature,''), COALESCE(old.dir_type,''), old.content);
    INSERT INTO live_docs_fts(rowid, path, project, feature, dir_type, content)
    VALUES (new.rowid, new.path, new.project, COALESCE(new.feature,''), COALESCE(new.dir_type,''), new.content);
END;
"""


def open_db() -> sqlite3.Connection:
    ARCHIVE_BASE.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(str(LIVE_DB), timeout=5.0)
    db.execute("PRAGMA journal_mode=WAL")
    db.execute("PRAGMA synchronous=NORMAL")
    db.executescript(SCHEMA_SQL)
    return db


def _try_log(msg: str) -> None:
    try:
        import importlib.util

        spec = importlib.util.spec_from_file_location(
            "_giantmem_log", os.path.join(os.path.dirname(__file__), "_giantmem_log.py")
        )
        if spec and spec.loader:
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            mod.log("live_index", msg)
    except Exception:
        pass


def main():
    try:
        data = json.load(sys.stdin)
    except Exception as e:
        _try_log(f"json.load failed: {e}")
        return

    # PostToolUse: tool_input has file_path; tool_name is Write|Edit|MultiEdit
    tool_input = data.get("tool_input", {}) or {}
    file_path = tool_input.get("file_path") or ""
    if not file_path:
        return
    if not file_path.endswith(".md"):
        return
    is_giantmem = bool(GIANTMEM_RE.search(file_path))
    is_memory = bool(MEMORY_RE.search(file_path))
    if not (is_giantmem or is_memory):
        return
    if not os.path.isabs(file_path):
        file_path = os.path.abspath(file_path)
    if not os.path.exists(file_path):
        return  # write may have failed

    if is_giantmem:
        cwd = (
            os.environ.get("CLAUDE_PROJECT_DIR")
            or data.get("cwd")
            or os.path.dirname(file_path)
        )
        project, worktree = detect_project(cwd, ARCHIVE_BASE)
        # prefer in-tree feature.json detection over path inference
        feature = feature_from_path(file_path) or feature_from_giantmem(worktree)
        dir_type = dir_type_from_path(file_path)
        sha = git_sha(worktree)
    else:
        project = project_from_memory_path(file_path)
        worktree = ""
        feature = ""
        dir_type = "memory"
        sha = ""
    sid = session_id_from_env(data)

    try:
        with open(file_path, "r", encoding="utf-8", errors="replace") as f:
            content = f.read()
    except Exception:
        return
    if len(content) > 5_000_000:  # skip pathologically large
        content = content[:5_000_000]

    mtime = int(os.path.getmtime(file_path))
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")

    try:
        db = open_db()
    except Exception as e:
        _try_log(f"open_db failed for {file_path}: {e}")
        return
    try:
        db.execute(
            """
            INSERT INTO live_docs (path, project, worktree_path, feature, dir_type,
                session_id, git_sha, mtime, ingested_at, content)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(path) DO UPDATE SET
                project=excluded.project,
                worktree_path=excluded.worktree_path,
                feature=excluded.feature,
                dir_type=excluded.dir_type,
                session_id=COALESCE(excluded.session_id, live_docs.session_id),
                git_sha=excluded.git_sha,
                mtime=excluded.mtime,
                ingested_at=excluded.ingested_at,
                content=excluded.content
            """,
            (
                file_path,
                project,
                worktree,
                feature,
                dir_type,
                sid,
                sha,
                mtime,
                now,
                content,
            ),
        )
        db.commit()
    except Exception as e:
        _try_log(f"insert failed for {file_path}: {e}")
    finally:
        try:
            db.close()
        except Exception:
            pass


if __name__ == "__main__":
    main()
