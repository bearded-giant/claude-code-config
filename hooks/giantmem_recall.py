#!/usr/bin/env python3
"""UserPromptSubmit hook: repo-first recall from giantmem, one cross-project slot.

Two signals, run concurrently and merged:
  - FTS5 bm25 over document bodies (`giantmem find -s memory`: live.db plus the
    archives.db memory docs) — always works, no embedder needed. The lexical
    floor: exact identifiers, tokens, phrases.
  - Semantic hybrid (`giantmem artifact search`) — conceptual recall via the
    daemon's bge embedder. Only real vector hits (vector_score > 0) are kept, so
    a cold daemon degrades cleanly to FTS-only.

Best-effort: any failure prints nothing so the prompt is never blocked.

Quality filters: drop MEMORY.md pointer indexes, drop history session-summary
noise (unless GIANTMEM_RECALL_INCLUDE_HISTORY=1), require each FTS hit to
share >= MIN_OVERLAP distinct keywords with the prompt (terms present in more
than MAX_DF of live_docs are dropped from the query first), prefer hits from the
current repo (path under the worktree, or same canonical project with -wt /
--bare stripped) with at most CROSS_MAX lines from other repos, and collapse
worktree siblings of one doc to a single line.

Output is packed into GIANTMEM_RECALL_BUDGET tokens (ceil(len/4) estimate,
default 600) with GIANTMEM_RECALL_LIMIT lines as a ceiling; the cross-repo slot
reserves its tokens first so current-repo hits cannot crowd it out.

Tunables: GIANTMEM_RECALL_BUDGET, GIANTMEM_RECALL_LIMIT (max lines),
GIANTMEM_RECALL_SNIPPET_CHARS (per-hit passage cap, default 400),
GIANTMEM_RECALL_SINCE, GIANTMEM_RECALL_MIN_OVERLAP, GIANTMEM_RECALL_MAX_DF
(document-frequency ceiling for query terms, default 0.2), GIANTMEM_RECALL_INCLUDE_HISTORY,
GIANTMEM_RECALL_SEMANTIC (0 to disable), GIANTMEM_RECALL_SEMANTIC_MAX,
GIANTMEM_RECALL_CROSS_MAX (other-repo lines, default 1),
GIANTMEM_RECALL_TIMEOUT (per-subprocess wall-clock cap, seconds).
"""

import functools
import importlib.util
import json
import os
import re
import shutil
import signal
import sqlite3
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone

BUDGET = int(os.getenv("GIANTMEM_RECALL_BUDGET", "600"))
LIMIT = int(os.getenv("GIANTMEM_RECALL_LIMIT", "8"))
SNIPPET_CHARS = int(os.getenv("GIANTMEM_RECALL_SNIPPET_CHARS", "400"))
SINCE = os.getenv("GIANTMEM_RECALL_SINCE", "180d")
MIN_OVERLAP = int(os.getenv("GIANTMEM_RECALL_MIN_OVERLAP", "2"))
MAX_DF = float(os.getenv("GIANTMEM_RECALL_MAX_DF", "0.2"))
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
        # over-collect so the document-frequency filter picks the survivors, not position
        if len(out) >= MAX_TERMS * 3:
            break
    return out


def canon(project):
    p = (project or "").strip("/").lower()
    for suffix in ("--bare", "-wt"):
        if p.endswith(suffix):
            p = p[: -len(suffix)]
    return p


