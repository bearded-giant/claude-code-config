# Feature Commands

Commands for managing feature lifecycle across sessions, branches, and workspaces.

## Quick Reference

| Command | What it does |
|---------|-------------|
| `/new-feature <name>` | Create feature folder + branch, start working |
| `/new-feature <name> pending` | Stub out a feature for later (no branch) |
| `/start-feature [name]` | Pick up a pending feature, create branch, start working |
| `/pause-feature [name]` | Snapshot state, mark paused, stay on current branch |
| `/reopen-feature [name]` | Resume paused/completed feature, checkout its branch |
| `/complete-feature [name]` | Mark done, finalize spec and facts |
| `/list-features` | Show all features with status and last modified |
| `/feature-facts <name>` | Quick lookup of a feature's flags, config, branch, test commands |

## Lifecycle

```
/new-feature pending  -->  /start-feature  -->  /pause-feature  -->  /reopen-feature  -->  /complete-feature
     (stub)                  (activate)          (shelve)             (resume)              (done)

/new-feature  ------------------------------------------->  /pause-feature  -->  ...
  (activate immediately)
```

## Common Workflows

### 1. Start a new feature from scratch

```
/new-feature session-cleanup
```

Prompts for a branch name and base branch. Creates `scratch/features/session-cleanup/` with spec, facts, and meta.json. Checks out the new branch.

### 2. Discovery during another feature

You're working on feature A and realize feature B needs to exist. Stub it without switching context:

```
/new-feature session-preserve-on-reauth pending
```

This creates a minimal spec with your discovery context and purpose. No branch created, no context switch. The feature shows as `pending` in `/list-features`. Pick it up later with `/start-feature`.

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

The branch name is stored in `meta.json` and `facts.md` so commands can check it out automatically.

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
| `_index.md` | row added | pending -> in_progress | in_progress -> paused | paused/complete -> in_progress | in_progress -> complete |
| `plans/current.md` | -- | set active | cleared | set active | moved to completed |
| git branch | created | created/checkout | -- | checkout | -- |
