---
name: grill
description: Adversarial pre-ship review loop for larger/complex changes. Reviews local branch diff vs base as skeptical staff engineer, scores each finding (severity 1-5, confidence 0-1), auto-fixes high-confidence sev 2-4 items per dual-axis matrix, flags sev-5 for human, loops up to N turns (default 3, configurable 1-5). Supports --loops, --threshold, --sev2-threshold, --dry-run, --base, --max-fixes-per-turn, --kai/--no-kai. Sticky per-feature config at .config.yaml. Outputs per-run artifacts under .giantmem/features/{feature}/grill/. Auto-fires when user says "grill me", "grill this", "tear it apart", "don't let me ship until", "adversarial review", "be skeptical", or invokes /grill. Pre-MR safety net for local branch — not for posted MRs (use kai-review:review-code or kai:review-adversarial for those).
---
<!-- caveman:compressed -->

Adversarial pre-ship review LOOP. Skeptical staff engineer reviews diff, scores findings, auto-fixes confident items, surfaces uncertain/fatal items, re-runs. Max 3 turns.

NEVER commits. NEVER pushes. NEVER stages. Edits files only.

## When to use

- **This skill**: local branch, pre-push. Catch + auto-tighten before MR opened. `--kai` predicts Recharge CI reviewer verdict before push.
- **kai-review:review-code**: posted GitLab MR exists.
- **kai:review-adversarial**: posted MR, verify claims vs diff.
- **caveman-review**: posted PR, line-by-line feedback.

## Output location

Resolve in order:

1. Active feature (status `in_progress` in `.giantmem/features/features.json`) → `.giantmem/features/{feature}/grill/`
2. No active feature → `.giantmem/grill/{YYYYMMDD-HHMM}/`

Create dir if missing. Files written per run:

```
grill/
  01-run.md
  02-run.md    (only if loop continues)
  03-run.md    (only if loop continues)
  final.md     (always, end of last run)
```

## Scoring rubric

### Severity (1-5)

| Score | Bucket | Meaning |
|---|---|---|
| 5 | Hard-Stop | Fatal logic / data / security. Outage, corruption, breach. Auto-fix forbidden — human review required. |
| 4 | Blocker | Real bug, breaking change, or missing safety. Must fix before ship. |
| 3 | Needed | Wrong-but-recoverable. Should fix before ship — readers will hit it. |
| 2 | Needed (minor) | Smell, weak test, narrow edge case. Fine to defer. |
| 1 | Nit | Style, naming, micro-cleanup. Doing nothing costs nothing. |

### Confidence (0.00-1.00)

Certainty the finding is real AND the proposed fix is correct. Examples:
- 0.95+ : verified via reading both call site and definition, behavior unambiguous
- 0.85-0.94 : strong inference from diff + immediate context
- 0.70-0.84 : plausible but depends on assumed caller behavior / runtime state
- < 0.70 : guess — surface only if sev ≥ 4

Default threshold for auto-fix: **0.85**. Tune after observing runs.

**Evidence gate**: conf ≥ 0.85 requires named evidence — files read (caller + definition), command output, type trace, or repro. No evidence → conf capped at 0.70 (below auto-fix). Evidence recorded per finding in run.md.

## Verification pass (refute before score)

For every candidate finding sev ≥ 3, BEFORE assigning final confidence: attempt to REFUTE it.

- Read the caller AND the definition, not just the diff hunk
- Trace the data path / types the finding depends on
- Runnable cheaply (pure function, small script)? Run the repro
- Finding assumes runtime state? Name the assumption in evidence; conf ≤ 0.84 unless state confirmed

Finding survives refutation → score with evidence. Refuted → drop (note in run.md `refuted:` list, one line each — reader sees what was considered). Same standard as claim-verification in `kai:review-adversarial`, applied pre-MR.

## Dual-axis decision matrix

Two thresholds: `T_main` (default 0.85, sev 3-4) and `T_sev2` (default 0.95, sev-2 only).