@functools.lru_cache(maxsize=1)
def live_index_mod():
    """live_index.py as a module; it owns project detection and the live.db path."""
    spec = importlib.util.spec_from_file_location(
        "live_index",
        os.path.join(os.path.dirname(os.path.abspath(__file__)), "live_index.py"),
    )
    if spec is None or spec.loader is None:
        raise ImportError("live_index.py not found beside giantmem_recall.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def current_repo(data):
    """(canonical project, worktree root with trailing slash) for this session's cwd."""
    cwd = os.getenv("CLAUDE_PROJECT_DIR") or data.get("cwd") or os.getcwd()
    try:
        mod = live_index_mod()
        project, root = mod.detect_project(cwd, mod.ARCHIVE_BASE)
    except Exception:  # pylint: disable=broad-exception-caught
        return "", ""
    return canon(project), root.rstrip("/") + "/"


def rare_terms(keywords, conn=None):
    """Drop prompt terms found in more than MAX_DF of live_docs; they match
    everything and only feed noise into the OR query and the overlap floor.
    Keeps the original list when fewer than two terms survive."""
    if len(keywords) < 3:
        return keywords
    close = False
    try:
        if conn is None:
            conn = sqlite3.connect(
                f"file:{live_index_mod().LIVE_DB}?mode=ro", uri=True, timeout=0.5
            )
            close = True
        try:
            total = conn.execute("SELECT COUNT(*) FROM live_docs").fetchone()[0]
            if not total:
                return keywords
            kept = []
            for idx, k in enumerate(keywords):
                df = conn.execute(
                    "SELECT COUNT(*) FROM live_docs_fts WHERE live_docs_fts MATCH ?",
                    (f'"{k}"',),
                ).fetchone()[0]
                if df / total <= MAX_DF:
                    kept.append((df, idx, k))
        finally:
            if close:
                conn.close()
    except Exception:  # pylint: disable=broad-exception-caught
        return keywords
    if len(kept) < 2:
        return keywords
    # rarest first so a later MAX_TERMS cut keeps the discriminative terms
    kept.sort()
    return [k for _, _, k in kept]


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
    if "/.giantmem/" in path:
        rel = path.split("/.giantmem/", 1)[1]
    elif path.startswith("/"):
        rel = os.path.basename(path)
    else:
        rel = path  # artifact paths are already relative to .giantmem/
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
            # live.db plus archives.db memory docs; live rows win on dedupe
            "-s",
            "memory",
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
        )[:SNIPPET_CHARS]
        if sum(1 for k in keywords if k in snippet.lower()) < required:
            continue
        project = (hit.get("project") or "").strip("/") or "?"
        loc = f"{project}/{dtype}" if dtype else project
        out.append(
            {
                "key": path or name,
                "path": path,
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
        snippet = clean_snippet(r.get("passage") or "")[:SNIPPET_CHARS]
        if not snippet and worktree and rel:
            snippet = artifact_snippet(worktree, rel)
        out.append(
            {
                "key": a.get("id") or rel,
                "path": (
                    os.path.join(worktree, ".giantmem", rel) if worktree and rel else ""
                ),
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
    s = re.sub(r"<!--.*?-->", " ", s, flags=re.DOTALL)
    s = re.sub(r"</?([A-Za-z0-9_]+)>", r"\1", s)
    return re.sub(r"\s+", " ", s).strip()


def artifact_snippet(worktree, rel):
    """Artifact paths are relative to the .giantmem/ dir under the worktree."""
    for path in (os.path.join(worktree, ".giantmem", rel), os.path.join(worktree, rel)):
        snip = body_snippet(path)
        if snip:
            return snip
    return ""


def body_snippet(path, maxlen=SNIPPET_CHARS):
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


def tokens(text):
    return -(-len(text) // 4)


def line_for(hit):
    suffix = f": {hit['snippet']}" if hit["snippet"] else ""
    return f"- [{hit['loc']}] {hit['name']} ({hit['tag']}){suffix}"


def pick(semantic, fts):
    """Current repo first (semantic before FTS within it), then at most CROSS_MAX
    hits from other repos, packed into BUDGET tokens with LIMIT lines as a
    ceiling. The cross slot's tokens are reserved before current-repo hits fill
    the budget. Dedup by key and by worktree-sibling key; an oversized hit is
    skipped, not fatal. Returns the chosen hits in output order."""
    ranked = [*semantic, *fts]
    cur = [h for h in ranked if h["cur"]]
    other = [h for h in ranked if not h["cur"]]
    seen_key, seen_sib, picked = set(), set(), []
    used = 0

    def fresh(hit):
        return hit["key"] not in seen_key and hit["sib"] not in seen_sib

    def take(hit, budget):
        nonlocal used
        cost = tokens(line_for(hit))
        if used + cost > budget:
            return False
        seen_key.add(hit["key"])
        seen_sib.add(hit["sib"])
        picked.append(hit)
        used += cost
        return True

    cross = other[:CROSS_MAX]
    reserve = sum(tokens(line_for(h)) for h in cross)
    line_cap = LIMIT - len(cross)
    for hit in cur:
        if len(picked) >= line_cap:
            break
        if fresh(hit):
            take(hit, BUDGET - reserve)
    taken_other = 0
    for hit in other:
        if taken_other >= CROSS_MAX or len(picked) >= LIMIT:
            break
        if fresh(hit) and take(hit, BUDGET):
            taken_other += 1
    return picked


def merge(semantic, fts):
    return [line_for(h) for h in pick(semantic, fts)]


def log_recall(data, repo, hits):
    """Append one recall_log row per injected line so `giantmem recall report`
    can measure whether recalled docs were then read or edited in the session.
    Schema is owned by the Go migrations; fail silent."""
    if not hits:
        return
    try:
        mod = live_index_mod()
        session_id = data.get("session_id") or mod.session_id_from_env(data) or ""
        ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        conn = sqlite3.connect(str(mod.LIVE_DB), timeout=0.5)
        try:
            conn.executemany(
                "INSERT INTO recall_log(ts, session_id, repo, rank, tag, cur, key, path)"
                " VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                [
                    (
                        ts,
                        session_id,
                        repo[0],
                        i + 1,
                        h["tag"],
                        int(bool(h["cur"])),
                        h["key"],
                        h.get("path", ""),
                    )
                    for i, h in enumerate(hits)
                ],
            )
            conn.commit()
        finally:
            conn.close()
    except Exception:  # pylint: disable=broad-exception-caught
        pass


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

    keywords = rare_terms(keywords_from(prompt))[:MAX_TERMS]
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

    hits = pick(semantic, fts)
    if not hits:
        return

    print(f'<giantmem-recall source="giantmem, repo-first" repo="{repo[0] or "?"}">')
    print("Possibly-relevant prior context (verify before relying):")
    print("\n".join(line_for(h) for h in hits))
    print("</giantmem-recall>")
    log_recall(data, repo, hits)


if __name__ == "__main__":
    try:
        main()
    except Exception:  # pylint: disable=broad-exception-caught
        pass
    sys.exit(0)
