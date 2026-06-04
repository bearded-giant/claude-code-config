---
description: Update kai plugin then reapply local patches from kai-patches/
---

Wrap kai's `update-kai` skill with patch reapplication. Steps:

1. Invoke the `kai:update-kai` skill. Pass through `$ARGUMENTS` (e.g. `--dry-run`). Wait for completion.
2. If the update reported new commits pulled (not dry-run, not already up to date), run:
   ```bash
   ~/dev/claude-code-config/scripts/apply-kai-patches.sh
   ```
3. Report combined output:
   - kai update summary (commits pulled, changed skills/agents)
   - patch reapply summary (applied / skipped / failed)
4. If any patch failed, surface the failure loudly and tell the user to regenerate that patch against the new upstream (see `kai-patches/README.md` conflict resolution).
5. Prompt user to restart claude session for plugin reload.

Skip patch reapply when:
- `--dry-run` was passed
- `kai:update-kai` reported "already up to date"
- `kai:update-kai` failed (don't compound errors)
