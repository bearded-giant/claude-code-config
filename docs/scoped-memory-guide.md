# Scoped memory guide

A narrative walk through the new memory pieces shipped in scoped-memory phase 1: scopes, lifecycle, retention tiers, the access log, and preload packs. Read this if the cheat sheet feels too dense.

## What changed and why

The artifact stack already gave us typed, frontmatter-tagged knowledge per repo. Three things were missing.

First, there was no cross-worktree memory unit. Everything indexed inside a single repo's `.giantmem/`. Preferences that span repos, paired-repo facts, and recurring patterns kept piling into `~/.claude/CLAUDE.md` because nowhere else was global. Scopes fix that — a scope is a named bundle of repos, defined once at `~/.giantmem-global/scopes.yaml`, and any artifact in any member repo can be filtered as part of the scope. An artifact can also override membership with an explicit `scope:` frontmatter field.

Second, FTS lookups happened at session-start (one shot) or via explicit shell calls. Claude rarely asked "have we seen this before" mid-session because there was nothing pushing it to. Preload packs replace the monolithic session-start dump with ordered layers, each driven by a query template against the artifact index. Phase 1 ships static-file + filter layers; phase 2 will add hybrid scoring with embeddings.

Third, `MEMORY.md` and discoveries kept growing. There was no distinction between "I trust this" and "this was auto-captured". Lifecycle adds three stages — `durable` (the trusted default), `candidate` (awaiting human review), and `deprecated` (kept on disk but excluded from packs). Retention tier is then derived from artifact type, so a proposal never auto-expires while a stale candidate task can fall off the radar.

## The five pieces

### Scope registry

The file lives at `~/.giantmem-global/scopes.yaml` (path is overridable via `GIANTMEM_SCOPES_PATH`). It's owned by the user, gitignored at every layer, and not part of any stow target.

Format:

```yaml
version: 1
scopes:
  personal:
    description: dotfiles + claude-code-config tooling
    tags: [tooling, config]
    repos: [claude-code-config, dotfiles, giant-tooling]
  recharge-customcheckout:
    description: customcheckout work across BE + FE pair
    tags: [customcheckout, frontend, paired]
    repos: [customcheckout, frontend, claude-code-config]
```

A `live.db.scopes` table mirrors the YAML. The YAML is always source of truth; the SQLite cache is rebuilt on `giantmem scope sync` (or implicitly the next time the registry is read after a `scope add-repo`).

### Lifecycle

`lifecycle:` is a per-artifact frontmatter field. Three legal values:

| Stage | Meaning | Set by |
|---|---|---|
| `durable` | Trusted, ages out only by deprecation. Default for every `/new-feature` scaffold. | Templates, user edits, backfill script, `/complete-feature`. |
| `candidate` | Auto-captured, awaiting human verdict. | AI agents writing `research/`, session-end discoveries hook. |
| `deprecated` | Rejected. Stays on disk for history; excluded from default packs and stale reports. | `/review-memory` reject flow. |

`/review-memory` walks every `lifecycle: candidate` artifact and asks per-item: approve → durable, reject → deprecated, skip, quit.

### Retention tier

Tier is a pure function of artifact type — never stored in frontmatter.

| Tier | Types | Candidate stale after | Durable stale after |
|---|---|---|---|
| A | proposal, design, source-spec | never | never |
| B | pattern, research, notes | 180 days | reported, not pruned |
| C | tasks, plan, review, facts, domain, delta-spec | 90 days | reported as `durable-stale` |

`giantmem artifact stale --days 0` uses tier policy. The legacy `--days N` flag still works as a hard cutoff.

### Access log

Every artifact retrieval writes one row to `live.db.artifact_access`:

| Operation | Logged | Query / rank |
|---|---|---|
| `giantmem artifact list` (N rows) | N rows | query = filter summary, rank = 1..N |
| `giantmem artifact show <id>` | 1 row | query = NULL, rank = NULL |
| MCP `find_artifact` | N rows | query = arg summary, rank = 1..N |
| `gma` selection | (deferred) | TBD wiring |
| `giantmem artifact reindex` (auto from watcher) | 0 rows | watcher writes MUST NOT pollute the log |

