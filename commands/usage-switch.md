---
description: "Rotate which account's usage the statusline displays (rc-team → rc-inc → skio). Display only — does not switch accounts."
argument-hint: ""
---

Rotate statusline usage display through `rc-team` → `rc-inc` → `skio`.

Display-only: this flips the `visible` filter in `~/.cache/claude-usage/config.json`, which controls which org's numbers the statusline renders. It does NOT change which account Claude Code bills usage to — run `/login` for that. Typical flow: `/login` into the account, then this command to point the statusline at it.

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
