---
description: "Abandon a feature: mark abandoned, skip spec merge, archive it (docs stay in live.db)"
argument-hint: "[feature-name] [--reason=...] [--no-archive]"
---

For a feature that got framed and is not getting built. NOT the same as complete — no delta-spec merge, so nothing leaks into a source-spec.

Call MCP `mcp__giantmem-search__feature` with `action: "abandon"`, `cwd` = the worktree, and `name`, `reason` (e.g. "scope died"), optional `no_archive`. MCP not connected → `giantmem feature abandon [feature] [--reason "..."] [--no-archive]` from the worktree.

Works from any status except `archived`/`abandoned`. Name required unless there's exactly one in_progress feature. The CLI:
- stamps `status: abandoned` + `abandoned: <date>` + `lifecycle: deprecated` on proposal.md, appends `## Abandoned` with the reason
- flips status across meta.json/features.json, drops the `_index.md` row
- skips the delta-spec merge entirely
- reindexes, then chains `giantmem feature archive {feature}` — verifies every file is in live.db, removes the dir, sets status=archived (`--no-archive` keeps the dir)

Artifacts are left untouched on the way out; `live_docs` rows stay searchable via `giantmem find`, MCP, and the GUI.

After the CLI: `list_todos list=<repo list> feature=<name> filter=all` (repo list = the SessionStart `list:` line, else `python3 ~/.claude/hooks/doit_session_prime.py --name-only --cwd "$(pwd)"`), then close each item not done via `complete_todo` + `WONTFIX {ts} feature abandoned: <reason>` note. No list delete ask: the repo list persists.

Ask the user for a `reason` if they didn't give one — it's the only record of why the feature died. Do not offer to salvage or re-scope the feature unless they ask.
