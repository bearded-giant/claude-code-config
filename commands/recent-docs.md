---
description: "Pick a recently-modified .giantmem doc from another repo, load it into context, and make its repo reachable. Optional dir_type filter."
argument-hint: "[dir_type] [--n <int>] [--since <7d|2h>] [--no-add-dir]"
---

Surface recently touched `.giantmem/*.md` docs across all live workspaces, let user pick one, then load the doc + make its repo reachable for sub-agents.

Use case: you were just working in another worktree's research/plans/feature spec, want to pick up here without copying paths between tmux panes.

## Arguments

- `dir_type` (optional positional): scope to one or more dir types (CSV). Common: `research`, `plans`, `features`, `reviews`, `context`. Default: all.
- `--n <int>`: limit results (default 10).
- `--since <dur>`: recency window (e.g. `7d`, `2h`). Default: no limit.
- `--no-add-dir`: load the doc but skip making the repo reachable.

## Steps

1. **Fetch candidates** — single Bash call:

   ```
   giantmem recent docs --exclude-current --json -n <N> [-t <dir_type>] [--since <dur>]
   ```

   Parse JSON. If empty: tell user "no recent docs from other repos" and stop.

2. **Present picker** via `AskUserQuestion`:

   - One question with multiple-choice options.
   - Each option label: `<age>  <project>/<dir_type>  <basename>`
     - Example: `19m  support-agent-wt/features  initial-ask-back/spec.md`
   - Description of each option: shortened path (use the rel path under `worktree_path`).
   - Cap option labels at ~40 chars; the description carries the long path.
   - Add a final option "Cancel" that aborts.

3. **On pick**:

   a. **Read the doc** via the `Read` tool (full file). Echo a one-line confirmation: `Loaded: <project>/<rel-path> (<age>)`.

   b. **Resolve the peer repo root**:
      - Take `worktree_path` from the chosen JSON row — that IS the repo root.
      - Sanity check: `<worktree_path>/.giantmem` exists.

   c. **Make the repo reachable** (skip if `--no-add-dir`):
      - `~/.claude/scripts/peer-probe <worktree_path>` (single Bash call). On error, stop with the error message.
      - Compare `git_root` to current repo's `git rev-parse --show-toplevel`. If equal, skip (same repo) and tell user.
      - Check `permissions.additionalDirectories` in `~/.claude/settings.json` and `~/.claude/settings.local.json`. Already listed (path or a parent) → done. Else ask user to pick: (1) write to `settings.local.json`, (2) run built-in `/add-dir` now, or (3) skip (read-only via `Read` tool only).

4. **Output summary**

   ```
   Loaded doc: <project>/<rel-path>
   Repo: <project> @ <worktree_path>  (branch: <branch>, dirty: <yes|no>)

   Doc contents are in context. /peer-scout <worktree_path> "<question>" for sub-agent dives.
   ```

   If `--no-add-dir` was used: omit the repo line, just confirm the doc load.

## Notes

- This command is the recommended entry point for "I want to work from doc X in repo Y" — beats copy-pasting paths between tmux panes.
- Pairs `well` with `/new-feature`: load the source-of-truth research doc first, then create the new feature spec from a populated context.
- Excludes current repo automatically (`--exclude-current`). Use `giantmem recent docs` directly (without this command) to see all recent docs including current.
