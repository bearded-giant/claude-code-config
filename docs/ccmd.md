# Slash Command Usage — Non-Interactive Driving

This doc covers running slash commands non-interactively via `claude -p`, the `ccmd` wrapper, the named-flag arg convention used by `/new-feature`, and the paired-counterpart (cross-repo) model that flows through `new-feature` → `start-feature` → `complete-feature` → `list-features`.

Review later — this is the source of truth for the workflow these commands implement.

---

## 1. The `ccmd` wrapper

Location:
- Source: `~/dev/claude-code-config/scripts/ccmd` (tracked in repo)
- Symlink: `~/.local/bin/ccmd` → source (created by `install.sh`)

Edit the source file. Symlink picks up changes immediately, no reload needed. Fresh installs run `install.sh` to re-create the symlink.

Why it exists: `claude -p` takes the prompt as a single positional arg. Flags like `--quick` or `--paired` get parsed by the `claude` CLI itself unless the whole prompt is quoted as one string. The wrapper does the quoting.

Shape:

```bash
ccmd <command-name> [args...]
# expands to: claude -p "/<command-name> <args>"
```

Optional `CCMD_CLAUDE_ARGS` env var forwards extra flags to `claude` itself (model, permission mode, etc.):

```bash
CCMD_CLAUDE_ARGS="--model sonnet --permission-mode acceptEdits" ccmd new-feature ...
```

Inside the slash command body, the whole arg string lands in `$ARGUMENTS`. The command is responsible for parsing flags out of that string.

---

## 2. Arg-style convention for non-interactive commands

Slash commands that support non-interactive driving accept **named flags** in `$ARGUMENTS`:

- First positional token = primary identifier (feature name, etc.)
- `--key=value` for options that take a value
- Bare `--flag` for booleans (opt-in)
- Bare `--no-flag` for explicit negation

Behavior when a required value is missing:

| Mode | Behavior |
|---|---|
| Interactive (TTY) | Prompt the user |
| Non-interactive (`-p`) | Fail with a clear error message |

Behavior when an optional boolean flag is missing:

| Mode | Default |
|---|---|
| Interactive (TTY) | Prompt |
| Non-interactive (`-p`) | False (treat as opt-out) |

This pattern is currently used by `/new-feature`. `/complete-feature` uses a single `--quick` flag, which is the degenerate case.

---

## 3. The paired-counterpart model (cross-repo features)

Some features require parallel branches in two linked repos (e.g., a backend API change plus a matching frontend UI change). The slash commands model this as a **paired counterpart**.

### Hardcoded counterpart map

The map lives inline in `/new-feature` (step 6a) and `/start-feature` (step 3b). It is intentionally hardcoded — only two pairs today, easy to scan, no extra config file to keep in sync.

| Current path prefix | Paired counterpart root | Counterpart base | Worktree create cmd |
|---|---|---|---|
| `~/dev/python/cc-wt/` | `~/dev/javascript/frontend-wt/` | `master` | `fewta {branch} master` |
| `~/dev/javascript/frontend-wt/` | `~/dev/python/cc-wt/` | `stage` | `cwta {branch} stage` |

The map is **bidirectional**: starting a feature from either side creates the counterpart in the other.

`fewta` and `cwta` are registered shell functions from `~/dotfiles/shell/scripts/worktrees/wt-frontend.sh` and `wt-customcheckout.sh`. Both use the `wt_register <prefix>` pattern where `<prefix>a` is the "add worktree" verb. Fallback uses raw `git worktree add` against the bare repo if the helper is not on PATH.

If `git rev-parse --show-toplevel` does not match a listed prefix, the current repo has no counterpart. The `--paired` flag is ignored (with a warning) and the feature is recorded as single-repo.

### Flag semantics

| Flag | Meaning |
|---|---|
| `--paired` | This feature needs a parallel branch in the counterpart repo. Worktree gets created. |
| `--no-paired` | Explicit single-repo. Skip the prompt even in interactive mode. |
| neither (interactive) | Prompt. |
| neither (`-p`) | Default to single-repo. |

### JSON schema — legacy `frontend.*` field

The persisted schema in `meta.json` and `features.json` still uses `frontend.*`:

```json
{
  "frontend": {
    "enabled": true,
    "branch": "<counterpart branch>",
    "base_branch": "<counterpart base>",
    "worktree": "<absolute counterpart worktree path>"
  }
}
```

This is a deliberate misnomer kept for back-compat. The field represents **any paired counterpart**, not specifically a frontend. When working from the FE side (frontend-wt), `frontend.worktree` will point at a path under `~/dev/python/cc-wt/`. Read it as "paired counterpart info that happens to be stored under the legacy key `frontend`".

Renaming the schema would require a coordinated update across all five feature commands plus any existing `features.json` data. Not worth the churn for a two-repo setup.

### Command coverage

| Command | Counterpart handling |
|---|---|
| `/new-feature` | Creates the counterpart worktree on `--paired`. Writes `frontend.*` to JSON. |
| `/start-feature` | Same as new-feature, but for pending → in_progress transitions. Reuses existing config if `frontend.enabled` already true. |
| `/complete-feature` | Reads `frontend.worktree` from JSON. Reports it as "Paired counterpart" and reminds user the counterpart needs its own MR. Does NOT remove the worktree. |
| `/list-features` | Displays `frontend.branch` under the `Paired` column. `-` if disabled. |
| `/pause-feature`, `/reopen-feature` | No counterpart-specific logic (operate on whatever the JSON already records). |

