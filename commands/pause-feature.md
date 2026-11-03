---
description: "Pause current feature: mark as paused, capture context for later resumption"
argument-hint: "[feature-name]"
---

Compose the resumption context from THIS session first, then delegate — that's the one judgment slot.

1. Figure out, from the session so far: what was in progress, the next steps to pick up, any blockers. And a one-line paused-state snapshot (e.g. "endpoints wired, untested").
2. Run (feature inferred from the single in_progress one if omitted):

MCP `mcp__giantmem-search__feature` with `action: "pause"`, `cwd` = the worktree, optional `name`, `note` = "<what was in progress; next steps; blockers>", `paused_state` = "<last working state; uncaptured partial work>". MCP not connected → `giantmem feature pause [feature] --note "..." --paused-state "..."` from the worktree.

The CLI validates status==in_progress, flips to paused across proposal.md/facts.md/meta.json/features.json/_index.md, appends `## Resumption Notes` + `## Paused State`, reindexes. Prints JSON.

If you have no real context to write, omit the flags — the CLI inserts a placeholder you (or the user) fill later. Report the `resume_with` line.
