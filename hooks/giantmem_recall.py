#!/usr/bin/env python3
"""UserPromptSubmit hook: cross-project recall from giantmem.

Two signals, run concurrently and merged:
  - FTS5 bm25 over document bodies (`giantmem find --live`) — always works, no
    embedder needed. The lexical floor: exact identifiers, tokens, phrases.
  - Semantic hybrid (`giantmem artifact search`) — conceptual recall via the
    daemon's bge embedder. Only real vector hits (vector_score > 0) are kept, so
    a cold daemon degrades cleanly to FTS-only.

Best-effort: any failure prints nothing so the prompt is never blocked.

Quality filters: drop MEMORY.md pointer indexes, drop history session-summary
noise (unless GIANTMEM_RECALL_INCLUDE_HISTORY=1), and require each FTS hit to
share >= MIN_OVERLAP distinct keywords with the prompt.

Tunables: GIANTMEM_RECALL_LIMIT, GIANTMEM_RECALL_SINCE,
GIANTMEM_RECALL_MIN_OVERLAP, GIANTMEM_RECALL_INCLUDE_HISTORY,
GIANTMEM_RECALL_SEMANTIC (0 to disable), GIANTMEM_RECALL_SEMANTIC_MAX,
GIANTMEM_RECALL_TIMEOUT (per-subprocess wall-clock cap, seconds).
"""

import json
import os
import re
import shutil
import signal
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor

LIMIT = int(os.getenv("GIANTMEM_RECALL_LIMIT", "4"))
SINCE = os.getenv("GIANTMEM_RECALL_SINCE", "180d")
MIN_OVERLAP = int(os.getenv("GIANTMEM_RECALL_MIN_OVERLAP", "2"))
INCLUDE_HISTORY = os.getenv("GIANTMEM_RECALL_INCLUDE_HISTORY") == "1"
SEMANTIC = os.getenv("GIANTMEM_RECALL_SEMANTIC", "1") != "0"
SEMANTIC_MAX = int(os.getenv("GIANTMEM_RECALL_SEMANTIC_MAX", str(max(1, LIMIT // 2))))
TIMEOUT = float(os.getenv("GIANTMEM_RECALL_TIMEOUT", "2"))
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


def run_giantmem(giantmem, argv, timeout=TIMEOUT):
    try:
        with subprocess.Popen(
            [giantmem, *argv],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            start_new_session=True,
        ) as proc:
            try:
                out = proc.communicate(timeout=timeout)[0]
            except subprocess.TimeoutExpired:
                # killing the child alone can leave the wait blocked on a
                # grandchild holding the stdout pipe, so take out the group
                try:
                    os.killpg(proc.pid, signal.SIGKILL)
                except OSError:
                    pass
                return None
    except OSError:
        return None
    try:
        return json.loads(out) if out.strip() else None
    except json.JSONDecodeError:
        return None


def fts_hits(giantmem, keywords):
    """Existing FTS path: OR-query, keyword-overlap filtered. Returns hit dicts."""
    query = " OR ".join(keywords)
    hits = run_giantmem(
        giantmem,
        [
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
    )
    hits = hits if isinstance(hits, list) else []
    required = min(MIN_OVERLAP, len(keywords))
    out = []
    for hit in hits:
        path = hit.get("filepath") or hit.get("filename") or ""
        name = os.path.basename(path)
        if name in EXCLUDE_NAMES:
            continue
        dtype = hit.get("dir_type") or hit.get("source_type") or ""
        if dtype in EXCLUDE_DIR_TYPES:
            continue
        snippet = clean_snippet(
            hit.get("snippet") or hit.get("content") or hit.get("text") or ""
        )
        if sum(1 for k in keywords if k in snippet.lower()) < required:
            continue
        project = (hit.get("project") or "").strip("/") or "?"
        loc = f"{project}/{dtype}" if dtype else project
        out.append(
            {
                "key": path or name,
                "loc": loc,
                "name": name,
                "snippet": snippet,
                "tag": "fts",
            }
        )
    return out


def semantic_hits(giantmem, prompt):
    """Hybrid semantic search over the artifacts projection. Keeps only real
    vector matches (vector_score > 0) so a cold daemon yields nothing here."""
    data = run_giantmem(
        giantmem,
        [
            "artifact",
            "search",
            prompt,
            "--repo",
            "all",
            "--json",
            "--limit",
            str(SEMANTIC_MAX * 3),
        ],
    )
    if not isinstance(data, dict):
        return []
    out = []
    for r in data.get("results", []):
        if float(r.get("vector_score") or 0) <= 0:
            continue
        a = r.get("artifact") or {}
        atype = a.get("type") or ""
        if not INCLUDE_HISTORY and atype == "history":
            continue
        rel, worktree = a.get("path") or "", a.get("worktree") or ""
        name = os.path.basename(rel) or a.get("id", "")
        if name in EXCLUDE_NAMES:
            continue
        repo = a.get("repo") or "?"
        loc = f"{repo}/{atype}" if atype else repo
        snippet = artifact_snippet(worktree, rel) if worktree and rel else ""
        out.append(
            {
                "key": a.get("id") or rel,
                "loc": loc,
                "name": name,
                "snippet": snippet,
                "tag": "sem",
            }
        )
        if len(out) >= SEMANTIC_MAX:
            break
    return out


def clean_snippet(s):
    s = re.sub(r"</?([A-Za-z0-9_]+)>", r"\1", s)
    return re.sub(r"\s+", " ", s).strip()


def artifact_snippet(worktree, rel):
    """Artifact paths are relative to the .giantmem/ dir under the worktree."""
    for path in (os.path.join(worktree, ".giantmem", rel), os.path.join(worktree, rel)):
        snip = body_snippet(path)
        if snip:
            return snip
    return ""


def body_snippet(path, maxlen=180):
    """First prose past YAML frontmatter — semantic hits carry no FTS snippet."""
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            text = f.read(4096)
    except OSError:
        return ""
    if text.startswith("---"):
        end = text.find("\n---", 3)
        if end != -1:
            text = text[end + 4 :]
    text = re.sub(r"<!--.*?-->", " ", text, flags=re.DOTALL)
    text = clean_snippet(text)
    return text[:maxlen]


def merge(semantic, fts):
    """Semantic first (guaranteed slots), fill remainder with FTS, dedup by key."""
    seen, lines = set(), []
    for hit in [*semantic, *fts]:
        key = hit["key"]
        if key in seen:
            continue
        seen.add(key)
        suffix = f": {hit['snippet']}" if hit["snippet"] else ""
        lines.append(f"- [{hit['loc']}] {hit['name']} ({hit['tag']}){suffix}")
        if len(lines) >= LIMIT:
            break
    return lines


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

    with ThreadPoolExecutor(max_workers=2) as pool:
        fts_future = pool.submit(fts_hits, giantmem, keywords)
        sem_future = pool.submit(semantic_hits, giantmem, prompt) if SEMANTIC else None
        fts = fts_future.result()
        semantic = sem_future.result() if sem_future else []

    lines = merge(semantic, fts)
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
