---
description: "Mark a feature complete: update spec, facts, index, and current plan"
argument-hint: "[feature-name] [--quick] [--no-merge] [--reason=...]"
---

Delegates to the feature CLI for the mechanical close-out.

Before the CLI: `list_todos list=<repo list> feature=<name> filter=all` (repo list = the SessionStart `list:` line, else `python3 ~/.claude/hooks/doit_session_prime.py --name-only --cwd "$(pwd)"`) and keep items not done (`filter: "pending"` skips `in_progress`). Any open → AskUserQuestion naming each (`<list> #N (<label>)`, owed ones marked): complete the feature with them dangling / stop. Stop → end here, CLI not run.

Call MCP `mcp__giantmem-search__feature` with `action: "complete"`, `cwd` = the worktree, and optional `name`, `quick`, `no_merge`, `reason` (e.g. "shipped"). MCP not connected → `giantmem feature complete [feature] [--quick] [--no-merge] [--reason "shipped"]` from the worktree.

Feature inferred from the single in_progress/paused one if omitted. The CLI:
- flips status→complete (`done` in proposal frontmatter) + completed date across proposal.md/meta.json/features.json/_index.md (moves the index row to Completed)
- runs `merge_delta_spec.py {feature} --reason ...` when `features/{feature}/specs/` has delta-specs (skipped by `--quick` / `--no-merge` / when empty)
- reindexes, reports paired-counterpart MR reminder

Prints JSON (`merge` line shows merge result or why skipped).

After it runs, only if warranted (the CLI leaves these to you):
1. Clean up facts.md (final commands, key files, drop placeholders).
2. Mark `## Acceptance Criteria` items `[x]`; if some are unmet and there were no delta-specs, flag to the user.

No doit step after the CLI: the repo list persists (no delete ask), and items left dangling above stay open.

