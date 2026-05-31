#!/usr/bin/env python3
"""UserPromptSubmit hook: cross-project recall from giantmem (FTS5).

Replaces the dead RLabs :8765 memory_inject. Queries the local giantmem
index (curated workspace docs across all worktrees) for the user's prompt
and prepends the top few hits. Best-effort: any failure prints nothing so
the prompt is never blocked.
"""

import json
import os
import re
import shutil
import subprocess
import sys

LIMIT = int(os.getenv("GIANTMEM_RECALL_LIMIT", "4"))
SINCE = os.getenv("GIANTMEM_RECALL_SINCE", "180d")
MIN_PROMPT_CHARS = 16
MAX_TERMS = 10

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
    "setup",
    "out",
}


def sanitize(prompt):
    seen, keywords = set(), []
    for token in re.findall(r"[A-Za-z0-9_]+", prompt.lower()):
        if len(token) < 3 or token in STOPWORDS or token in seen:
            continue
        seen.add(token)
        keywords.append(token)
        if len(keywords) >= MAX_TERMS:
            break
    return " OR ".join(keywords)


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

    query = sanitize(prompt)
    if not query:
        return

    try:
        result = subprocess.run(
            [
                giantmem,
                "find",
                query,
                "--live",
                "--json",
                "--no-daemon",
                "--full",
                "--limit",
                str(LIMIT),
                "--since",
                SINCE,
            ],
            capture_output=True,
            text=True,
            timeout=4,
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

    lines = []
    for hit in hits[:LIMIT]:
        project = (hit.get("project") or "").strip("/") or "?"
        path = hit.get("filepath") or hit.get("filename") or "?"
        name = os.path.basename(path)
        dtype = hit.get("dir_type") or hit.get("source_type") or ""
        loc = f"{project}/{dtype}" if dtype else project
        snippet = hit.get("snippet") or hit.get("content") or hit.get("text") or ""
        snippet = re.sub(r"</?([A-Za-z0-9_]+)>", r"\1", snippet)
        snippet = re.sub(r"\s+", " ", snippet).strip()
        suffix = f": {snippet[:180]}" if snippet else ""
        lines.append(f"- [{loc}] {name}{suffix}")

    if not lines:
        return

    print('<giantmem-recall source="workspace, cross-project">')
    print("Possibly-relevant prior context (verify before relying):")
    print("\n".join(lines))
    print("</giantmem-recall>")


if __name__ == "__main__":
    try:
        main()
    except Exception:  # pylint: disable=broad-exception-caught
        pass
    sys.exit(0)
