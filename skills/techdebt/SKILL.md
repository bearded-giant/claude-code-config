---
name: techdebt
description: End-of-session sweep for duplicated and dead code. Finds 3+ similar code blocks and unused exports/functions/variables. Asks which to fix, fixes one at a time with tests after each. Auto-fires when user says "tech debt", "techdebt", "dead code", "cleanup before commit", "end of session sweep", "find duplication", "what's unused", or invokes /techdebt. Skip if branch has zero edits or no test infra exists.
---

End-of-session codebase cleanup. Find and kill duplicated + dead code.

## When to use

- After a feature lands, before commit, "is there cruft I left behind?"
- Periodic sweep: "tech debt check" on a module
- After a refactor: "what helpers are now unused?"

## Steps

1. **Scope**: ask user — current branch diff, specific dir, or whole repo? Default: current branch + immediate neighbors of changed files (smallest useful blast radius).

2. **Scan** for:
   - **Duplication**: 3+ similar lines appearing in multiple places (literal or near-literal)
   - **Dead exports**: functions/classes/constants with no callers
   - **Dead branches**: unreachable code (always-true/always-false conditions, unreachable returns)
   - **Stale imports**: imported but unused
   - **Stale config**: env vars / settings / flags referenced nowhere
   - **Stale tests**: tests targeting functions that no longer exist

3. **Present findings** grouped by file:

   ```
   src/auth/jwt.py
     L42-58 — duplicate of src/auth/refresh.py:88-104 (16 lines, 90% match)
     L120-128 — unused function `_legacy_decode` (0 callers)

   src/utils/time.py
     L15 — unused import `pytz`
   ```

4. **Ask which to fix**: present numbered menu. User picks subset.

5. **Fix one at a time**:
   - Make the change
   - Run relevant tests (`py-check`/`ts-check` or project test command)
   - If tests fail → revert change, flag for user, move to next item
   - If tests pass → continue to next approved item

6. **Summary**: list what was removed, what was deduped, what was skipped (and why).

## Detection strategy

| What | How |
|---|---|
| Duplication | grep for 3+ line blocks, then visual diff. Use `ast-grep` or `semgrep` if available, fall back to `git grep -A 3` |
| Dead exports | language-specific tools (`vulture` for Python, `ts-prune`/`knip` for TS) — fall back to grep for symbol usage |
| Unreachable code | linter output (ruff F841, pyflakes, tsc unreachable code) |
| Stale imports | `ruff check --select F401`, `eslint no-unused-vars` |
| Stale config | grep env var / flag name across repo, report 0-reference matches |

Prefer tools when present. Skip to grep fallback if not installed.

## Style

- One line per finding. file:line — what — match percentage / caller count.
- No "you might want to consider" — direct: "unused function, 0 callers, suggest delete."
- Group by file, not by category, so user can context-switch less.
- If finding is borderline (e.g., 70% match), say so explicitly. Don't hide uncertainty.

## Refusal cases

- Branch has uncommitted changes → ask user to commit first (so revert is clean if a fix breaks tests)
- No test infra exists → warn user, proceed only with explicit "yes proceed without tests"
- Repo > 50 files in scope → ask user to narrow scope first

## Output template

```
Findings (4 items across 3 files):

src/auth/jwt.py
  1. [dup] L42-58 ≈ src/auth/refresh.py:88-104 (16 lines, 90% match) — extract to common
  2. [dead] L120-128 `_legacy_decode` — 0 callers, suggest delete

src/utils/time.py
  3. [import] L15 `pytz` unused

tests/test_legacy.py
  4. [dead] entire file — targets `_legacy_decode` (item #2)

Fix which? (1,2,3,4 / all / none / N1,N2)
```

After user picks, fix sequentially with tests after each.
