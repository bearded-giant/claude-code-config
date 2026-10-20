---
description: "Rotate the fallback usage org (rc-team → rc-inc → skio) for the tmux strip and for sessions whose account can't be matched. Display only — does not switch accounts."
argument-hint: ""
---

Rotate the fallback usage display through `rc-team` → `rc-inc` → `skio`.

Display-only: this flips the `visible` filter in `~/.cache/claude-usage/config.json`. It does NOT change which account Claude Code bills usage to — run `/login` for that.

Each session's statusline already shows its own account's usage, matched by org, and ignores this filter. The filter applies to the tmux strip (`usage.tmux`) and to a session whose org can't be matched yet.

## Steps

1. Run:

   ```
   python3 ~/.claude/hooks/usage-fetch.py --switch
   ```

2. Echo command output to user (e.g. `switched to: skio`).
3. Statusline updates on next tick (≤30s cache).

## Related

- `python3 ~/.claude/hooks/usage-fetch.py --list` — show current state
- `--only <label>` / `--toggle <label>` / `--show-all` — manual control
