# Feature Commands

Commands for managing feature lifecycle across sessions, branches, and workspaces.

## Quick Reference

| Command | What it does |
|---------|-------------|
| `/new-feature <name>` | Create feature folder. Scaffolds `proposal.md` + `tasks.md` + empty `specs/` (all with YAML frontmatter), runs `giantmem artifact reindex`. Auto-selects status: `in_progress` if nothing active, `pending` if another feature is in progress. |
| `/start-feature [name]` | Pick up a pending feature, create branch, start working |
| `/pause-feature [name]` | Snapshot state, mark paused, stay on current branch |
| `/reopen-feature [name]` | Resume paused/completed feature, checkout its branch |
| `/complete-feature [name] [--no-merge] [--reason "..."]` | Mark done. Merges feature's `specs/{domain}/spec.md` (delta-specs) into `.giantmem/specs/{domain}/spec.md` (source-of-truth) unless `--no-merge` or no delta-specs exist. Writes per-feature + repo-level history. Reindexes. |
| `/feature-validate <name> [--fix]` | Lint feature structure + frontmatter; `--fix` auto-repairs (rename, backfill, scaffold). |
| `/feature-next [name]` | Informational. Reads `artifacts.json` + DAG config, prints next ready artifact + path + hint. |
| `/feature-report [name]` | QA report. Parses delta-spec Requirements first; falls back to legacy "Acceptance Criteria" bullets when no delta-specs. |
| `/list-features` | Show all features from cache (fast, no directory scanning) |
| `/feature-facts <name>` | Quick lookup of a feature's flags, config, branch, test commands |
| `/review-memory [scope] [repo] [limit]` | Walk `lifecycle: candidate` artifacts. Per-item: approve → durable / reject → deprecated / skip / quit. Persists frontmatter + reindexes. |

## Lifecycle

```
/new-feature (no active feature)  -->  /pause-feature  -->  /reopen-feature  -->  /complete-feature
  (auto in_progress)                    (shelve)             (resume)              (done)

/new-feature (active feature exists)  -->  /start-feature  -->  /pause-feature  -->  ...
  (auto pending)                            (activate)           (shelve)
```

## Auto-Status on `/new-feature`

The status is determined automatically:

