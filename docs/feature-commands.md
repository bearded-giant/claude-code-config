# Feature commands

Manage feature lifecycle across sessions, branches, and workspaces.

## Quick reference

| Command | Does |
|---|---|
| `/new-feature <name>` | Scaffold `features/{name}/` with `proposal.md` + `tasks.md` + empty `specs/` + `facts.md` + `meta.json`. Auto-status: `in_progress` if nothing active, else `pending`. Reindexes artifacts. |
| `/start-feature [name]` | Pick up a pending feature, create branch, set active. |
| `/pause-feature [name]` | Snapshot state, mark paused, stay on current branch. |
| `/reopen-feature [name]` | Resume paused/complete feature, checkout its branch. |
| `/complete-feature [name] [--no-merge] [--reason "..."]` | Mark done. Merges `features/{name}/specs/{domain}/spec.md` (delta-specs) → `.giantmem/specs/{domain}/spec.md` (source-of-truth). Writes per-feature + repo history. Reindexes. |
| `/abandon-feature [name] [--reason "..."] [--no-archive]` | Framed but not building it. Marks `status: abandoned` + `lifecycle: deprecated`, appends `## Abandoned`, skips the delta-spec merge entirely, then chains `giantmem feature archive` (dir removed, `live_docs` rows stay searchable). |
| `/feature-validate <name> [--fix]` | Lint structure + frontmatter; `--fix` auto-repairs. |
| `/feature-next [name]` | Print next ready artifact from `artifacts.json` + DAG config. |
| `/feature-report [name]` | QA report from delta-spec Requirements (falls back to legacy "Acceptance Criteria"). |
| `/list-features` | All features from cache. |
| `/feature-facts <name>` | Flags / config / branch / test commands. |
| `/review-memory [scope] [repo] [limit]` | Walk `lifecycle: candidate` artifacts: approve → durable / reject → deprecated / skip / quit. Persists frontmatter + reindexes. |

## Lifecycle

```
/new-feature (no active)   -->  /pause   -->  /reopen   -->  /complete
  (auto in_progress)            (shelve)      (resume)       (done)

/new-feature (active exists) -->  /start   -->  /pause   -->  ...
  (auto pending)                  (activate)    (shelve)
```

Auto-status: `/new-feature` reads `features.json` for any `in_progress`. If found → new feature = `pending`. Else → `in_progress`.

## Three-spec model

| Artifact | Path | Holds |
|---|---|---|
| proposal | `features/{name}/proposal.md` | Intent + scope + approach. NOT behavior. |
| delta-spec | `features/{name}/specs/{domain}/spec.md` | `## ADDED / MODIFIED / REMOVED Requirements`. Each Requirement has `#### Scenario:` GIVEN/WHEN/THEN (RFC 2119). |
| source-spec | `.giantmem/specs/{domain}/spec.md` | Accumulated across completed features. Only `/complete-feature` writes. Never hand-edit mid-feature. |

Legacy `features/{name}/spec.md` is a 30-day back-compat symlink → `proposal.md`.

Every `.md`/`.yaml` artifact has YAML frontmatter (`type`, `status`, `feature` or `repo`, `lifecycle`, ...). JSON artifacts use same keys top-level. Templates stamp `lifecycle: durable`. AI-captured discoveries / research land as `candidate` and surface in `/review-memory`. Backfill: `python3 ~/dev/giant-tooling/workspace/scripts/backfill_lifecycle.py`.

See [scoped-memory-overview.md](scoped-memory-overview.md) for the memory model.

## Features cache (`features.json`)

`.giantmem/features/features.json` — flat map keyed by feature name:

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

Every feature command updates this. `/list-features` reads directly. Rebuilds from `meta.json` files if cache missing.

## `/complete-feature` flow

Loose rules — never blocks.

1. Read `features/{name}/specs/{domain}/spec.md` (delta-specs).
2. Merge ADDED/MODIFIED/REMOVED Requirements → source-spec (idempotent).
3. Flip delta-spec frontmatter `status` ready → done.
4. Append to `features/{name}/spec_history.md` + `.giantmem/specs/_history.md`.
5. Update `.giantmem/specs/_index.md`.
6. Flip `meta.json` + `features.json` + `_index.md` → `complete`.
7. Reindex.

Does NOT touch git — you handle merge/PR.

Empty `specs/` → merge step silently skips.

## Branch handling

Feature names and branch names are decoupled. Branch stored in `meta.json`, `facts.md`, `features.json`.

| Command | Git behavior |
|---|---|
| `/new-feature` (in_progress) | Create branch. Prompts name + base. |
| `/new-feature` (pending) | No git. Deferred to `/start-feature`. |
| `/start-feature` | Create branch if none set. Checkout if exists. |
| `/reopen-feature` | Checkout recorded branch. Asks if branch deleted. |
| `/pause-feature` | No git. Metadata only. |
| `/complete-feature` | No git. Metadata only. |

## File update matrix

| File | new | start | pause | reopen | complete |
|---|:-:|:-:|:-:|:-:|:-:|
| `proposal.md` | created | expanded | status + notes | restored | → done |
| `tasks.md` | created | — | — | — | status from checkbox % |
| `specs/{domain}/spec.md` | dir created | — | — | — | → done after merge |
| `.giantmem/specs/{domain}/spec.md` | — | — | — | — | merged |
| `spec_history.md` (feature) | — | — | — | — | append |
| `.giantmem/specs/_history.md` | — | — | — | — | append |
| `.giantmem/specs/_index.md` | — | — | — | — | new domains |
| `facts.md` | created | + branch | + paused state | − paused | finalized |
| `meta.json` | created | status + branch | status | status | status |
| `features.json` | + entry | status + branch | status | status | status |
| `features/_index.md` | + row | pending → ip | ip → paused | → ip | → complete |
| `plans/current.md` | — | set active | cleared | set active | moved to completed |
| `artifacts.json` | reindex | reindex | — | reindex | reindex |
