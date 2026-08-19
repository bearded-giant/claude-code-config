---
description: "Pick a recently-active repo/worktree (any layout) and make it reachable for sub-agents. No doc load."
argument-hint: "[--n <int>] [--since <7d|2h>]"
---

Surface recently active repos (worktrees or plain repos — anything live-indexed in giantmem) and make the chosen one reachable. Companion to `/recent-docs` for when you don't have a specific doc in mind.

## Arguments

- `--n <int>`: limit results (default 10).
- `--since <dur>`: recency window. Default: no limit.

## Steps

1. **Fetch candidates** — single Bash call:

   ```
   giantmem recent repos --exclude-current --json -n <N> [--since <dur>]
   ```

   Parse JSON. If empty: tell user "no recent repos found" and stop.

2. **Present picker** via `AskUserQuestion`:

   - One multi-choice question.
   - Each option label: `<age>  <project>  (<doc_count> docs)`
   - Description: full `worktree_path`.
   - Final option "Cancel" aborts.

3. **On pick**: run `/recent-docs` step 3c inline — probe the path, then ensure it's in `permissions.additionalDirectories` (or have the user `/add-dir` it). Sub-agents inherit the same gate.

4. **Output summary**

   ```
   Repo: <project> @ <worktree_path>  (branch: <branch>, dirty: <yes|no>)

   /peer-scout <worktree_path> "<question>" for sub-agent dives.
   ```

## Notes

- Use `/recent-docs` if you want to load a specific doc and reach its repo in one step. This command skips the doc.
- Live Claude session already running in that repo? `SendMessage` beats a fresh sub-agent — it has warm context.
