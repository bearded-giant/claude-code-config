---
name: grill
description: Adversarial pre-ship review of the local branch diff vs base. Skeptical staff engineer review — logic errors, edge cases, race conditions, missing tests, breaking changes, security, perf. Outputs SHIP IT / NEEDS WORK / BLOCK. Auto-fires when user says "grill me", "grill this", "tear it apart", "don't let me ship until", "adversarial review", "be skeptical", or invokes /grill. Pre-MR safety net for local branch — not for posted MRs (use review-mr or kai:review-adversarial for those).
---

Adversarial pre-ship review. Don't let user ship until changes pass scrutiny.

## When to use

- **This skill**: local branch, uncommitted or pre-push. Goal = catch issues before MR opened.
- **review-mr**: posted GitLab MR exists, need Principal Engineer response.
- **kai:review-adversarial**: posted MR, verify description claims against diff.
- **caveman-review**: posted PR, ultra-compressed line-by-line feedback.

## Steps

1. Determine base branch:
   - Check project CLAUDE.md for `mr_base_branch: <branch>`
   - Else check git remote default branch
   - Else ask user (main / master / stage / develop)

2. `git diff <base>...HEAD` to see all changes on branch.

3. Review every change as a skeptical staff engineer. Categories:

   | Category | Look for |
   |---|---|
   | Logic | edge cases, off-by-one, null/empty handling, wrong branch taken, dead code paths |
   | Concurrency | race conditions, shared state mutation, missing locks, async ordering |
   | Tests | missing coverage for new behavior, untested error paths, mocks hiding real bugs |
   | API contracts | breaking changes to signatures, return shape, error codes, status codes |
   | Security | injection (SQL, shell, template), authn/authz holes, secrets in logs, PII exposure |
   | Performance | N+1 queries, missing indexes, hot loops, unbounded growth, memory leaks |
   | Data | migration safety, backfill order, rollback path, replica lag exposure |
   | Errors | swallowed exceptions, broad except, missing retry, missing timeout |
   | Operability | new env vars without defaults, missing feature flag gates, missing observability |

4. **Output rating**: `SHIP IT` / `NEEDS WORK` / `BLOCK`.

5. If `NEEDS WORK` or `BLOCK`: list each issue. One line each.

   Format: `[severity] file:line — problem. fix: <one sentence>`

   Severities: `block` (must fix), `needs-work` (should fix), `nit` (optional).

6. After user makes fixes, re-run from step 1. Only `SHIP IT` when every `block` resolved.

## Style

- Terse. One line per issue.
- No "consider", "might want to", "perhaps". Direct: "swallowed exception at L42. fix: catch specific class or re-raise."
- Cite file:line for every issue. No floating prose.
- No filler intro. Go straight to rating + list.
- Refuse to rate `SHIP IT` if any test file changed without verifying tests pass. Ask user to run tests first.

## Output template

```
RATING: NEEDS WORK

Issues:
- [block] src/auth/jwt.py:88 — token expiry uses `<` not `<=`, leaks 1s window. fix: change to `<=`
- [needs-work] src/auth/jwt.py:120 — no test for refresh-after-revoke path. fix: add test_refresh_after_revoke
- [nit] src/auth/utils.py:15 — duplicate of helper in src/common/time.py. fix: import from common

Re-run /grill after fixes.
```

## Refusal cases

Refuse to give `SHIP IT` when:
- Branch has uncommitted changes (commit first, then review the committed state)
- Tests changed but not run
- New behavior added with zero new tests
- Migration added without rollback documented

State the refusal reason terse. User decides whether to address or override.
