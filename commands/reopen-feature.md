---
description: "Reopen a completed feature: set back to in_progress, update index and tracking"
argument-hint: "[feature-name]"
---

Delegates to the feature CLI.

```bash
python3 ~/dev/giant-tooling/workspace/scripts/feature.py reopen <feature> --cwd "$(pwd)"
```

The CLI validates status is `complete` or `paused`, checks out the recorded branch (reports if it's gone), flips to in_progress, removes the `completed`/`paused` frontmatter + the facts `## Paused State` section, reindexes. It surfaces any `## Resumption Notes` in the JSON `resumption_notes` field.

After it runs:
1. Show the `resumption_notes` to the user (the cold-start context).
2. If `checkout` reports the branch is gone, ask whether to recreate it (then `feature.py start`-style, or manual git).
3. If reopening from complete, ask which acceptance criteria need rework and uncheck them in proposal.md — the CLI leaves that judgment to you.