`access_count` (last 30 days) is enriched onto JSON output of `artifact list --json` and `find_artifact` results. `giantmem access top` shows the top-N most-accessed; `giantmem access prune --older-than 180d` trims.

The next phase will use access counts as a recency-style ranking signal in the hybrid scorer.

### Preload packs

The session-start hook (`~/dev/giant-tooling/workspace/workspace_session_hook.py`) reads `~/.claude/config/preload_packs.yaml` when present and emits one `=== PRELOAD PACK: <pack>/<layer> ===` block per declared layer.

```yaml
packs:
  default:
    layer_1:
      name: global_preferences
      static_files:
        - ~/.claude/CLAUDE.md
    layer_2:
      name: scope_active_work
      query_template: "{active_scope} architecture decisions"
      scope_filter: "{active_scope}"
      limit: 5
      lifecycle: [durable]
    layer_3:
      name: repo_recent_work
      query_template: "{active_feature}"
      repo_filter: current
      limit: 5
      types: [proposal, delta-spec, design, tasks]
      lifecycle: [durable, candidate]
```

`{active_scope}` is resolved from the registry by matching the cwd's repo against the `repos:` lists. `{active_feature}` is the feature in `.giantmem/features/features.json` whose status is `in_progress`. `{repo}` and `{branch}` are detected from git. Missing variables collapse to empty strings — the layer keeps running.

Static files inline verbatim. Query layers run `giantmem artifact list` with the resolved filters, then optionally narrow by substring across id/feature/domain/name and file body. If the query eliminates everything, the layer falls back to the unfiltered filter set so packs never show an empty section when matching artifacts exist.

Phase 1 is additive — every existing session-start section still appears. Phase 2 (after dogfood) may trim redundancy.

## Walkthrough: set this up on a new machine

```bash
# 1. Seed the scope registry with the current repo.
giantmem scope init

# 2. Extend to other repos in the same scope (optional).
giantmem scope add-repo personal dotfiles giant-tooling

# 3. Backfill lifecycle on existing artifacts.
python3 ~/dev/giant-tooling/workspace/scripts/backfill_lifecycle.py --all-repos

# 4. Make sure preload_packs.yaml exists (default ships with claude-code-config).
ls ~/.claude/config/preload_packs.yaml

# 5. Smoke-test the hook.
echo '{"cwd":"'"$PWD"'","source":"resume"}' \
  | python3 ~/dev/giant-tooling/workspace/workspace_session_hook.py \
  | grep -A 5 'PRELOAD PACK'
```

After this, every new Claude session in any covered repo sees the same scope context, and `lifecycle: candidate` artifacts surface in `/review-memory` instead of accumulating silently.

## Open questions deferred to later phases

Phase 2 will spike the sqlite-vec Go binding and decide whether embeddings load via pure-Go ONNX, CGO, or a Python subprocess. Hybrid scoring weights and `--semantic` opt-in land in that phase. Phase 3 adds the fsnotify watch daemon, TF-IDF domain suggestion, and `domains/*.json` → typed-entity promotion.

Until those ship, treat the system as a passive memory backbone: it filters, ages, and packs — it doesn't yet semantically rank or auto-reindex.

## Reference

| Surface | Where |
|---|---|
| CLI subcommands | `giantmem scope`, `giantmem access`, `giantmem artifact --scope/--lifecycle/--days 0` |
| MCP tools | `find_artifact(scope, lifecycle)`, `get_stats(scope, repo, feature)` |
| Slash commands | `/review-memory` |
| Scripts | `backfill_lifecycle.py` (sibling to `backfill_frontmatter.py`) |
| Config files | `~/.giantmem-global/scopes.yaml`, `~/.claude/config/preload_packs.yaml`, `live.db` (scopes + artifact_access tables) |
| Source design | `.giantmem/features/scoped-memory/{proposal,design,tasks,specs/*}.md` |
