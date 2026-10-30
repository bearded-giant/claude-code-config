#!/usr/bin/env python3
import html
import json
import os
import re
import shutil
import sys
from pathlib import Path

# same layout as cache_file in skills/obsidian-note/scripts/note.py
CACHE = Path(
    os.environ.get("ARTIFACT_CACHE", "~/.local/share/claude-artifact")
).expanduser()
ARTIFACT_URL = re.compile(r"https://claude\.ai/[\w./-]*artifact/[\w-]+")
SOURCE_RE = re.compile(r'<meta name="source-note" content="([^"]+)"')
STAMP_RE = re.compile(r"\bRev\s+(\d+)\s*·\s*\d{4}-\d{2}-\d{2}[ T]\d{2}:\d{2}")
CHANGELOG_RE = re.compile(
    r"change\s*log|revision history|version history|release notes|what'?s new"
    r"|what changed|recent changes|changes (in|since)|update log|^history$",
    re.IGNORECASE,
)
HEADING_RE = re.compile(
    r"<h[1-6][^>]*>(.*?)</h[1-6]>|^#{1,6}\s+(.+)$",
    re.IGNORECASE | re.MULTILINE | re.DOTALL,
)


def visible_text(src):
    src = re.sub(
        r"<(script|style)\b.*?</\1>", " ", src, flags=re.IGNORECASE | re.DOTALL
    )
    return html.unescape(re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", src)))


def problems(src):
    out = []
    if not STAMP_RE.search(visible_text(src)):
        out.append("no visible `Rev N · YYYY-MM-DD HH:MM TZ` stamp under the title")
    for m in HEADING_RE.finditer(src):
        heading = visible_text(m.group(1) or m.group(2)).strip()
        if CHANGELOG_RE.search(heading):
            out.append(f"changelog heading `{heading}`")
    return out


def cache(data, path, src):
    if not ARTIFACT_URL.search(json.dumps(data.get("tool_response"))):
        return
    stamp, source = STAMP_RE.search(visible_text(src)), SOURCE_RE.search(src)
    if not (stamp and source):
        return
    dest = (
        CACHE / Path(source.group(1)).with_suffix("") / f"rev-{stamp.group(1)}.html"
    ).resolve()
    if not dest.is_relative_to(CACHE.resolve()):
        return
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(Path(path).expanduser(), dest)


def main():
    try:
        data = json.load(sys.stdin)
    except Exception:  # pylint: disable=broad-exception-caught
        return
    ti = data.get("tool_input") or {}
    path = ti.get("file_path") or ""
    if ti.get("action", "publish") != "publish" or ti.get("asset"):
        return
    if not path.endswith((".html", ".htm", ".md")):
        return
    try:
        src = Path(path).expanduser().read_text(encoding="utf-8", errors="replace")
    except OSError:
        return
    if data.get("hook_event_name") == "PostToolUse":
        cache(data, path, src)
        return
    found = problems(src)
    if not found:
        return
    print(
        json.dumps(
            {
                "decision": "block",
                "reason": "Artifact blocked by claude-artifact rules: "
                + "; ".join(found)
                + ". Add the stamp, rewrite history as current-state prose, then republish.",
            }
        )
    )


if __name__ == "__main__":
    main()
