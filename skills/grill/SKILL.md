---
name: grill
description: 'Adversarial pre-ship review loop for larger/complex changes. Runs `greptile review --json` on local branch committed diff vs base (Recharge GitLab + RechargePayments / skio-org GitHub repos; any other remote gets grill''s own review instead), triages each finding as skeptical staff engineer, scores it (severity 1-5, confidence 0-1), auto-fixes high-confidence sev 2-4 items per dual-axis matrix, flags sev-5 for human, loops up to N turns (default 3, configurable 1-5). Supports --loops, --threshold, --sev2-threshold, --dry-run, --base, --max-fixes-per-turn. Sticky per-feature config at .config.yaml. Outputs per-run artifacts under .giantmem/features/{feature}/grill/. Auto-fires when user says "grill me", "grill this", "tear it apart", "don''t let me ship until", "adversarial review", "be skeptical", or invokes /grill. Given a GitLab MR or GitHub PR URL (`/grill <mr-url>`, "grill this MR", "grill this PR", "adversarial review of <mr-url>"), runs read-only MR mode instead: seeds from Greptile''s MR threads, verifies the MR description''s claims against the code, refutes and scores, prints findings. MR mode never edits, writes files, or posts.'
context: fork
model: sonnet
background: false
---
<!-- caveman:compressed -->

Adversarial pre-ship review LOOP. Turn 1: Greptile CLI reviews committed diff on Recharge repos; any other remote, grill self-reviews it (see Scope). Skeptical staff engineer refutes + scores each finding, auto-fixes confident items, surfaces uncertain/fatal items, re-checks own fixes. Max 3 turns.

NEVER commits. NEVER pushes. NEVER stages. Edits files only.

## When to use

- **This skill**: local branch, pre-push. Catch + auto-tighten before MR opened.
- **This skill, MR mode** (`/grill <mr-url>`): posted GitLab MR, yours or someone else's. Reviewer pass, read-only. glmon review poller runs it.
- **kai:review-code**: kai template review of a posted GitLab MR.
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

## Scope

Greptile is Recharge's tool: it reviews Recharge-owned repos only. `git remote get-url origin` picks turn 1's finding source:

| origin | Turn 1 source |
|---|---|
| host `gitlab.rechargeapps.net` | Greptile |
| `github.com`, org `RechargePayments` (Recharge) or `skio-org` (Skio) | Greptile |
| anything else: personal GitHub, other hosts, no `origin` | self-review |

Org = first path segment after the host, from `git@github.com:<org>/...` or `https://github.com/<org>/...`, matched case-insensitive. A personal fork of a Recharge repo is out of scope.

Self-review (out of scope): skip Greptile preflight + run. Read `git diff <base>...HEAD` whole, plus callers and definitions of changed symbols; sweep the Review categories table as checklist; every candidate `source: self-review`. Downstream unchanged: Verification pass, scoring, matrix, auto-fix, loop. run.md + final.md say `Greptile: n/a (out of scope: <host>/<org>)`, frontmatter `reviewer: self`, `greptile_confidence: n/a`.

In scope + Greptile unavailable (not installed, signed out, repo not connected, review failed) → stop and report per Preflight. Self-review is the out-of-scope path, never a fallback.

## Greptile review

In-scope repos only (see Scope). Turn 1 finding source is the Greptile CLI (`greptile-cli` skill has command + output details). Grill triages, scores, fixes, and tests. Greptile does not run code, so the Generated-output rule and Refusal cases stay grill's own.

### Preflight (step 5)

- `command -v greptile` empty → stop, report broken install or `PATH`.
- `greptile whoami | grep -q '^Not signed in'` → stop, tell user to run `greptile login` (interactive browser flow, never run it). `whoami` exits 0 when signed out; gate on text.
- `this repository is not connected to Greptile yet` → stop, tell user to run `greptile init` or add the repo in the dashboard (never run it: registers the repo with the org).
- No fallback. In-scope repo + Greptile unavailable → stop and report. NEVER substitute a Claude-only review.