---

## 4. Worked examples

### `/complete-feature` — quick mode

```bash
ccmd complete-feature logging-extras --quick
```

`$ARGUMENTS` = `logging-extras --quick`. Skips facts.md / plans/current.md / paired-counterpart check; only updates status + completion date + index + features.json.

### `/new-feature` from BE side, with paired FE

```bash
cd ~/dev/python/cc-wt/some-branch
ccmd new-feature jwt-session-enforcement \
  --branch=feat/jwt-session \
  --base=stage \
  --paired
```

Result:
- BE branch `feat/jwt-session` checked out from `origin/stage` in current cc-wt worktree
- FE worktree created at `~/dev/javascript/frontend-wt/feat/jwt-session/` from `origin/master`
- `frontend.enabled = true`, `frontend.branch = feat/jwt-session`, `frontend.base_branch = master`, `frontend.worktree = ~/dev/javascript/frontend-wt/feat/jwt-session`

### `/new-feature` from FE side, with paired BE

```bash
cd ~/dev/javascript/frontend-wt/some-branch
ccmd new-feature jwt-ui-revamp \
  --branch=feat/jwt-ui \
  --base=master \
  --paired
```

Result:
- FE branch `feat/jwt-ui` checked out from `origin/master` in current frontend-wt worktree
- BE worktree created at `~/dev/python/cc-wt/feat/jwt-ui/` from `origin/stage`
- `frontend.enabled = true`, `frontend.branch = feat/jwt-ui`, `frontend.base_branch = stage`, `frontend.worktree = ~/dev/python/cc-wt/feat/jwt-ui`

Note the schema misnomer: from the FE side, `frontend.worktree` points at a BE path. Read it as "paired counterpart".

### `/new-feature` single-repo

```bash
ccmd new-feature local-cleanup --branch=chore/cleanup --base=stage
```

No `--paired`, no prompt (non-interactive). `frontend.enabled = false`. Works in any repo, no counterpart logic runs.

### `/new-feature` — lazy mode (smart defaults)

Both `--branch` and `--base` are optional:

| Flag missing | Default |
|---|---|
| `--branch` | Current HEAD (`git rev-parse --abbrev-ref HEAD`) |
| `--base` | Remote default branch (`git symbolic-ref --short refs/remotes/origin/HEAD`), with fallback order: `develop` → `stage` → `main` → `master` (first that exists on `origin`) |

Shortest usage when you're already on the feature branch and the repo has a sensible default base:

```bash
ccmd new-feature analytics-tidy
```

Sanity guard: refuses if resolved branch == resolved base (so it won't accidentally create a feature record sitting on `main`/`develop`). Override by passing `--branch=` explicitly.

### `/new-feature` when branch already exists

Step 5 auto-detects:

1. Currently on `{branch}` → no git ops, just record.
2. Branch exists locally → `git checkout {branch}`.
3. Branch exists on `origin` only → fetch + check out tracking.
4. Branch nowhere → create from `{base}`.

For full opt-out of git side effects, pass `--skip-checkout`:

```bash
# explicit branch + base, branch may or may not exist
ccmd new-feature analytics-tidy --branch=feat/analytics-tidy --base=develop

# explicit skip (no git ops at all)
ccmd new-feature analytics-tidy --branch=feat/analytics-tidy --base=develop --skip-checkout
```

`--base` is still recorded in JSON for traceability even when no checkout runs.

### `/new-feature` in a non-paired repo with `--paired` set

```bash
cd ~/dev/ai/chat-orchestrator-wt/some-branch
ccmd new-feature harness-update --branch=feat/x --base=main --paired
```

Result: `--paired` ignored with a warning ("repo X has no listed counterpart"). Feature created single-repo.

---

## 5. Extending — adding a new paired repo

1. Pick the path prefix (e.g., `~/dev/python/some-other-repo-wt/`)
2. Identify the paired counterpart's worktree root, base branch, and `wt_register` prefix (so the create cmd is `<prefix>a`)
3. Add one row to the table in `/new-feature` step 6a **and** `/start-feature` step 3b (table must stay in sync — duplication is intentional, only two callers)
4. No code changes elsewhere — `/complete-feature` and `/list-features` read `frontend.worktree` from JSON, so they pick up the new pair automatically

If the list ever grows past ~5 rows, factor into a shared reference file and have the commands include it.

---

## 6. Known sharp edges

- **Interactive prompts inside `claude -p`**: any slash command that hits an unprovided required value (no `--branch`, no `--base`) will fail in non-interactive mode rather than prompt. Provide the flags, or run interactively.
- **Schema misnomer**: `frontend.*` in JSON does not necessarily mean frontend. Mental rename to "paired counterpart" when reading.
- **Table duplication**: counterpart table lives in both `/new-feature` and `/start-feature`. If you add a row to one, add to the other.
- **`/complete-feature` does not delete the counterpart worktree**: intentional. Counterpart MR is the user's responsibility, including the cleanup.
- **`--quick` on `/complete-feature` skips the counterpart check**: deliberate. If you need the counterpart-MR reminder, run without `--quick`.
