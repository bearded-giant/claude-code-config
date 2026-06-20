---
description: "Create a new feature folder with templates. Auto-detects status: pending if another feature is in_progress, otherwise in_progress."
argument-hint: "<name> [--branch=X] [--base=Y] [--builds-on=Z] [--paired]"
---

Delegates to the deterministic feature CLI. Do NOT scaffold by hand.

```bash
python3 ~/dev/giant-tooling/workspace/scripts/feature.py new <name> [flags] --cwd "$(pwd)"
```

Pass through from `$ARGUMENTS`: first token → `<name>`; `--branch= --base= --builds-on= --paired / --no-paired --skip-checkout` as-is; pending-stub reason → `--discovery="..."`.

Baked in (don't duplicate): status = `pending` if any feature in_progress else `in_progress`; branch defaults to current HEAD, or the feature name when HEAD==base (the "start off develop" case — no prompt); base = origin/HEAD → develop→stage→main→master; guard refuses branch==base; paired only for the `cc-wt`↔`frontend-wt` map; pending skips git. Prints a JSON summary.

After it runs:
1. Non-zero with the base==branch guard (only when `--branch=` was passed equal to base) → ask once for a distinct branch, re-run with `--branch=`.
2. `.giantmem/features/` missing → tell user to run `/ws-init`.
3. Success → summarize from JSON (branch+base, created-vs-reused, status+why, paired).
4. Echo Open Questions only if `open_questions` != `"none (placeholder only)"`. Offer to draft intent/scope from the feature goal.
