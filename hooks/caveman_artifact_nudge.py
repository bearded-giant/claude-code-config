#!/usr/bin/env python3
"""
PostToolUse hook: nudge Claude to compress artifact docs via the caveman skill.

Hook: PostToolUse (matcher: Write|Edit|MultiEdit)

Fires when Claude writes a long-form research/plan/review/spec doc under
`.giantmem/`. Emits `hookSpecificOutput.additionalContext` telling Claude
to run the `caveman:compress` skill on the file (or compress in-style).

Loop / noise guards:
- skip files named *.original.md (caveman backup)
- skip files smaller than MIN_BYTES (too small to be worth compressing)
- skip files containing the marker `<!-- caveman:compressed -->`
- per-session debounce: only nudge each path once via /tmp marker
- only fires for known artifact dir_types (research, reviews, plans, etc.)

Stdlib only.
"""

import hashlib
import json
import os
import re
import sys
from pathlib import Path

# minimum file size to be worth compressing
MIN_BYTES = 600

# marker that signals the file was already compressed
COMPRESSED_MARKER = "<!-- caveman:compressed -->"

# dir_types under .giantmem/ that hold long-form prose worth compressing
ARTIFACT_DIR_TYPES = {"research", "reviews", "plans", "context"}

# specific feature-scoped artifact filenames worth compressing
FEATURE_ARTIFACT_NAMES = {"spec.md", "plan.md"}

# files to never nudge on, even inside artifact dirs
SKIP_NAMES = {
    "WORKSPACE.md",
    "_index.md",
    "MEMORY.md",
    "tree.md",
    "patterns.md",  # curated, hand-maintained
    "facts.md",     # already terse key/value
    "current.md",   # transient session work, churns too fast
    "features.json",
    "meta.json",
    "plan_context.json",
}

NUDGE_DIR = Path("/tmp/claude-caveman-nudged")

GIANTMEM_RE = re.compile(r"/\.giantmem/")


def is_artifact_path(path: str) -> bool:
    """True if path looks like a long-form artifact under .giantmem/."""
    m = GIANTMEM_RE.search(path)
    if not m:
        return False
    rest = path[m.end():]
    parts = rest.split("/")
    if not parts or not parts[0]:
        return False
    head = parts[0]
    name = parts[-1]

    if name in SKIP_NAMES or name.endswith(".original.md"):
        return False
    if not name.endswith(".md"):
        return False

    # feature-scoped: .giantmem/features/{name}/...
    if head == "features" and len(parts) >= 3:
        sub = parts[2]
        leaf = parts[-1]
        if leaf in FEATURE_ARTIFACT_NAMES:
            return True
        if sub in ARTIFACT_DIR_TYPES:
            return True
        return False

    # top-level artifact dirs
    return head in ARTIFACT_DIR_TYPES


def already_compressed(path: str) -> bool:
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            head = f.read(4096)
        return COMPRESSED_MARKER in head
    except Exception:
        return False


def session_marker(session_id: str, file_path: str) -> Path:
    digest = hashlib.sha1(file_path.encode("utf-8")).hexdigest()[:16]
    return NUDGE_DIR / session_id / digest


def already_nudged(marker: Path) -> bool:
    return marker.exists()


def mark_nudged(marker: Path) -> None:
    try:
        marker.parent.mkdir(parents=True, exist_ok=True)
        marker.touch()
    except Exception:
        pass


def emit(additional_context: str) -> None:
    out = {
        "hookSpecificOutput": {
            "hookEventName": "PostToolUse",
            "additionalContext": additional_context,
        }
    }
    sys.stdout.write(json.dumps(out))


def main() -> None:
    try:
        data = json.load(sys.stdin)
    except Exception:
        return

    tool_input = data.get("tool_input") or {}
    file_path = tool_input.get("file_path") or ""
    if not file_path:
        return
    if not os.path.isabs(file_path):
        cwd = os.getenv("CLAUDE_PROJECT_DIR") or data.get("cwd") or os.getcwd()
        file_path = os.path.abspath(os.path.join(cwd, file_path))

    if not os.path.exists(file_path):
        return
    if not is_artifact_path(file_path):
        return

    try:
        size = os.path.getsize(file_path)
    except Exception:
        return
    if size < MIN_BYTES:
        return

    if already_compressed(file_path):
        return

    session_id = data.get("session_id") or os.getenv("CLAUDE_SESSION_ID") or "nosid"
    marker = session_marker(session_id, file_path)
    if already_nudged(marker):
        return
    mark_nudged(marker)

    rel = file_path
    cwd = os.getenv("CLAUDE_PROJECT_DIR") or data.get("cwd")
    if cwd and file_path.startswith(cwd):
        rel = os.path.relpath(file_path, cwd)

    msg = (
        f"Artifact written: {rel} ({size} bytes). "
        f"User wants long-form artifacts compressed via the caveman skill. "
        f"Invoke the `caveman:compress` skill on `{file_path}` now, "
        f"or rewrite the prose in caveman style (drop articles/filler/hedging, "
        f"preserve code/paths/commands exactly). "
        f"Add `{COMPRESSED_MARKER}` near the top of the file after compressing "
        f"so this hook does not re-nudge. "
        f"Skip if user explicitly asked for verbose output."
    )
    emit(msg)


if __name__ == "__main__":
    main()
