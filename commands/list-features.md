---
description: List all features in the current workspace from the features cache. Auto-fires when user invokes /list-features, asks "what features are there", "show my features", "list active features", or "what's in progress".
---

Run the script — do NOT walk the cache by hand:

```bash
list-features
```

(`~/.claude/scripts/list-features`, on PATH. Reads `.giantmem/features/features.json`, prints a
table sorted by last_session desc. Handles missing dir / missing cache / no features itself.
Read-only — never mutates anything. Scans only `.giantmem/features`, never the archive.)

Show its output. That's the whole command.

If the user then asks about ONE specific feature, read that feature's `facts.md` + `proposal.md`
from `.giantmem/features/{name}/` (and `frontend.worktree` from its `meta.json` if a paired
counterpart is enabled).