| Sev | Conf ≥ threshold | Conf < threshold |
|---|---|---|
| 5 Hard-Stop | flag-human, NO auto-fix | flag-human, NO auto-fix |
| 4 Blocker | auto-fix (T_main) | flag-user (uncertain blocker) |
| 3 Needed | auto-fix (T_main) | skip (note in final) |
| 2 Needed-minor | auto-fix (T_sev2) | report only |
| 1 Nit | report only | report only |

Dispositions: `auto-fix` | `flag-human` | `flag-user` | `skip` | `report-only`.

In `--dry-run` mode: all `auto-fix` dispositions downgrade to `would-fix` (recorded in run.md, no edits applied, loop stops after run 01).

## Arguments

All optional. Parsed from `$ARGUMENTS` after `/grill`.

| Arg | Type | Default | Range | Effect |
|---|---|---|---|---|
| `--loops N` | int | 3 | 1-5 | Max loop turns. >5 rejected (diminishing returns + churn risk). |
| `--threshold X` | float | 0.85 | 0.50-1.00 | Conf cutoff for sev 3-4 auto-fix. |
| `--sev2-threshold X` | float | 0.95 | 0.50-1.00 | Conf cutoff for sev-2 auto-fix. |
| `--dry-run` | flag | off | — | Score + report only. No edits, no loops past run 01. |
| `--base <branch>` | string | auto | any ref | Override base branch detection. |
| `--max-fixes-per-turn N` | int | unlimited | 1+ | Hard cap on edits applied per turn. Extra `auto-fix` items demoted to `deferred` and surfaced in final.md. |
| `--kai` | flag | auto | — | Force Kai preflight on. Auto = on when `origin` points at `gitlab.rechargeapps.net`. |
| `--no-kai` | flag | auto | — | Force Kai preflight off. |

Examples:
- `/grill --loops 2 --threshold 0.9`
- `/grill --dry-run`
- `/grill --base develop --max-fixes-per-turn 10`

Reject invalid values (out of range, non-numeric) with terse error. Do not silently clamp.

## Sticky config

Per-feature config at `.giantmem/features/{feature}/grill/.config.yaml` (or `.giantmem/grill/{ts}/.config.yaml` for non-feature runs).

Resolution order (highest wins):
1. CLI args this invocation
2. `.config.yaml` in target grill dir
3. Skill defaults

After resolving effective config, write back to `.config.yaml` so next `/grill` in same feature reuses. Note in chat when sticky config loaded: `loaded sticky config: loops=2, threshold=0.9`.

Format:

```yaml
loops: 3
threshold: 0.85
sev2_threshold: 0.95
dry_run: false
base: main
max_fixes_per_turn: null
kai: auto
```

User can hand-edit `.config.yaml` between runs. Skill respects it.

To reset: delete `.config.yaml` or pass `--no-sticky` (skill ignores file for that invocation, does not write back).

## Loop control

Loop runs up to `loops` turns (default 3, configurable). Each turn:

1. `git diff <base>...HEAD` → review
2. Score every finding (sev + conf)
3. Write `NN-run.md` with all findings + dispositions
4. Apply `auto-fix` items (edit files only — no stage/commit/push)
5. Decide: continue or stop

