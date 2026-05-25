# Scoped memory

Cross-worktree memory unit + lifecycle aging + hybrid search. Shipped across 3 phases.

| Phase | Adds |
|---|---|
| 1 | scopes, lifecycle, retention tiers, access log, preload packs, `/review-memory` |
| 2 | sqlite-vec embeddings (CGO-free), hybrid scoring, `--semantic` opt-in |
| 3 | fsnotify watch daemon, TF-IDF domain suggester, entity promotion |

## Memory model

Four dimensions on every artifact:

| Dim | Where | Values |
|---|---|---|
| `type` | frontmatter | source-spec / delta-spec / proposal / design / tasks / plan / research / review / domain / notes / pattern / facts |
| `lifecycle` | frontmatter | `durable` (default), `candidate` (auto-captured), `deprecated` |
| `scope` | frontmatter (optional) + `~/.giantmem-global/scopes.yaml` | scope id; explicit OR repo→scope membership |
| retention tier | derived from `type` | A=proposal/design/source-spec (never), B=pattern/research/notes (180d), C=tasks/plan/review/facts/delta-spec (90d) |

Plus `access_count` (last 30d) — observability + ranking signal. Logged on every list/show/find.

## New CLI

```
giantmem scope init|list|show|add-repo|sync

giantmem artifact list --scope X --lifecycle Y
giantmem artifact stale --days 0          # tier policy mode
giantmem artifact search <q>              # hybrid: FTS + vec + recency + access

giantmem embed --backfill [--reset] [--scope X] [--repo Y] [--backend stub|python|ollama]
giantmem access top|prune --older-than 180d
giantmem suggest-domain [text]            # TF-IDF; reads stdin
giantmem entity list|show <path-or-name>
giantmem watch start|stop|status|run|install
```

New MCP tools: `get_stats`, `find_entity`. `find_artifact` gains `scope`/`lifecycle`/`semantic` args.

New slash: `/review-memory`.

## Workflow changes

| Old | New |
|---|---|
| repo-scoped list | `--scope X --repo all` cross-repo |
| stale = fixed cutoff | `stale --days 0` = per-type retention tier |
| Discoveries pile up forever | Stamped `lifecycle: candidate`. `/review-memory` walks: approve/reject/skip/quit |
| Hook: monolithic dump | Hook: legacy sections + `=== PRELOAD PACK ===` from `~/.claude/config/preload_packs.yaml` |
| Manual reindex per edit | `giantmem watch start` — fsnotify, 2s debounce |
| FTS-only | `artifact search <q>` blends FTS+vec+recency+access (opt-in) |

## Storage (live.db)

| Table | Purpose |
|---|---|
| `scopes` | mirror of `~/.giantmem-global/scopes.yaml` |
| `artifact_access` | `(artifact_id, query, rank, accessed_at)` per list/show/find |
| `artifact_embeddings` (vec0) + `artifact_embedding_meta` | 768-dim vectors + body-hash gating |

Pure Go via `modernc.org/sqlite/vec` blank import. No CGO.

## Config files

| Path | Purpose |
|---|---|
| `~/.giantmem-global/scopes.yaml` | scope registry (user, gitignored) |
| `~/.claude/config/preload_packs.yaml` | session-start pack layers |
| `~/.cache/giantmem/giantmem-watch.{pid,log}` | watcher runtime |
| `~/.cache/giantmem/live.db` (or `$GIANTMEM_ARCHIVE_BASE/live.db`) | scopes + access + embeddings |

## Env knobs

```
GIANTMEM_SCOPES_PATH                       # override scopes.yaml location
GIANTMEM_EMBED_BACKEND={stub,python,ollama}
GIANTMEM_EMBED_MODEL                       # default BAAI/bge-base-en-v1.5
GIANTMEM_EMBED_DIM                         # default 768
GIANTMEM_EMBED_SCRIPT                      # path to embed.py
GIANTMEM_HYBRID_FTS_WEIGHT                 # default 0.5
GIANTMEM_HYBRID_VEC_WEIGHT                 # default 0.25
GIANTMEM_HYBRID_RECENCY_WEIGHT             # default 0.15
GIANTMEM_HYBRID_ACCESS_WEIGHT              # default 0.1 (sum == 1.0)
GIANTMEM_DEV_ROOTS                         # watcher + cross-repo crawl roots
OLLAMA_HOST                                # default http://127.0.0.1:11434
```

## Bootstrap

```bash
cd ~/dev/giant-tooling/giantmem && make install

giantmem scope init                                                # seed registry
giantmem scope add-repo personal dotfiles giant-tooling            # extend
python3 ~/dev/giant-tooling/workspace/scripts/backfill_lifecycle.py --all-repos
giantmem watch start                                               # auto-reindex
GIANTMEM_EMBED_BACKEND=python giantmem embed --backfill --repo all # real semantic (opt-in)
```

## Embedder backends

| Backend | Dep | Use when |
|---|---|---|
| `stub` (default) | none | Testing the pipeline. Deterministic hash vectors. NOT semantic. |
| `python` | `python3` + `sentence-transformers` | Real semantic ranking. Long-running subprocess. |
| `ollama` | Ollama on `OLLAMA_HOST` | Already running Ollama. HTTP per call. |

Embedder daemon: `workspace/scripts/embed.py` (sentence-transformers, default `BAAI/bge-base-en-v1.5`). Cold-start ~3s, warm calls fast. Body-hash gating → idempotent backfill.

## Lifecycle stages

| Stage | Used for | Behavior |
|---|---|---|
| `durable` | `/new-feature` scaffolds, source-specs after merge | never auto-prunes, in default packs |
| `candidate` | AI-captured research / discoveries / mid-session notes | `/review-memory` promotes → durable / demotes → deprecated |
| `deprecated` | Rejected. Kept on disk. | excluded from default packs + stale reports |

## Where to read more

| Topic | File |
|---|---|
| Search CLI cheat sheet | `gma-search.md` |
| Full artifact workflow | `usage-summary.md` |
| Feature commands | `feature-commands.md` |
| Backend decision rationale | `.giantmem/features/scoped-memory/research/sqlite_vec_decision.md` |
| Source-of-truth specs | `.giantmem/features/scoped-memory/specs/*/spec.md` |
