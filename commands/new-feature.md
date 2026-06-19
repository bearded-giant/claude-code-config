---
description: "Create a new feature folder with templates. Auto-detects status: pending if another feature is in_progress, otherwise in_progress."
argument-hint: "<name> [--branch=X] [--base=Y] [--builds-on=Z] [--paired]"
---

Delegates the whole scaffold to one deterministic script — status detect, branch
resolve+checkout, file scaffold (proposal/tasks/facts/notes/meta), features.json +
_index.md update, `giantmem artifact reindex`, session topic pin — in a single process.
Do NOT re-implement these steps by hand; that is what made this command slow.

## Run

```bash
python3 ~/dev/giant-tooling/workspace/scripts/new_feature.py <name> [flags]
```

Parse `$ARGUMENTS` and pass through:
- first positional token → `<name>` (kebab-case, required)
- `--branch=X` `--base=Y` `--builds-on=Z` `--paired` / `--no-paired` `--skip-checkout` → pass as-is
- pending-stub discovery context (why it's queued) → `--discovery="..."`

Always pass `--cwd "$(pwd)"`.

Behavior baked into the script (don't duplicate):
- **Status**: `pending` if any feature is `in_progress`, else `in_progress`.
- **Branch default**: current HEAD, EXCEPT when HEAD == base (sitting on the base branch) it
  defaults to the feature name. This is the common "start a feature off develop" case — no prompt needed.
- **Base default**: `origin/HEAD` → fallbacks `develop`→`stage`→`main`→`master` (remote then local).
- **Guard**: refuses when resolved branch == base.
- **Paired**: only for repos in the hardcoded `cc-wt`↔`frontend-wt` map; otherwise `frontend.enabled=false`.
- `pending` features skip all git (branch deferred to `/start-feature`).

The script prints a JSON summary (status, branch, base, checkout state, files, reindex, topic, open_questions).

## After it runs

1. **If it exits non-zero with the base==branch guard** (only when `--branch=` was passed equal to base):
   ask the user once for a distinct branch name (single AskUserQuestion), then re-run with `--branch=`.
2. **If `.giantmem/features/` is missing**: tell the user to run `/ws-init`.
3. **Success**: summarize from the JSON (branch + base + created-vs-reused, status + why, paired state).
   Surface `reindex` / `topic` only if they report `skipped` and it matters.
4. **Echo Open Questions**: only if `open_questions` is NOT `"none (placeholder only)"` —
   i.e. the user pre-seeded real questions. Otherwise skip silently. Offer to draft intent/scope
   from the feature goal if they give it.
