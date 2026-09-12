#!/usr/bin/env python3
"""UserPromptSubmit hook: repo-first recall from giantmem, one cross-project slot.

Two signals, run concurrently and merged:
  - FTS5 bm25 over document bodies (`giantmem find --live`) — always works, no
    embedder needed. The lexical floor: exact identifiers, tokens, phrases.
  - Semantic hybrid (`giantmem artifact search`) — conceptual recall via the
    daemon's bge embedder. Only real vector hits (vector_score > 0) are kept, so
    a cold daemon degrades cleanly to FTS-only.

Best-effort: any failure prints nothing so the prompt is never blocked.

Quality filters: drop MEMORY.md pointer indexes, drop history session-summary
noise (unless GIANTMEM_RECALL_INCLUDE_HISTORY=1), require each FTS hit to
share >= MIN_OVERLAP distinct keywords with the prompt, prefer hits from the
current repo (path under the worktree, or same canonical project with -wt /
--bare stripped) with at most CROSS_MAX lines from other repos, and collapse
worktree siblings of one doc to a single line.

Tunables: GIANTMEM_RECALL_LIMIT, GIANTMEM_RECALL_SINCE,
GIANTMEM_RECALL_MIN_OVERLAP, GIANTMEM_RECALL_INCLUDE_HISTORY,
GIANTMEM_RECALL_SEMANTIC (0 to disable), GIANTMEM_RECALL_SEMANTIC_MAX,
GIANTMEM_RECALL_CROSS_MAX (other-repo lines, default 1),
GIANTMEM_RECALL_TIMEOUT (per-subprocess wall-clock cap, seconds).
"""

import importlib.util
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
CROSS_MAX = int(os.getenv("GIANTMEM_RECALL_CROSS_MAX", "1"))
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


def canon(project):
    p = (project or "").strip("/").lower()
    for suffix in ("--bare", "-wt"):
        if p.endswith(suffix):
            p = p[: -len(suffix)]
    return p


def current_repo(data):
    """(canonical project, worktree root with trailing slash) for this session's cwd."""
    cwd = os.getenv("CLAUDE_PROJECT_DIR") or data.get("cwd") or os.getcwd()
    try:
        spec = importlib.util.spec_from_file_location(
            "live_index",
            os.path.join(os.path.dirname(os.path.abspath(__file__)), "live_index.py"),
        )
        if spec is None or spec.loader is None:
            return "", ""
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        project, root = mod.detect_project(cwd, mod.ARCHIVE_BASE)
    except Exception:  # pylint: disable=broad-exception-caught
        return "", ""
    return canon(project), root.rstrip("/") + "/"


def is_current(repo, project, path="", worktree=""):
    cur, root = repo
    if not cur:
        return True
    if root and path.startswith(root):
        return True
    if root and worktree and (worktree.rstrip("/") + "/").startswith(root):
        return True
    c = canon(project)
    return c == cur or c.endswith("-" + cur)


def sibling_key(project, path):
    """Same doc across worktree siblings shares (canonical project, path under .giantmem/)."""
    rel = (
        path.split("/.giantmem/", 1)[1]
        if "/.giantmem/" in path
        else os.path.basename(path)
    )
    return (canon(project), rel)


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


def fts_hits(giantmem, keywords, repo):
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
            str(LIMIT * 8),
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
                "sib": sibling_key(project, path),
                "cur": is_current(repo, project, path=path),
                "loc": loc,
                "name": name,
                "snippet": snippet,
                "tag": "fts",
            }
        )
    return out


def semantic_hits(giantmem, prompt, repo):
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
        arepo = a.get("repo") or "?"
        loc = f"{arepo}/{atype}" if atype else arepo
        snippet = artifact_snippet(worktree, rel) if worktree and rel else ""
        out.append(
            {
                "key": a.get("id") or rel,
                "sib": sibling_key(arepo, rel),
                "cur": is_current(repo, arepo, worktree=worktree),
                "loc": loc,
                "name": name,
                "snippet": snippet,
                "tag": "sem",
            }
        )
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
    """Current repo first (semantic before FTS within it), then at most CROSS_MAX
    lines from other repos. Dedup by key and by worktree-sibling key."""
    ranked = [*semantic, *fts]
    cur = [h for h in ranked if h["cur"]]
    other = [h for h in ranked if not h["cur"]]
    seen_key, seen_sib, lines = set(), set(), []

    def take(hit):
        if hit["key"] in seen_key or hit["sib"] in seen_sib:
            return False
        seen_key.add(hit["key"])
        seen_sib.add(hit["sib"])
        suffix = f": {hit['snippet']}" if hit["snippet"] else ""
        lines.append(f"- [{hit['loc']}] {hit['name']} ({hit['tag']}){suffix}")
        return True

    cur_cap = LIMIT - min(CROSS_MAX, len(other))
    for hit in cur:
        if len(lines) >= cur_cap:
            break
        take(hit)
    taken_other = 0
    for hit in other:
        if taken_other >= CROSS_MAX or len(lines) >= LIMIT:
            break
        if take(hit):
            taken_other += 1
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

    repo = current_repo(data)
    with ThreadPoolExecutor(max_workers=2) as pool:
        fts_future = pool.submit(fts_hits, giantmem, keywords, repo)
        sem_future = (
            pool.submit(semantic_hits, giantmem, prompt, repo) if SEMANTIC else None
        )
        fts = fts_future.result()
        semantic = sem_future.result() if sem_future else []

    lines = merge(semantic, fts)
    if not lines:
        return

    print(f'<giantmem-recall source="giantmem, repo-first" repo="{repo[0] or "?"}">')
    print("Possibly-relevant prior context (verify before relying):")
    print("\n".join(lines))
    print("</giantmem-recall>")


if __name__ == "__main__":
    try:
        main()
    except Exception:  # pylint: disable=broad-exception-caught
        pass
    sys.exit(0)
