---
description: "Pick a recently-active repo/worktree (any layout) and auto-pair it. No doc load — just pairing."
argument-hint: "[--n <int>] [--since <7d|2h>]"
---

Surface recently active repos (worktrees or plain repos — anything live-indexed in giantmem) and auto-pair the chosen one. Companion to `/recent-docs` for when you don't have a specific doc in mind.

## Arguments

- `--n <int>`: limit results (default 10).
- `--since <dur>`: recency window. Default: no limit.

## Steps

1. **Fetch candidates** — single Bash call:

   ```
   giantmem recent repos --exclude-current --json -n <N> [--since <dur>]
   ```

   Parse JSON. If empty: tell user "no recent repos to pair with" and stop.

2. **Present picker** via `AskUserQuestion`:

   - One multi-choice question.
   - Each option label: `<age>  <project>  (<doc_count> docs)`
   - Description: full `worktree_path`.
   - Final option "Cancel" aborts.

3. **On pick**: run the `/pair-repo` flow on `worktree_path` (inline — see `/recent-docs` step 3c for the procedure). Use `role: sibling`.

4. **Output summary**

   ```
   Peer paired: <project> @ <worktree_path>  (role: sibling)
   peers.md: <path>

   /peer-scout <project> "<question>" for sub-agent dives.
   ```

## Notes

- Use `/recent-docs` if you want to load a specific doc and pair its repo in one step. This command is the bare-pair shortcut.