1. `/new-feature` reads `features.json` to check for any `in_progress` feature
2. If one exists: new feature is created as `pending` (you're mid-work, just stubbing for later)
3. If none exists: new feature is created as `in_progress` (you're starting fresh)

This removes the extra step of having to say `start` or run `/start-feature` separately when you're ready to work.

## Three-spec model (post-migration)

Per-feature `spec.md` was split into three typed artifacts:

| Artifact | Path | Holds |
|---|---|---|
| `proposal` | `features/{name}/proposal.md` | Intent + scope + approach. NOT behavior. |
| `delta-spec` | `features/{name}/specs/{domain}/spec.md` | `## ADDED / MODIFIED / REMOVED Requirements` blocks. Each `### Requirement:` carries `#### Scenario:` (GIVEN/WHEN/THEN, RFC 2119). |
| `source-spec` | `.giantmem/specs/{domain}/spec.md` | Accumulated behavior across every completed feature. Written ONLY by `/complete-feature` merging delta-specs in. Never hand-edit mid-feature. |

Legacy `features/{name}/spec.md` is a 30-day back-compat symlink → `proposal.md` (set by `migrate_spec_to_proposal.py`).

Every `.md` / `.yaml` artifact has YAML frontmatter (`type`, `status`, `feature` or `repo`, `lifecycle`, …). JSON artifacts use the same keys at top level. That's what makes the typed query layer (`giantmem artifact`, MCP `find_artifact`, fzf `gma`) possible.

Templates stamp `lifecycle: durable` on every scaffolded artifact. AI-captured discoveries / research land as `lifecycle: candidate` and surface in `/review-memory`. Backfill legacy files via `python3 ~/dev/giant-tooling/workspace/scripts/backfill_lifecycle.py`.

Full breakdown: [usage-summary.md](usage-summary.md). Scoped-memory model: [scoped-memory-overview.md](scoped-memory-overview.md) / [scoped-memory-guide.md](scoped-memory-guide.md).

## Features Cache (`features.json`)

All feature metadata is cached in `.giantmem/features/features.json`. This is a flat JSON object keyed by feature name:

```json
{
  "session-cleanup": {
    "name": "session-cleanup",
    "status": "in_progress",
    "branch": "fix-session-cleanup",
    "base_branch": "main",
    "builds_on": "none",
    "beta_flag": "",
    "created": "2026-02-15",
    "last_session": "2026-02-15"
  }
}
```

Every feature command (new, start, pause, complete, reopen) updates this cache. `/list-features` reads directly from it, making it fast and token-efficient.

If the cache is missing but feature directories exist, `/list-features` rebuilds it from individual `meta.json` files.

## Common Workflows

### 1. Start a new feature (nothing else active)

```
/new-feature session-cleanup
```

Auto-detects no active feature, creates as `in_progress`. Prompts for branch name and base branch. Creates `.giantmem/features/session-cleanup/` with `proposal.md` (intent only), `tasks.md` (empty checkbox scaffold), empty `specs/` (delta-specs land here later), `facts.md`, `meta.json` — all with YAML frontmatter. Checks out the new branch. Runs `giantmem artifact reindex` so `.giantmem/artifacts.json` reflects the new entries immediately.

### 2. Discovery during another feature

You're working on feature A and realize feature B needs to exist. Stub it without switching context:

```
/new-feature session-preserve-on-reauth
```

Auto-detects feature A is `in_progress`, creates B as `pending`. No branch created, no context switch. Pick it up later with `/start-feature`.

### 3. Pick up a pending feature

```
/start-feature
```

If multiple pending features exist, lists them and asks which one. Prompts for branch name and base, creates the branch, expands the stub spec into a full working template, and sets it as active work in `plans/current.md`.

### 4. Switch between features

Pause current work, reopen something else:

```
/pause-feature
/reopen-feature session-cleanup
```

Pause captures resumption notes and working state in spec and facts. Reopen checks out the feature's branch and surfaces the resumption notes.

### 5. Finish a feature

```
/complete-feature                                  # default merge
/complete-feature --no-merge                       # explicit skip even when delta-specs exist
/complete-feature --reason "scope cut, moved to X" # captured in both history files
```

Loose rules — never blocks. Steps:

1. Reads `features/{name}/specs/{domain}/spec.md` (delta-specs).
2. Merges ADDED / MODIFIED / REMOVED Requirements into `.giantmem/specs/{domain}/spec.md` (source-spec, created if missing). Idempotent — re-runs are no-ops.
3. Flips each delta-spec's frontmatter `status` from `ready` → `done`.
4. Appends a merge entry to `features/{name}/spec_history.md` (per-feature) AND `.giantmem/specs/_history.md` (repo-level chronological log).
5. Updates `.giantmem/specs/_index.md` with new domains.
6. Flips `meta.json` + `features.json` + `_index.md` status to `complete`.
7. Runs `giantmem artifact reindex`.

Does not touch git — you handle merge/PR separately.

If `features/{name}/specs/` is empty (no behavior contracts written), the merge step silently skips. Common when the feature was a fix, scope cut, or moved elsewhere.

## Branch Handling

Feature names and branch names are intentionally decoupled. Your feature might be `session-redis-only-save-latest` while the branch is `shopify-do-not-accumulate-sessions`.

The branch name is stored in `meta.json`, `facts.md`, and `features.json` so commands can check it out automatically.

| Command | Git behavior |
|---------|-------------|
| `/new-feature` (in_progress) | Creates branch. Prompts for name + base branch. |
| `/new-feature` (pending) | No git. Branch deferred to `/start-feature`. |
| `/start-feature` | Creates branch if none set. Checks out if already exists. |
| `/reopen-feature` | Checks out recorded branch. Asks if branch was deleted. |
| `/pause-feature` | No git. Metadata only. |
| `/complete-feature` | No git. Metadata only. |

## What Gets Updated

| File | `/new-feature` | `/start-feature` | `/pause-feature` | `/reopen-feature` | `/complete-feature` |
|------|:-:|:-:|:-:|:-:|:-:|
| `proposal.md` | created (frontmatter) | expanded | status + resumption notes | status restored | status → done |
| `tasks.md` | created (frontmatter, empty checkbox scaffold) | -- | -- | -- | status auto from checkbox % |
| `specs/{domain}/spec.md` (delta-spec) | dir created, files empty | -- | -- | -- | status → done after merge |
| `.giantmem/specs/{domain}/spec.md` (source-spec) | -- | -- | -- | -- | created/updated by merge |
| `spec_history.md` (per-feature) | -- | -- | -- | -- | append on merge |
| `.giantmem/specs/_history.md` (repo) | -- | -- | -- | -- | append on merge |
| `.giantmem/specs/_index.md` | -- | -- | -- | -- | new-domain rows |
| `facts.md` | created (frontmatter) | branch added | paused state snapshot | paused state removed | finalized |
| `meta.json` | created | status + branch | status | status | status |
| `features.json` | entry added | status + branch | status | status | status |
| `features/_index.md` | row added | pending → in_progress | in_progress → paused | paused/complete → in_progress | in_progress → complete |
| `plans/current.md` | -- | set active | cleared | set active | moved to completed |
| `artifacts.json` | reindexed | reindexed | -- | reindexed | reindexed |
| git branch | created (in_progress only) | created/checkout | -- | checkout | -- |
