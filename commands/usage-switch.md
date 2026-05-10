---
description: "Toggle Claude usage statusline between rc-team and rc-inc accounts."
argument-hint: ""
---

Flip statusline session indicators between Recharge Team (`rc-team`) and Recharge Inc (`rc-inc`).

## Steps

1. Run:

   ```
   python3 ~/.claude/hooks/usage-fetch.py --switch
   ```

2. Echo command output to user (e.g. `switched to: rc-inc`).
3. Statusline updates on next tick (≤30s cache).

## Related

- `python3 ~/.claude/hooks/usage-fetch.py --list` — show current state
- `--only <label>` / `--toggle <label>` / `--show-all` — manual control
