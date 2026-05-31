#!/usr/bin/env python3
"""UserPromptSubmit hook: cross-project recall from giantmem (FTS5).

Replaces the dead RLabs :8765 memory_inject. Sanitizes the prompt into a
keyword OR-query, runs `giantmem find --live` (uses giantmemd if running),
filters for signal, and prepends the top hits. Best-effort: any failure
prints nothing so the prompt is never blocked.

Quality filters: drop MEMORY.md pointer indexes, drop history session-summary
noise (unless GIANTMEM_RECALL_INCLUDE_HISTORY=1), and require each hit to share
>= MIN_OVERLAP distinct keywords with the prompt.

Tunables: GIANTMEM_RECALL_LIMIT, GIANTMEM_RECALL_SINCE,
GIANTMEM_RECALL_MIN_OVERLAP, GIANTMEM_RECALL_INCLUDE_HISTORY.
"""

import json
import os
import re
import shutil
import subprocess
import sys

LIMIT = int(os.getenv("GIANTMEM_RECALL_LIMIT", "4"))
SINCE = os.getenv("GIANTMEM_RECALL_SINCE", "180d")
MIN_OVERLAP = int(os.getenv("GIANTMEM_RECALL_MIN_OVERLAP", "2"))
INCLUDE_HISTORY = os.getenv("GIANTMEM_RECALL_INCLUDE_HISTORY") == "1"
MIN_PROMPT_CHARS = 16
MAX_TERMS = 10

EXCLUDE_NAMES = {"MEMORY.md"}
EXCLUDE_DIR_TYPES = set() if INCLUDE_HISTORY else {"history"}

STOPWORDS = {
    "the",
    "and",
    "for",
    "are",
    "was",
    "were",
    "been",
    "does",
    "did",
    "how",
    "what",
    "why",
    "when",
    "where",
    "which",
    "who",
    "you",
    "this",
    "that",
    "these",
    "those",
    "should",
    "would",
    "could",
    "can",
    "will",
    "across",
    "about",
    "using",
    "use",
    "need",
    "want",
    "get",
    "got",
    "make",
    "just",
    "like",
    "not",
    "yes",
    "with",
    "from",
    "into",
    "have",
    "has",
    "but",
    "set",
    "out",
    "cannot",
    "even",
    "really",
    "actually",
    "something",
}


def keywords_from(prompt):
    seen, out = set(), []
    for token in re.findall(r"[A-Za-z0-9_]+", prompt.lower()):
        if len(token) < 3 or token in STOPWORDS or token in seen:
            continue
        seen.add(token)
        out.append(token)
        if len(out) >= MAX_TERMS:
            break
    return out


def main():
    raw = sys.stdin.read()
    try:
        data = json.loads(raw) if raw.strip() else {}
    except json.JSONDecodeError:
        return

    prompt = (data.get("prompt") or "").strip()
    if len(prompt) < MIN_PROMPT_CHARS or prompt.startswith("/"):
        return

    giantmem = shutil.which("giantmem") or os.path.expanduser("~/.local/bin/giantmem")
    if not os.path.exists(giantmem):
        return

    keywords = keywords_from(prompt)
    if not keywords:
        return
    query = " OR ".join(keywords)

    try:
        result = subprocess.run(
            [
                giantmem,
                "find",
                query,
                "--live",
                "--json",
                "--full",
                "--limit",
                str(LIMIT * 4),
                "--since",
                SINCE,
            ],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
    except (subprocess.TimeoutExpired, OSError):
        return

    try:
        hits = json.loads(result.stdout) if result.stdout.strip() else []
    except json.JSONDecodeError:
        return
    if not isinstance(hits, list) or not hits:
        return

    required = min(MIN_OVERLAP, len(keywords))
    lines = []
    for hit in hits:
        path = hit.get("filepath") or hit.get("filename") or ""
        name = os.path.basename(path)
        if name in EXCLUDE_NAMES:
            continue
        dtype = hit.get("dir_type") or hit.get("source_type") or ""
        if dtype in EXCLUDE_DIR_TYPES:
            continue
        snippet = hit.get("snippet") or hit.get("content") or hit.get("text") or ""
        snippet = re.sub(r"</?([A-Za-z0-9_]+)>", r"\1", snippet)
        snippet = re.sub(r"\s+", " ", snippet).strip()
        if sum(1 for k in keywords if k in snippet.lower()) < required:
            continue
        project = (hit.get("project") or "").strip("/") or "?"
        loc = f"{project}/{dtype}" if dtype else project
        suffix = f": {snippet[:180]}" if snippet else ""
        lines.append(f"- [{loc}] {name}{suffix}")
        if len(lines) >= LIMIT:
            break

    if not lines:
        return

    print('<giantmem-recall source="giantmem, cross-project">')
    print("Possibly-relevant prior context (verify before relying):")
    print("\n".join(lines))
    print("</giantmem-recall>")


if __name__ == "__main__":
    try:
        main()
    except Exception:  # pylint: disable=broad-exception-caught
        pass
    sys.exit(0)
