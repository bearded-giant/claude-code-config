# Artifact + spec workflow

What shipped from the OpenSpec-hybrid migration + scoped-memory. Daily-driver reference.

## Mental model

Three-spec split per feature → repo-truth:

| Artifact | Path | Holds |
|---|---|---|
| proposal | `features/{name}/proposal.md` | Intent + scope + approach. NOT behavior. |
| delta-spec | `features/{name}/specs/{domain}/spec.md` | `## ADDED / MODIFIED / REMOVED Requirements`. Each `### Requirement:` has `#### Scenario:` GIVEN/WHEN/THEN (RFC 2119). |
| source-spec | `.giantmem/specs/{domain}/spec.md` | Accumulated behavior across all completed features. Only `/complete-feature` writes. Never hand-edit. |

Legacy `features/{name}/spec.md` is a 30-day symlink → `proposal.md`.

Every `.md`/`.yaml` has YAML frontmatter (`type`, `status`, `feature` or `repo`, `lifecycle`, ...). JSON same keys top-level. That's what makes the typed query layer (`giantmem artifact`, MCP `find_artifact`, fzf `gma`) work.

## Before / after (8 common tasks)

| Task | Before | After |
|---|---|---|
| New feature | `/new-feature foo` → scaffolds `spec.md` | scaffolds `proposal.md` + empty `specs/` + `tasks.md` + `facts.md` (all w/ frontmatter + `lifecycle: durable`) |
| Capture behavior change | hand-edit a section | write delta-spec in `features/foo/specs/{domain}/spec.md` w/ ADDED/MODIFIED/REMOVED |
| Complete feature | `/complete-feature foo` flips status | merges delta-specs → source-of-truth, writes both histories, reindexes |
| Find all proposals across repos | scan dirs manually | `giantmem artifact list --repo all -t proposal` |
| Find one feature's domains | grep | `giantmem artifact list -f foo -t delta-spec` |
| Find stale work | nothing | `giantmem artifact stale --days 0` (tier policy) |
| QA validate feature | manual | `/feature-validate foo --fix` |
| Cross-repo memory unit | none | `giantmem artifact list --scope X` |

## Commands

See [feature-commands.md](feature-commands.md) for full lifecycle (new/start/pause/reopen/complete + validate/next/report/facts/review-memory).

See [gma-search.md](gma-search.md) for query + content search (`giantmem artifact`, `giantmem find`, `gma`, semantic).

## Daily-driver cheat sheet

```bash
giantmem artifact list -t delta-spec -s ready          # work in flight
giantmem artifact list --repo all -t proposal          # what's been proposed
giantmem artifact stale --days 0                       # what's gone cold (tier policy)
giantmem artifact show <id>                            # one artifact

giantmem find "rate limiting"                          # content FTS
giantmem artifact search "rate limiting"               # semantic (after embed)

gma                                                    # interactive picker
gma --scope personal --lifecycle candidate

/new-feature <name>                                    # scaffold
/complete-feature <name>                               # merge deltas into source
/review-memory                                         # walk candidates
```

## Scope + lifecycle (phase 1)

Scope = named bundle of repos at `~/.giantmem-global/scopes.yaml`. Membership = repo match unless artifact frontmatter sets `scope:` explicitly.

```bash
giantmem scope init
giantmem scope add-repo personal dotfiles giant-tooling
giantmem artifact list --scope personal -t delta-spec
```

Lifecycle stages: `durable` (default), `candidate` (awaits `/review-memory`), `deprecated` (excluded from packs).

Retention tier derived from `type:` — A=never expire, B=180d candidate cutoff, C=90d. `stale --days 0` uses tier policy.

Access log: `live.db.artifact_access` rows `(artifact_id, query, rank, accessed_at)` per list/show/find. `giantmem access top` / `prune`. `access_count` enriched on `--json` output + MCP `find_artifact` results.

Preload packs: `~/.claude/config/preload_packs.yaml` declares ordered layers for `workspace_session_hook.py`. Layers inline `static_files`, run filtered `artifact list`, resolve `{active_scope}` / `{active_feature}` / `{repo}` / `{branch}`. Additive to existing hook sections in phase 1.

## Hybrid search (phase 2)

CGO-free via `modernc.org/sqlite/vec` blank import. live.db v4 adds vec0 `artifact_embeddings` + `artifact_embedding_meta` (body-hash gated).

Backends: `stub` (none, default — NOT semantic), `python` (sentence-transformers, `BAAI/bge-base-en-v1.5`), `ollama` (HTTP).

```bash
giantmem embed --backfill                              # stub, deterministic
GIANTMEM_EMBED_BACKEND=python giantmem embed --backfill
giantmem artifact search "scope registry yaml" --limit 5
```

Weights env-tunable, sum-to-1.0: `GIANTMEM_HYBRID_{FTS,VEC,RECENCY,ACCESS}_WEIGHT`. MCP `find_artifact(semantic=true)` routes through same scorer.

## Watch + suggest + entity (phase 3)

```bash
giantmem watch start                                   # fsnotify auto-reindex, 2s debounce
giantmem watch install                                 # macOS launchd
giantmem suggest-domain "JWT session refresh"          # TF-IDF over source-spec corpus
giantmem entity list                                   # cross-repo file entities
giantmem entity show src/state.rs                      # one entity + back-refs
```

## Conventions + invariants

| Rule | Why |
|---|---|
| Source-spec only via `/complete-feature` | Audit trail of when a behavior landed |
| `--include-archived` for stale snapshots | `gma` default excludes them |
| Feature names != branch names | Decoupled in `meta.json`/`facts.md` |
| Branch surfaces on `Artifact` JSON | `--branch` filter on multi-worktree features |
| `--feature`/`-f` is a positional partial-match | Works without exact spelling |
| `Index` keyed on `(repo, branch, feature)` | Separate entries for same feature in different branches |
| Loose `/complete-feature` | empty specs = silent skip; `--no-merge` to skip even when present |
| Both histories | per-feature `spec_history.md` AND repo `.giantmem/specs/_history.md` |

## Deferred / NOT done

1. Plugin-v2 artifact taxonomy via `~/.config/giantmem/artifact_types.toml`
2. Paired-feature view — `--paired` joins cwt ↔ fewt branches sharing a feature name
3. Full SQL `artifacts` table in `archives.db` with FTS join
4. Adversarial test for `/feature-validate --fix` byte-identity guarantee

## Where to read more

| Topic | File |
|---|---|
| Feature lifecycle commands | [feature-commands.md](feature-commands.md) |
| Search cheat sheet | [gma-search.md](gma-search.md) |
| Session transcript search | [session-search-guide.md](session-search-guide.md) |
| Scoped memory model | [scoped-memory-overview.md](scoped-memory-overview.md) |
| Output rules | `~/.claude/skills/workspace-rules/SKILL.md` |
| Feature folder rules | `~/.claude/skills/feature-management/SKILL.md` |
| Mental model + invariants | `~/.claude/CLAUDE.md` "Three-Spec Model" + "Scope + Lifecycle" + "Finding artifacts" |