### Run (turn 1)

`greptile review -b <base> --json`. Base unqualified (`main`, not `origin/main`). Read stdout directly; NEVER redirect into the worktree (dirty tree trips the uncommitted-changes refusal on re-run). Takes about a minute: no short timeout, never start a second review while one runs.

Exit 0 is normal whatever the findings. Non-zero = review did not finish. Recover first: `greptile review status --json` (exit 3 → wait 30s, retry), then `greptile review show <runId> --json`. Recovery fails → abort with stub `01-run.md` (`status: refused`, stderr line as reason). `every committed change was held back` → same abort; `--include` only when user asks.

### Map comments to findings

| Greptile field | Grill field |
|---|---|
| `path` + `startLine` | file:line. `side: "old"` → anchors base version, read `git show <base>:<path>` |
| `body` | problem |
| `suggestion` | proposed fix. Check it fits surrounding code; never apply blind |
| `severity` | seed sev: P0 → 4-5, P1 → 3-4, P2 → 1-3. Final sev from own read |
| `securityIssue: true` | triage first, seed sev ≥ 4 |
| `id` | `source: greptile <id> <severity>` in run.md |
| `category`, `verifiedEvidence` | ignore (always `"comment"` / `null`) |

Confidence is grill's own, per evidence gate + Verification pass. Greptile asserts; grill refutes. Advisory comment (no concrete failure: style, naming, "consider adding X", doc request) → sev 1, report-only. Findings from grill's own checks carry `source: generated-output | self-review`.

Review-level `confidence` (1-5) goes in run.md and final.md, never drives disposition. Exception: `confidence` ≤ 3 with zero surviving findings → read `summary` + `confidenceReasoning`; concrete failure the comments never raised → triage it as a finding.

### Turns 2+

Greptile excludes uncommitted changes, so it cannot see auto-fix edits. Turn N>1 = self-review of fix hunks (Loop control). Greptile re-checks fixes when user commits and re-runs `/grill`; prior-finding status (step 7b) covers them.

## MR mode

First arg matches `https://<host>/<ns/project>/-/merge_requests/<iid>` or `https://github.com/<owner>/<repo>/pull/<n>` → MR mode. Review the posted MR as reviewer, not author. "MR" below covers both; each Fetch call has its `gh` twin. A GitHub PR outside the orgs `skio-org` / `RechargePayments` has no Greptile: review it on the `greptile: none` path.

Differs from local mode:

- Read-only. Implies `--dry-run`, one turn. Skip output dir, sticky config, every file write. Chat reply is the deliverable: glmon poller stores it as the review file.
- Refusal cases become findings, never refusals: new behavior with zero tests → sev 3 tests, migration without rollback → sev 4 data.
- NEVER write to the MR: no notes, no `@greptile review` (GitHub `@greptileai review`), no approval or review submission. Posting is `review-comment`, on request.

### Fetch

`<enc>` = URL-encoded `ns/project`.

- `glab api "projects/<enc>/merge_requests/<iid>"` → head `sha`, `source_branch`, `title`, `description`.
- `glab mr diff <iid> --repo <ns/project>` → diff.
- `glab api --paginate "projects/<enc>/merge_requests/<iid>/discussions?per_page=100"` → Greptile threads.
- Files at head (Verification pass reads callers + definitions beyond hunks): `glab api "projects/<enc>/repository/files/<url-encoded path>/raw?ref=<sha>"`. Cwd is a clone of the same repo → `git fetch origin <source_branch>`, then `git show <sha>:<path>`.
- Diff between two shas: `glab api "projects/<enc>/repository/compare?from=<a>&to=<b>"`.

GitHub twins, `<o/r>` from the URL:

