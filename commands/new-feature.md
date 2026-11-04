---
description: "Create a new feature folder with templates. Auto-detects status: pending if another feature is in_progress, otherwise in_progress."
argument-hint: "<name> [--branch=X] [--base=Y] [--builds-on=Z] [--paired]"
---

Delegates to the deterministic feature CLI. Do NOT scaffold by hand.

Call MCP `mcp__giantmem-search__feature` with `action: "new"`, `cwd` = the worktree (`pwd`), and from `$ARGUMENTS`: first token → `name`; `--branch=` → `branch`, `--base=` → `base`, `--builds-on=` → `builds_on`, `--paired` / `--no-paired` → `paired` / `no_paired`, `--skip-checkout` → `skip_checkout`; pending-stub reason → `discovery`. MCP not connected → `giantmem feature new <name> [flags]` from the worktree, same flags.

Baked in (don't duplicate): status = `pending` if any feature in_progress else `in_progress`; branch defaults to current HEAD, or the feature name when HEAD==base (the "start off develop" case — no prompt); base = origin/HEAD → develop→stage→main→master; guard refuses branch==base; paired only for the `cc-wt`↔`frontend-wt` map; pending skips git. Prints a JSON summary.

After it runs:
1. Error from the base==branch guard (only when `--branch=` was passed equal to base) → ask once for a distinct branch, re-run with `--branch=`.
2. `.giantmem/features/` missing → tell user to run `/ws-init`.
3. Success → summarize from JSON (branch+base, created-vs-reused, status+why, paired).
4. Echo Open Questions only if `open_questions` != `"none (placeholder only)"`. Offer to draft intent/scope from the feature goal.
5. No doit list to create: the repo list (SessionStart `list:` line) covers every feature. For the rest of the session every new doit item for this feature, any status incl. `pending`, passes `feature=<name>` on that list, even while SessionStart primed another feature. Never call `switch_list`: tmux window links are the user's view state.
