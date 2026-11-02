---
description: "Mark a feature complete: update spec, facts, index, and current plan"
argument-hint: "[feature-name] [--quick] [--no-merge] [--reason=...]"
---

Delegates to the feature CLI for the mechanical close-out.

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

Always: the feature's doit list (`python3 ~/.claude/hooks/doit_session_prime.py --name-only --cwd "$(pwd)"`) at 0 pending → AskUserQuestion: delete it (`clear_done` + `delete_list`) / keep it. Name any tmux window `list_lists` shows linked to it. Skip when `/wrap` already asked this session.