**Continue to next turn** when ANY `auto-fix` was applied this turn (re-review needed to confirm fixes didn't introduce new issues).

**Stop loop** when:
- Zero `auto-fix` dispositions this turn (nothing actionable left), OR
- Turn `loops` complete (limit hit), OR
- `--dry-run` mode (always stops after run 01), OR
- Refusal condition tripped mid-loop (see Refusal cases)

Sev-5 items do NOT block the loop — they're flagged in `final.md` and execution continues fixing other items.

## Review categories

| Category | Look for |
|---|---|
| Logic | edge cases, off-by-one, null/empty, wrong branch, dead paths |
| Concurrency | races, shared state, missing locks, async ordering |
| Tests | missing coverage, untested error paths, mocks hiding bugs |
| API contracts | breaking signature / return shape / error code / status changes |
| Security | injection (SQL/shell/template), authn/authz holes, secrets in logs, PII |
| Performance | N+1, missing indexes, hot loops, unbounded growth, leaks |
| Data | migration safety, backfill order, rollback path, replica lag |
| Generated output | script emits data (TSV/CSV/JSON/SQL/mutations) → inspect the OUTPUT, not just the code. Column shift from unescaped delimiters, NaN/null emission, empty delete/rollback lists, truncate-before-read (open-for-write before content read), doubled braces in templated SQL, wrong constant values, null in required fields |
| Errors | swallowed exceptions, broad except, missing retry/timeout |
| Operability | new env vars w/o defaults, missing flag gates, missing observability |

### Generated-output rule

Diff touches a script that emits data artifacts (converters, generators, mutation builders, exporters): reviewing the code is NOT sufficient — these bugs produce valid-looking output. Run the script against a sample/fixture input (its own `--dry-run` / sample mode if present) and inspect output shape: column count + order, null/NaN density, list lengths (empty delete list = sev-5 candidate), required-field presence. No sample input available → `flag-user` with what's needed to verify. Never score a generated-output finding above 0.84 without having looked at actual output.

## Kai preflight

Predicts whether Recharge's CI reviewer blocks the MR, before it is pushed.

**Enabled** when `git remote get-url origin` contains `gitlab.rechargeapps.net`, unless `--no-kai`. `--kai` forces on for any repo. Disabled → skip K1-K5 entirely and emit no Kai sections.

Kai's CI gate approves only at `must_fix == 0`. Two things raise it:

1. any finding labeled `Must fix`
2. any finding carrying a `**File:**` / `**Issue:**` marker with NO `Must fix` / `Should fix` / `Advisory` keyword — a deterministic backstop in kai's gate, so an unlabeled finding blocks just as hard as a real one

### K1 — size gate (before turn 1)

Count from `git diff --numstat <base>...HEAD`: files = line count, lines = sum of added + deleted.

| | Files | Lines |
|---|---|---|
| Warn | > 30 | > 600 |
| Block | > 75 | > 2000 |

**Block** → abort before any review turn. Write `final.md` with `termination: kai-size-block`, rating `BLOCK`, and a concrete split proposal: group changed paths by top-level dir, name each proposed piece. Kai refuses to review at this size — splitting is the only fix, a review pass here is wasted.

**Warn** → record in `final.md`, continue.

### K2 — load references

Resolve in order, first hit wins:

1. `<project_root>/.claude/skills/review-code/SKILL.md` — repo owns its review (kai DEFER mode). This file **replaces** the reference set below. Apply it instead and note `defer: <path>` in final.md.
2. `~/.claude/kai/plugins/kai/skills/review-code/references/index.md`

From the index, apply every entry whose `**Paths:**` globs match a changed file. Entries with no `Paths:` always apply. Skip `**Category:** dapr` entries unless the repo is a dapr repo (has `deploy/` plus `**/consumers/**` or `**/handlers/**`).

Read each matched reference and fold its checks into the turn's review. Neither path resolves → note `kai references unavailable` in final.md, run K3-K5 anyway (labeling and verdict still work).

Also read the repo's own `CLAUDE.md` for designated high-risk files. Diff touches one → sev-3 finding naming any missing MR requirement (post-deploy monitoring plan, QA instructions, revert MR).

### K3 — label every finding

Every finding carries a Kai label next to sev/conf. Unlabeled is the failure mode kai's backstop catches.

| Grill sev | Kai label |
|---|---|
| 5, 4 | Must fix |
| 3 | Should fix |
| 2, 1 | Advisory |

Refuted findings get no label — dropped, not reported.

### K4 — checks outside the category table

- **Unrelated changes** — hunk not serving the branch's stated purpose (dep bump, rename, reformat bundled with a feature). sev-3, disposition `flag-user`, never auto-fix. Name the split.
- **Risk assessment** — scored once per run, not per finding:
  - Severity: `Critical` (checkout, charge processing, payment collection) | `Major` (subscriptions, customer portal, orders, billing) | `Minor` (memberships, rewards, notifications) | `No Incident` (tooling, admin views, logging, background jobs)
  - Likelihood: `Probable` | `Occasional` | `Remote` | `Improbable`. Raised by: no test coverage on changed paths, downstream behavior not understood, no observability plan, large mixed diff. Lowered by: beta flag, thorough tests, log-only mode, small focused diff.
  - Risk reducer, only when one actually applies: beta flag, log-only mode, store setting, smaller changeset. None apply → say so.

### K5 — predicted verdict

`must_fix` = findings still labeled `Must fix` when the loop ends. Auto-fixed ones do not count.

`must_fix == 0` → `would approve`. Otherwise `would block`, and final rating is `BLOCK`.

---

## Steps

1. **Parse args** (see Arguments). Reject invalid values terse.
2. **Resolve output dir** (active feature or timestamp fallback). Create if missing.
3. **Load sticky config** from `<dir>/.config.yaml` if present. Merge: CLI > sticky > defaults.
4. **Determine base branch**:
   - `--base` arg if passed
   - Else project CLAUDE.md `mr_base_branch: <branch>`
   - Else git remote default
   - Else ask (main / master / stage / develop)
5. **Refusal check** (see Refusal cases). Bail out terse if tripped. Then **Kai preflight** if enabled: K1 size gate (block → abort per K1), then K2 reference load.
6. **Write sticky config** back to `<dir>/.config.yaml` (unless `--no-sticky`).
7. **Loop turn N = 1**:
   a. `git diff <base>...HEAD`
   b. Review each change as skeptical staff engineer. Diff includes data-emitting scripts → apply Generated-output rule (run on sample, inspect output). Kai preflight on → also apply the K2 references and the K4 checks.
   c. Candidate findings sev ≥ 3 → Verification pass (refute before score). Record evidence or refutation.
   d. For each surviving finding: assign category, severity, confidence, evidence, file:line, problem, fix. Kai preflight on → also assign a Kai label per K3.
   e. Determine disposition via matrix (respect `T_main`, `T_sev2`, `--dry-run`)
   f. If `max_fixes_per_turn` set: keep first N `auto-fix` items, demote rest to `deferred`
   g. Write `0N-run.md` (template below)
   h. If NOT dry-run: apply all `auto-fix` items via Edit. Re-run `py-check` / `ts-check` if relevant files touched. Run tests covering the edited files (scoped, not full suite) — fix broke a test → revert that fix, demote finding to `flag-user`.
   i. If any auto-fix applied AND N < `loops` AND not dry-run: increment N, goto 7a.
8. **Write `final.md`** (template below).
9. **Report to user**: one-line rating + file path to `final.md`. Nothing else.

## File templates

### `NN-run.md` frontmatter

```yaml
---
type: grill-run
status: complete
feature: {name or "none"}
run: N
loop_turn: "N/3"
base_branch: {base}
lifecycle: candidate
---
```

### `NN-run.md` body

```markdown
# Grill Run 0N

Rating: SHIP IT | NEEDS WORK | BLOCK

## Findings

### 1. [sev:4 conf:0.92] src/auth/jwt.py:88 — token expiry uses `<` not `<=`
- category: logic
- disposition: auto-fix
- evidence: read jwt.py:80-95 + caller session.py:41; expiry compared exclusive, boundary second rejected
- fix: change `<` to `<=` on L88

### 2. [sev:5 conf:0.98] src/db/migrate.py:42 — no rollback path
- category: data
- disposition: FLAG-HUMAN
- fix: write down migration

### 3. [sev:3 conf:0.72] src/api/orders.py:140 — unbounded list returned
- category: performance
- disposition: skip (conf<0.85)
- fix: cap at 1000 or paginate

## Refuted (considered, disproven)

- src/api/orders.py:97 — suspected N+1; refuted: query batched via dataloader (orders.py:60)

## Loop turn decision

- auto-fixed: 1
- flagged-human: 1
- flagged-user: 0
- skipped low-conf: 1
- report-only: 0
- refuted: 1
- continue to run 02: yes
```

### `final.md` frontmatter

```yaml
---
type: grill-final
status: complete
feature: {name or "none"}
runs_completed: N
termination: all-clear | loop-limit | refusal | kai-size-block
final_rating: SHIP IT | NEEDS WORK | BLOCK
kai_preflight: true | false
kai_must_fix: N
kai_size: ok | warn | block
lifecycle: candidate
---
```

### `final.md` body

```markdown
# Grill Final

Rating: NEEDS WORK
Runs: 2/3
Termination: all-clear

## Kai preflight

Predicted CI verdict: **would block — must_fix=1**
Size: 12 files / 340 lines (ok)
References applied: core-principles, test-coverage, react-hooks-deps
Risk: Severity Major — touches subscription cancel path. Likelihood Occasional — new validation branch, tests cover happy path only.
Risk reducer: beta flag — change alters cancel behavior for all stores.

| File:Line | Kai label | Sev | Status |
|---|---|---|---|
| src/db/migrate.py:42 | Must fix | 5 | still open |

(Omit this whole section when Kai preflight is off.)

## Fixed across runs

| Run | File:Line | Sev | Conf | Category | Fix applied |
|---|---|---|---|---|---|
| 01 | src/auth/jwt.py:88 | 4 | 0.92 | logic | `<` → `<=` |
| 02 | src/api/orders.py:55 | 3 | 0.88 | logic | added null guard |

## Flagged for human (sev-5)

| File:Line | Sev | Conf | Category | Problem | Suggested fix |
|---|---|---|---|---|---|
| src/db/migrate.py:42 | 5 | 0.98 | data | no rollback | write down migration |

## Flagged for user (sev-4, low conf)

| File:Line | Sev | Conf | Category | Problem | Suggested fix |
|---|---|---|---|---|---|

## Remaining sev≥3 (not auto-fixed)

| File:Line | Sev | Conf | Category | Reason |
|---|---|---|---|---|

## Deferred (over max-fixes-per-turn cap)

| File:Line | Sev | Conf | Category | Suggested fix |
|---|---|---|---|---|

## Skipped low-confidence

| File:Line | Sev | Conf | Category | Note |
|---|---|---|---|---|

## Reported-only (sev 1-2)

- src/util/x.py:12 sev:1 — duplicate of helper
```

## Final rating logic

- `BLOCK` — any sev-5 flagged-human OR any remaining sev-4 not fixed OR Kai preflight size-block
- `NEEDS WORK` — any remaining sev-3 OR sev-4 flagged-user
- `SHIP IT` — no remaining sev≥3, no flagged-human, no flagged-user

## Chat reply

After loop ends, reply ONLY:

```
Grill complete. Rating: <rating>. Runs: N/3.
Kai: would block — must_fix=N
final.md: <path>
```

Omit the `Kai:` line when preflight is off.

No additional summary in chat. User reads `final.md`.

## Refusal cases

Refuse to start (or abort mid-loop) when:
- Branch has uncommitted changes (commit first — grill reviews committed state, then applies new edits that user reviews before commit)
- Tests changed but not run
- New behavior added with zero new tests
- Migration added without rollback documented

State refusal reason terse, write a stub `NN-run.md` with `status: refused` + reason in frontmatter. User decides.

## Hard rules

- NEVER `git add`, `git commit`, `git push`, or `git stash`. Edit files only.
- Auto-fix edits ONLY files already in the diff, plus new test files. Fix requires touching an untouched file → `flag-user`.
- NEVER score conf ≥ 0.85 without recorded evidence.
- NEVER auto-fix sev-5 — always flag-human.
- NEVER auto-fix sev 3-4 below `T_main` (default 0.85).
- NEVER auto-fix sev-2 below `T_sev2` (default 0.95).
- NEVER auto-fix sev-1 — report only.
- NEVER mutate `final.md` after first write — immutable end-of-loop artifact.
- NEVER apply edits in `--dry-run` mode.
- Demoted (over `max_fixes_per_turn` cap) items must surface in final.md `Deferred` section.
- Kai preflight on → NEVER emit a finding without a Kai label. Unlabeled is what trips kai's gate.
- NEVER auto-fix an unrelated-change finding — splitting the branch is the user's call.
- NEVER continue past a K1 size block. A review at that size is wasted work; kai will not run one either.