- `gh pr view <n> -R <o/r> --json headRefOid,headRefName,title,body` → head, branch, title, description. The Greptile summary is in `body` (frost) or in a bot issue comment (`gh api repos/<o>/<r>/issues/<n>/comments`, RechargePayments repos); read both.
- `gh pr diff <n> -R <o/r>` → diff.
- Threads: `gh api graphql -f query='{ repository(owner:"<o>", name:"<r>") { pullRequest(number:<n>) { reviewThreads(first:100) { nodes { isResolved isOutdated comments(first:50) { nodes { author { login } body path line url } } } } } } }'`.
- Files at head: `gh api "repos/<o>/<r>/contents/<path>?ref=<sha>" -H "Accept: application/vnd.github.raw"`; a local clone works the same as on GitLab.
- Diff between two shas: `gh api "repos/<o>/<r>/compare/<a>...<b>"`.

### Seed findings

Greptile author: `author.username == "greptile"`; GitHub `author.login == "greptile-apps"` (`greptile` skill, Greptile facts).

- Summary note (`<!-- greptile_summary -->`; GitHub: the same markers in the PR `body` or in the bot's issue comment): score from `<!-- greptile_confidence_score:N -->`, reviewed sha from its "Last reviewed commit" `/commit/<sha>` link.
- Each unresolved Greptile DiffNote → candidate. `position.new_path` + `new_line` = file:line (`old_line` only → base side). GitHub: each thread with `isResolved: false` whose first comment is the bot's; `path` + `line` = file:line. Bold title + body = problem. ```` ```suggestion ```` block = proposed fix, never applied blind. Badge `badges/p0|p1|p2.svg` seeds sev per the mapping table above. Resolved threads: skip.
- `<!-- greptile_outside_diff -->` note: each item a candidate (GitHub: same marker wherever it appears; not observed on frost).
- Reviewed sha != head → Greptile stale. Status each seeded finding at head (RESOLVED / STILL OPEN), then self-review `<reviewed>..<head>` with the Review categories table, `source: self-review`.
- No summary note (GitHub: no marker in body or comments; Greptile reviews off for the repo, a personal org, or not run yet) → self-review the full diff with the Review categories table, header says `greptile: none`. Only MR-mode path where grill reviews without Greptile.
- Prompt names a previously reviewed sha (glmon re-review) → lead with what changed in `<prev>..<head>`.

### Claim check

Description = hypothesis. Test it.

1. Extract every falsifiable claim: behavior changes, scope limits ("refactor only", "no behavior change", "tests only"), coverage ("added tests for X"), negative claims ("does not affect Y"). Vague prose is not a claim.
2. Map each claim to the diff region that should prove it. No region → claim-shaped hole, a finding.
3. Verdict: `confirmed` | `wrong` | `misleading` (true, omits material detail; hunt for it) | `partial` | `unverifiable` (name what would settle it).
4. "No behavior change", "pure refactor", "internal only", "no user impact" are suspect. Trace one concrete call path through changed code before accepting.

`wrong` / `misleading` / `partial` → finding (`source: claim`) only when the gap changes what a reviewer would do. `confirmed` earns no line.

### Score + report

Verification pass + scoring as local mode. Nothing fixed; dispositions only drive rating. Rating for reviewer: SHIP IT = approve, NEEDS WORK = comment, BLOCK = request changes.

Reply ONLY:

```
Rating: NEEDS WORK · greptile 4/5 @ a1b2c3d4 (head e5f6a7b8, stale)
Claims: 5 checked, 1 wrong, 1 misleading

## Findings
- [sev:4 conf:0.92] src/auth/jwt.py:88: expiry compares with `<`, rejects boundary second. Use `<=`. (greptile)
- [sev:3 conf:0.88] says "no behavior change"; src/api/orders.py:140 drops the 1000-row cap. (claim)
- Nits: src/util/x.py:12 duplicate helper; src/api/orders.py:20 unused import

## Refuted
- src/api/orders.py:97: greptile N+1; batched via dataloader at orders.py:60

## Held
"adds retry" and "tests cover cancel path" verified; money/auth paths untouched.
```

`greptile: none` replaces the greptile segment when no summary note. One line per finding, most severe first. Sev 1-2 collapse into one `Nits:` line. Nothing above nit → two lines: what was verified, and that it came back clean.

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

Finding survives refutation → score with evidence. Refuted → drop (note in run.md `refuted:` list, one line each — reader sees what was considered).

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
| `<mr-url>` | positional | none | GitLab MR or GitHub PR URL | MR mode (see MR mode). Other flags ignored. |
| `--loops N` | int | 3 | 1-5 | Max loop turns. >5 rejected (diminishing returns + churn risk). |
| `--threshold X` | float | 0.85 | 0.50-1.00 | Conf cutoff for sev 3-4 auto-fix. |
| `--sev2-threshold X` | float | 0.95 | 0.50-1.00 | Conf cutoff for sev-2 auto-fix. |
| `--dry-run` | flag | off | — | Score + report only. No edits, no loops past run 01. |
| `--base <branch>` | string | auto | any ref | Override base branch detection. |
| `--max-fixes-per-turn N` | int | unlimited | 1+ | Hard cap on edits applied per turn. Extra `auto-fix` items demoted to `deferred` and surfaced in final.md. |

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
```

User can hand-edit `.config.yaml` between runs. Skill respects it.

To reset: delete `.config.yaml` or pass `--no-sticky` (skill ignores file for that invocation, does not write back).

## Loop control

Loop runs up to `loops` turns (default 3, configurable). Each turn:

1. N=1: in scope, `greptile review -b <base> --json` + `git diff <base>...HEAD` for context → triage (see Greptile review); out of scope, self-review the diff (see Scope); N>1: `git diff` (prior turn's auto-fix edits) → self-review
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

Greptile `category` carries no signal; assign one from this table during triage. Also the checklist for turn N>1 self-review.

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
| Unrelated changes | hunk not serving the branch's purpose (dep bump, rename, reformat bundled with a feature). sev 3, `flag-user`, name the split |

### Generated-output rule

Diff touches a script that emits data artifacts (converters, generators, mutation builders, exporters): reviewing the code is NOT sufficient — these bugs produce valid-looking output. Run the script against a sample/fixture input (its own `--dry-run` / sample mode if present) and inspect output shape: column count + order, null/NaN density, list lengths (empty delete list = sev-5 candidate), required-field presence. No sample input available → `flag-user` with what's needed to verify. Never score a generated-output finding above 0.84 without having looked at actual output.

---

## Steps

1. **Parse args** (see Arguments). Reject invalid values terse. First arg is an MR URL → follow MR mode, skip steps 2-9.
2. **Resolve output dir** (active feature or timestamp fallback). Create if missing. `<dir>/final.md` already exists → earlier grill: move every `*-run.md` and `final.md` into `<dir>/prev-{YYYYMMDD-HHMM}/`, then read the archived `final.md` and collect every finding outside `Fixed across runs` as `prior` (file:line, sev, problem).
3. **Load sticky config** from `<dir>/.config.yaml` if present. Merge: CLI > sticky > defaults.
4. **Determine base branch**:
   - `--base` arg if passed
   - Else project CLAUDE.md `mr_base_branch: <branch>`
   - Else git remote default
   - Else ask (main / master / stage / develop)
5. **Refusal check** (see Refusal cases). Bail out terse if tripped. Then **Scope check** (see Scope): in scope → **Greptile preflight** (see Greptile review), fails → stop and report; out of scope → self-review, no Greptile.
6. **Write sticky config** back to `<dir>/.config.yaml` (unless `--no-sticky`).
7. **Loop turn N = 1**:
   a. N=1, in scope: run `greptile review -b <base> --json` (see Greptile review); read `git diff <base>...HEAD` for context. N=1, out of scope: self-review `git diff <base>...HEAD` (see Scope). N>1: `git diff` (uncommitted auto-fix edits from turn N-1) plus surrounding lines; review only those hunks for regressions and status prior findings against the working tree. Do not re-review the committed diff.
   b. `prior` non-empty → status each prior finding first, with evidence: RESOLVED (head no longer exhibits it, cite file:line), STILL OPEN, or REGRESSED (fixed in the earlier grill, back in this diff). STILL OPEN and REGRESSED re-enter as findings and score normally. Then map every Greptile comment to a candidate finding (see Greptile review), or collect self-review candidates when out of scope; N>1: self-review the fix hunks as skeptical staff engineer. Diff includes data-emitting scripts → apply Generated-output rule (run on sample, inspect output).
   c. Candidate findings sev ≥ 3 → Verification pass (refute before score). Record evidence or refutation.
   d. For each surviving finding: assign category, severity, confidence, evidence, file:line, problem, fix.
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
loop_turn: "N/{loops}"
base_branch: {base}
lifecycle: candidate
---
```

### `NN-run.md` body

```markdown
# Grill Run 0N

Rating: SHIP IT | NEEDS WORK | BLOCK
Greptile: confidence 4/5, 3 comments (run 01 only)

## Findings

### 1. [sev:4 conf:0.92] src/auth/jwt.py:88 — token expiry uses `<` not `<=`
- source: greptile comment-7312 P1
- category: logic
- disposition: auto-fix
- evidence: read jwt.py:80-95 + caller session.py:41; expiry compared exclusive, boundary second rejected
- fix: change `<` to `<=` on L88

### 2. [sev:5 conf:0.98] src/db/migrate.py:42 — no rollback path
- source: greptile comment-7315 P0
- category: data
- disposition: FLAG-HUMAN
- fix: write down migration

### 3. [sev:3 conf:0.72] src/api/orders.py:140 — unbounded list returned
- source: greptile comment-7318 P2
- category: performance
- disposition: skip (conf<0.85)
- fix: cap at 1000 or paginate

## Refuted (considered, disproven)

- src/api/orders.py:97 — suspected N+1; refuted: query batched via dataloader (orders.py:60)

## Prior findings (from prev-20260925-1410)

- src/db/migrate.py:42 sev:5 — STILL OPEN
- src/api/orders.py:140 sev:3 — RESOLVED: paginated at L138-152

(Omit when no earlier grill in this dir.)

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
termination: all-clear | loop-limit | refusal
final_rating: SHIP IT | NEEDS WORK | BLOCK
reviewer: greptile | self
greptile_confidence: 1-5 | n/a
prior_grill: prev-{YYYYMMDD-HHMM} | none
lifecycle: candidate
---
```

### `final.md` body

```markdown
# Grill Final

Rating: NEEDS WORK
Runs: 2/3
Termination: all-clear
Greptile: confidence 4/5. Auto-fixes not Greptile-checked; commit, re-run `/grill`.

## Prior findings

| File:Line | Sev | Status | Evidence |
|---|---|---|---|
| src/db/migrate.py:42 | 5 | STILL OPEN | no rollback path at head |
| src/api/orders.py:140 | 3 | RESOLVED | paginated at L138-152 |

(Omit when `prior_grill: none`.)

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

- `BLOCK` — any sev-5 flagged-human OR any remaining sev-4 not fixed
- `NEEDS WORK` — any remaining sev-3 OR sev-4 flagged-user
- `SHIP IT` — no remaining sev≥3, no flagged-human, no flagged-user

## Chat reply

After loop ends, reply ONLY:

```
Grill complete. Rating: <rating>. Runs: N/{loops}.
Greptile re-check: commit fixes, re-run /grill
final.md: <path>
```

Omit the `Greptile re-check:` line when zero auto-fixes applied or the repo is out of scope.

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
- NEVER auto-fix an unrelated-change finding — splitting the branch is the user's call.
- Local mode, in-scope repo: turn 1 findings come from `greptile review --json`. Greptile unavailable → stop and report, NEVER substitute a Claude-only review.
- Local mode, out-of-scope repo: turn 1 is grill's self-review (see Scope). NEVER run `greptile review` or `greptile init` there.
- MR mode: NEVER write to the MR or the filesystem. No notes, approvals, `@greptile review`, edits, or files.
- NEVER write Greptile output into the worktree.
- NEVER apply a Greptile `suggestion` without checking it fits the surrounding code.
