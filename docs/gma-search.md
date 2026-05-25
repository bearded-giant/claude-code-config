# Artifact + content search

Find typed artifacts (proposal/delta-spec/tasks/plan/research/...) OR keyword content. Two engines:

| Engine | Indexes | Use for |
|---|---|---|
| `giantmem artifact ...` | `artifacts.json` per workspace | typed query by frontmatter — type, status, feature, domain, repo, branch, scope, lifecycle |
| `giantmem find ...` | `live.db` + `archives.db` (FTS5) | full content match across .giantmem markdown + Claude session JSONL |

`gma` = fzf wrapper over `giantmem artifact list`.

## When in doubt

| Question | Reach for |
|---|---|
| Know the type/status/feature | `giantmem artifact list` |
| Just remember a phrase | `giantmem find "..."` |
| Click through options | `gma` |
| Inside Claude | MCP `find_artifact` |
| Recent activity | `--since 7d` on `find`, or jq date filter on `artifact list` |
| Old / forgotten | `giantmem artifact stale [--days 0]` |
| Missing frontmatter | `giantmem artifact orphans` |
| Cross-repo by scope | `--scope <id>` on `artifact list` or MCP `find_artifact(scope=)` |
| Pending review candidates | `--lifecycle candidate` or `/review-memory` |
| Most-touched artifacts | `giantmem access top` |
| Counts dashboard | MCP `get_stats(scope=, repo=, feature=)` |
| Semantic search | `giantmem artifact search <q>` or MCP `find_artifact(semantic=true)` |

## Typed query — `giantmem artifact`

```bash
giantmem artifact list                               # current workspace
giantmem artifact list -t delta-spec -s ready
giantmem artifact list --repo all -t proposal
giantmem artifact list --feature scoped-memory
giantmem artifact list --domain auth
giantmem artifact list --include-archived            # with --repo all
giantmem artifact list --json | jq '.artifacts[] | select(.size > 5000)'
giantmem artifact list --paths                       # absolute paths only

giantmem artifact show <id>                          # frontmatter + body
giantmem artifact reindex                            # rebuild artifacts.json
giantmem artifact orphans                            # files missing frontmatter
giantmem artifact stale --days 30                    # fixed cutoff
giantmem artifact stale --days 0                     # tier policy: A=never, B=180d, C=90d
```

### Scope + lifecycle filters

```bash
giantmem scope init                                  # one-time seed
giantmem scope add-repo personal dotfiles giant-tooling

giantmem artifact list --scope personal -t delta-spec
giantmem artifact list --repo all --scope personal --lifecycle durable
giantmem artifact list --lifecycle candidate         # awaiting /review-memory
giantmem artifact list --lifecycle durable,deprecated
```

Scope membership = repo match OR explicit `scope:` frontmatter override.

### Access log

```bash
giantmem access top --limit 10                       # top by 30d count
giantmem access prune --older-than 180d              # trim
giantmem access prune --older-than 30d --dry-run     # row count only
```

`artifact list --json` carries `access_count` (30d) + `lifecycle` per row.

## Content search — `giantmem find`

```bash
giantmem find "jwt refresh"
giantmem find "jwt refresh" --live                   # current .giantmem only
giantmem find "jwt refresh" --archive                # archives.db only
giantmem find "jwt refresh" -s session               # transcripts only
giantmem find "jwt refresh" -p cc-wt                 # project
giantmem find "jwt refresh" --since 7d --until 1d
giantmem find "jwt refresh" --tool Write,Edit        # only lines where Claude used these tools
giantmem find "jwt refresh" --ext md,go              # only matches touching these files
giantmem find "jwt refresh" --no-interactive        # no fzf
giantmem find "jwt refresh" --paths                  # path-only output
giantmem find "jwt refresh" --full                   # snippet inline
giantmem find "jwt refresh" -n 5
```

FTS5 syntax: `term1 term2` (AND), `"phrase"`, `t1 OR t2`, `t1 NOT t2`, `prefix*`. Punctuation auto-quoted by CLI.

## Semantic search

Opt-in. Requires `giantmem embed --backfill` first.

```bash
giantmem embed --backfill --backend stub             # one-time, fast, NOT semantic
GIANTMEM_EMBED_BACKEND=python giantmem embed --backfill --repo all

giantmem artifact search "scope yaml registry" -t proposal --limit 5
giantmem artifact search "lifecycle" --json
```

Default behavior unchanged — `giantmem find` and `artifact list` stay FTS-only. Semantic is opt-in.

Backends: `stub` (none, default), `python` (sentence-transformers), `ollama` (HTTP).

Weights sum-to-1.0:

```
GIANTMEM_HYBRID_FTS_WEIGHT=0.5
GIANTMEM_HYBRID_VEC_WEIGHT=0.25
GIANTMEM_HYBRID_RECENCY_WEIGHT=0.15
GIANTMEM_HYBRID_ACCESS_WEIGHT=0.1
```

## fzf — `gma`

```bash
gma                                                  # all repos
gma --scope personal -t delta-spec
gma --lifecycle candidate
```

Pipes selection into `$EDITOR` or prints `path:line`.

## MCP tools

| Tool | Purpose |
|---|---|
| `find_artifact` | Typed lookup. Args: type, status, feature, domain, repo, branch, scope, lifecycle, query, semantic, limit |
| `get_artifact` | Full body + frontmatter by id |
| `list_features_with_artifacts` | Group by feature, one or all repos |
| `get_stats` | Counts by type/lifecycle/status/repo + recent_writes_24h + recent_accesses_24h + top_accessed |
| `find_entity` | Domain key_file lookup + back-references |
| `search_archive` | Content FTS over archives.db (sessions + workspace + domain) |
| `recent_writes` | Recent file activity |
| `feature_status` | Per-feature state |
| `workspace_tree` | Workspace layout |

## See also

- [scoped-memory-overview.md](scoped-memory-overview.md) — memory model + scope/lifecycle/hybrid mechanics
- [session-search-guide.md](session-search-guide.md) — Claude session transcripts (separate corpus)
- [usage-summary.md](usage-summary.md) — full workflow
