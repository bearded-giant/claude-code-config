# Feature Commands

Commands for managing feature lifecycle across sessions, branches, and workspaces.

## Quick Reference

| Command | What it does |
|---------|-------------|
| `/new-feature <name>` | Create feature folder. Auto-selects status: `in_progress` if nothing active, `pending` if another feature is in progress. |
| `/start-feature [name]` | Pick up a pending feature, create branch, start working |
| `/pause-feature [name]` | Snapshot state, mark paused, stay on current branch |
| `/reopen-feature [name]` | Resume paused/completed feature, checkout its branch |
| `/complete-feature [name]` | Mark done, finalize spec and facts |
| `/list-features` | Show all features from cache (fast, no directory scanning) |
| `/feature-facts <name>` | Quick lookup of a feature's flags, config, branch, test commands |

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

## Features Cache (`features.json`)

All feature metadata is cached in `scratch/features/features.json`. This is a flat JSON object keyed by feature name:

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

Auto-detects no active feature, creates as `in_progress`. Prompts for branch name and base branch. Creates `scratch/features/session-cleanup/` with spec, facts, and meta.json. Checks out the new branch.

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
/complete-feature
```

Finalizes spec (marks acceptance criteria), cleans up facts, updates the index. Does not touch git -- you handle the merge/PR separately.

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
| `spec.md` | created | expanded | status + resumption notes | status restored | status + criteria |
| `facts.md` | created | branch added | paused state snapshot | paused state removed | finalized |
| `meta.json` | created | status + branch | status | status | status |
| `features.json` | entry added | status + branch | status | status | status |
| `_index.md` | row added | pending -> in_progress | in_progress -> paused | paused/complete -> in_progress | in_progress -> complete |
| `plans/current.md` | -- | set active | cleared | set active | moved to completed |
| git branch | created (in_progress only) | created/checkout | -- | checkout | -- |
