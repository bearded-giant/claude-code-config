---
type: notes
feature: scoped-memory
status: ready
lifecycle: durable
created: 2026-05-25
updated: 2026-05-25
---
<!-- caveman:compressed -->

# scoped-memory — quick overview

Ship summary across 3 phases. Branches `feat/scoped-memory` (giant-tooling) + `scoped-memory` (claude-code-config), both pushed.

## TL;DR

| Layer | Adds |
|---|---|
| Phase 1 | scopes, lifecycle, retention tiers, access log, preload packs |
| Phase 2 | sqlite-vec embeddings (CGO-free), hybrid scoring, `--semantic` opt-in |
| Phase 3 | fsnotify watch daemon, TF-IDF domain suggester, entity promotion |

## New CLI surfaces

```
giantmem scope init|list|show|add-repo|sync
giantmem access top|prune --older-than <dur>
giantmem embed --backfill [--reset] [--scope X] [--repo Y] [--backend stub|python|ollama]
giantmem artifact search <query> [--limit N]      # hybrid scoring
giantmem artifact list --scope X --lifecycle Y    # new filters
giantmem artifact stale --days 0                  # tier-policy mode
giantmem suggest-domain [text]                    # TF-IDF
giantmem entity list|show <path>
giantmem watch start|stop|status|run|install      # fsnotify daemon
```

New MCP tools: `get_stats(scope, repo, feature)`, `find_entity(name, repo)`. `find_artifact` gains `scope`, `lifecycle`, `semantic` args.

New slash command: `/review-memory`.

## Memory model (the big shift)

**Before:** repo-scoped `.giantmem/`. MEMORY.md grows forever. No cross-worktree unit. Hook injects monolithic dump.

**After:** four orthogonal dimensions on every artifact:

| Dim | Where | Values |
|---|---|---|
| `type` | frontmatter | source-spec / delta-spec / proposal / design / tasks / plan / research / review / domain / notes / pattern / facts |
| `lifecycle` | frontmatter (new) | `durable` (default), `candidate` (auto-captured, awaits review), `deprecated` (kept, hidden from packs) |
| `scope` | frontmatter (new, optional) + `~/.giantmem-global/scopes.yaml` | scope id — explicit override OR repo→scope membership |
| `retention tier` | derived from `type` | A=proposal/design/source-spec (never expire), B=pattern/research/notes (180d), C=tasks/plan/review/facts/delta-spec (90d) |

Plus a 5th observability dim: `access_count` (last 30d). Logged on every list/show/find. Powers the `access_boost` term in hybrid scoring.

## Workflow changes

| Old flow | New flow |
|---|---|
| `giantmem artifact list` returns repo only | `giantmem artifact list --scope personal --repo all` returns scope cross-repo |
| Stale = single fixed day cutoff | `stale --days 0` uses per-type retention tier; durable items reported with `durable-stale` annotation |
| Discoveries/research pile up forever | Auto-stamped `lifecycle: candidate`. `/review-memory` walks them: (a)pprove → durable / (r)eject → deprecated / (s)kip / (q)uit |
| Hook injects monolithic WORKSPACE/PLAN/ARTIFACTS dump | Same legacy sections PLUS `=== PRELOAD PACK: <pack>/<layer> ===` blocks from `~/.claude/config/preload_packs.yaml`. Placeholders `{active_scope}` `{active_feature}` `{repo}` `{branch}` resolved at runtime |
| Manual `giantmem artifact reindex` after every edit | `giantmem watch start` runs fsnotify daemon, debounced 2s per workspace |
| FTS-only search | `giantmem artifact search <q>` blends FTS + vec + recency + access (weights env-tunable, sum-to-1.0). Default stays FTS-only — semantic opt-in |
| `/new-feature` scaffolds with type+status frontmatter | Templates now stamp `lifecycle: durable` too. Backfill via `scripts/backfill_lifecycle.py` |
| No cross-repo finder | scope filter + MCP `find_artifact(scope=...)` cross-repo |

## Storage (live.db)

Three new tables:

| Table | Purpose | When written |
|---|---|---|
| `scopes` | mirror of `~/.giantmem-global/scopes.yaml` | `scope sync` / `add-repo` |
| `artifact_access` | (artifact_id, query, rank, accessed_at) | per list/show/find call |
| `artifact_embeddings` (vec0) + `artifact_embedding_meta` | 768-dim vectors + body-hash gating | `giantmem embed --backfill` |

Pure Go via `modernc.org/sqlite/vec` blank import. No CGO.

## Config files

| Path | Owner | Purpose |
|---|---|---|
| `~/.giantmem-global/scopes.yaml` | user (gitignored) | scope registry, cross-repo memberships |
| `~/.claude/config/preload_packs.yaml` | claude-code-config (stowed) | session-start pack layers |
| `~/.cache/giantmem/giantmem-watch.{pid,log}` | runtime | watch daemon state |
| `~/.cache/giantmem/live.db` (or `$GIANTMEM_ARCHIVE_BASE/live.db`) | runtime | scopes + access + embeddings |

## Env knobs

```
GIANTMEM_SCOPES_PATH              # override scopes.yaml location
GIANTMEM_EMBED_BACKEND={stub,python,ollama}
GIANTMEM_EMBED_MODEL              # default BAAI/bge-base-en-v1.5
GIANTMEM_EMBED_DIM                # default 768
GIANTMEM_EMBED_SCRIPT             # path to embed.py
GIANTMEM_HYBRID_FTS_WEIGHT        # default 0.5
GIANTMEM_HYBRID_VEC_WEIGHT        # default 0.25
GIANTMEM_HYBRID_RECENCY_WEIGHT    # default 0.15
GIANTMEM_HYBRID_ACCESS_WEIGHT     # default 0.1 (sum must == 1.0)
OLLAMA_HOST                       # default http://127.0.0.1:11434
```

## Bootstrap on a new machine

```bash
# install latest giantmem
cd ~/dev/giant-tooling/giantmem && make install   # or go build + cp

# seed scope registry
giantmem scope init
giantmem scope add-repo personal dotfiles giant-tooling

# backfill lifecycle on every workspace
python3 ~/dev/giant-tooling/workspace/scripts/backfill_lifecycle.py --all-repos

# enable auto-reindex
giantmem watch start

# (opt-in) real semantic search
GIANTMEM_EMBED_BACKEND=python giantmem embed --backfill --repo all
```

## Where to read more

| Topic | File |
|---|---|
| Narrative + walkthrough | `docs/scoped-memory-guide.md` |
| Cheat sheet | `docs/gma-search.md` §7-9 |
| Phase 1/2/3 details | `docs/usage-summary.md` bottom |
| Backend decision rationale | `.giantmem/features/scoped-memory/research/sqlite_vec_decision.md` |
| Source-of-truth specs | `.giantmem/features/scoped-memory/specs/{scope-registry,lifecycle,context-packs,access-log,embeddings,watch}/spec.md` |
| Proposal + 3-phase plan | `.giantmem/features/scoped-memory/proposal.md` |
| Design + decisions | `.giantmem/features/scoped-memory/design.md` |

## Open / deferred

1. Phase 1 dogfood week — skipped per user call; revisit weights/UX after real use.
2. Auto-promote candidate → durable on N accesses — design open question; not built.
3. Stowing `config/preload_packs.yaml` into `~/.claude/config/` — manual symlink today; future stow run will normalize.
4. python embedder model auto-download UX — sentence-transformers silently downloads; no progress UI.
5. `gma` fzf integration with `--scope` / `--semantic` flags — separate repo, not touched.
