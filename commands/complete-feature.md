---
description: "Mark a feature complete: update spec, facts, index, and current plan"
argument-hint: "[feature-name] [--quick] [--no-merge] [--reason=...]"
---

Delegates to the feature CLI for the mechanical close-out.

Before the CLI: list the feature's doit list (`python3 ~/.claude/hooks/doit_session_prime.py --name-only --cwd "$(pwd)"`) with `list_todos` `filter: "all"` and keep items not done (`filter: "pending"` skips `in_progress`). Any open → AskUserQuestion naming each (`<list> #N (<label>)`, owed ones marked): complete the feature with them dangling / stop. Stop → end here, CLI not run.

```bash
python3 ~/dev/giant-tooling/workspace/scripts/feature.py complete [feature] \
  [--quick] [--no-merge] [--reason "shipped"] --cwd "$(pwd)"
```

Feature inferred from the single in_progress/paused one if omitted. The CLI:
- flips status→complete (`done` in proposal frontmatter) + completed date across proposal.md/meta.json/features.json/_index.md (moves the index row to Completed)
- runs `merge_delta_spec.py {feature} --reason ...` when `features/{feature}/specs/` has delta-specs (skipped by `--quick` / `--no-merge` / when empty)
- reindexes, reports paired-counterpart MR reminder

Prints JSON (`merge` line shows merge result or why skipped).

After it runs, only if warranted (the CLI leaves these to you):
1. Clean up facts.md (final commands, key files, drop placeholders).
2. Mark `## Acceptance Criteria` items `[x]`; if some are unmet and there were no delta-specs, flag to the user.

Always, the feature's doit list after the CLI:
- Open items confirmed above → AskUserQuestion: delete the list / keep it open. Delete → `delete_list` alone: no `complete_todo`, no `delete_todo`, no DONE/WONTFIX notes. It archives the file to `deleted/` in the doit data dir and keeps each owed item's `daily` twin, unlinked, with the project-side notes; report the archive path and each kept twin from its reply. Keep → touch nothing.
- 0 pending → AskUserQuestion: delete it (`clear_done` + `delete_list`) / keep it. Skip when `/wrap` already asked this session.

Either ask names any tmux window `list_lists` shows linked to the list.

