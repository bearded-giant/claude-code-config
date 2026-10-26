---
description: Auto-address open review threads on the MR for the CURRENT worktree branch. Scoped to one MR — the one whose source branch == current branch. Idempotent — safe to /loop inside a worktree. Trigger phrases - "babysit this MR", "address review comments", "/babysit", or invoked via `/loop 5m /babysit`. Ends its own loop once the pipeline is green and, on Greptile MRs, Greptile has reviewed the head.
argument-hint: "[worktree path] [signoff <n>[: plan edits]]..."
allowed-tools: Bash, Read, Edit, Write, Grep, Glob, Skill, ToolSearch, ScheduleWakeup, CronList, CronDelete
context: fork
background: false
---

Address open review comments on the MR for **this** worktree's branch.

Runs as a forked subagent: a `/loop` fire costs a fresh context instead of re-reading the host session's (an idle run was 2 requests at 300-730k tokens each). The fork sees this command and its arguments, never the session's chat, so sign-offs arrive as arguments.

## Worktree scoping model

This command is worktree-scoped by design. One loop handles exactly one MR — the one matching the current branch of its worktree.

Arguments: `$ARGUMENTS`. First token, when it is a path, is the worktree: start every Bash call with `cd <path> &&`, so one session can loop several MRs across repos (`/loop 5m /babysit <path>` per MR). No path → the session cwd. Each `signoff <n>` that follows signs off deferred thread `n` (numbered as in the last output); text after `signoff <n>:` up to the next `signoff` edits that thread's plan.

## Preconditions

- `glab auth status` succeeds (skip + log if not)
- In a git repo with a GitLab remote (skip + log if not)
- Current branch is **not** `main` / `master` / `stage` — if it is, exit clean with `not on a feature branch — nothing to babysit`
- `git status --porcelain` is clean — if dirty, **abort** and report (do not stash user work)

## Steps

1. **Resolve current branch and MR** —
   ```
   BRANCH="$(git branch --show-current)"
   glab mr list --source-branch="$BRANCH" -F json   # opened is the default state
   ```
   - Zero results → `glab mr list --source-branch="$BRANCH" --merged -F json`. Merged MR found → run the `doit-prune` skill with `--mr <iid> --auto`, stop the loop (step 9 **Stop loop**), exit: `<repo>!<iid> merged, doit <n> closed` plus the MR `web_url` on its own line. None → exit clean: `no open MR for branch <BRANCH>`
   - Multiple results → exit clean: `ambiguous: <n> MRs from this branch — manual triage needed`
   - One result → proceed. Capture `iid`, `project_id`, `web_url`.

2. **Fetch unresolved discussions**:
   ```
   glab api "projects/<project_id>/merge_requests/<iid>/discussions" --paginate
   ```
   Keep a thread if `system=false` AND it still requests a change (`resolved=false`, or a `resolvable=false` MR-level note that asks for one) AND its last non-system note author is someone other than you. Skip a thread whose last note is yours — you are mid-conversation, leave it. Exception: Greptile edits its `<!-- greptile_outside_diff -->` note in place on each re-review, so keep a thread whose first note is by `greptile` and has `updated_at` later than the `created_at` of your last note in that thread. Never keep notes carrying `<!-- greptile_summary -->` or `<!-- greptile_auto_approval_sha:` — they restate the inline threads; step 9 reads them.

   **Deferred state** lives in `$(git rev-parse --git-dir)/babysit-<iid>.json`: `{discussion_id: {n, reason, plan, url}}`, plus reserved key `_greptile: {requested_sha, requested_at, rounds}` (step 9). `n` is the thread's number in the output, assigned once (next unused, including for older entries that lack one) and never reused. Skip any kept thread already in it unless this run's arguments sign it off. Zero kept threads → skip to step 9.

   **Never run the sign-off handshake through MR comments.** No `[babysit]` notes, no asking the user to reply on a thread. Deferrals go to the state file and to the output; the user signs off with `/babysit <path> signoff <n>`.

3. **Classify each kept thread** before touching code. Read the thread context (file path + line if present). Bucket into:
   - `signed_off` — a deferred thread whose `n` this run's arguments name (`signoff <n>`, plan edits after the colon). Implement the plan as approved. Highest priority, overrides the buckets below; drop its state-file entry once pushed.
   - `actionable_simple` — rename, typo, missing test case, obvious null check, dead code, lint-style nit. Safe to one-shot.
   - `actionable_complex` — design or refactor request. Split by how concrete the direction is:
     - **concrete direction** (reviewer named the target, e.g. "use request hooks for `internal_chat_api_bp`", "move to its own blueprint") → attempt it, scoped strictly to what was asked.
     - **ambiguous / open question** (e.g. "is this the right layer?", "should this live elsewhere?") → defer: state file + chat, with the open question and 1–3 options. No thread reply.
   - `informational` — "looks good", "nit just FYI", no requested change. Skip.
   - `contradicts_design` — the ask runs counter to a design decision or known reason recorded in the **branch work**: its commits (`git log <base>..HEAD`), the active feature's docs under `.giantmem/` and its handoff (workspace-rules `## Handoff`), or the repo's CLAUDE.md. Do not implement. The thread still gets a one-line decline-with-reason reply (step 6.7). Only use this when a concrete established reason actually exists — never fabricate a rationale to dodge work; absent a real reason, fall back to `actionable_*`.

   Thread author `greptile` that you decline → also run the `greptile` skill's **rule** step; its proposal rides the state file + chat sign-off, never AskUserQuestion. After the final push, run its **sync** step once if the repo has `.greptile/`.

4. **Sync branch first** — once, before any edits:
   ```
   git fetch origin
   git pull --rebase --no-edit
   ```
   On conflict → abort rebase, report `rebase conflict — manual fixup needed` in chat, raise attention (step 7), exit clean.

5. **Plan-gate** each concrete `actionable_complex` thread before editing (`actionable_simple` and `signed_off` skip the gate):
   1. Write a 2–4 step plan from the reviewer's stated direction.
   2. Classify the plan **CLEAN** vs **NEEDS-SIGN-OFF** (moderate bar). NEEDS-SIGN-OFF if the plan would:
      - change a public contract (response code, route, payload shape), **or**
      - alter request/response **precedence or ordering** — e.g. a `before_request` hook that runs ahead of an auth view decorator, middleware reordering, changing which check fires first, **or**
      - touch a repo **High-Risk File** (see the repo's CLAUDE.md High-Risk Files), **or**
      - be unverifiable by existing tests or a trivially-added one.
      CLEAN otherwise — including multi-file moves/renames the test suite already covers.
   3. **NEEDS-SIGN-OFF** → write the plan to the state file, list it in chat, leave the thread **unresolved** with no reply, and **do not touch code**. (The attention signal in step 7 fires at end of run.)

6. **Execute** each CLEAN thread (and every `actionable_simple`). `contradicts_design` threads are handled reply-only per 6.7.
   1. Build the edit, scoped to exactly what was asked — do not expand into adjacent refactors.
   2. Run `py-check` / `ts-check` skill on touched files.
   3. Commit using caveman-commit format. Subject prefix `review:` (e.g., `review: rename foo to bar`). If the repo's commit-msg hook needs a JIRA key, prefix it (derive from branch name or sibling commits). If push is then rejected **by the commit-msg / pre-push policy hook only** (not a non-fast-forward), retry once with `git push --no-verify` — py-check already ran in 6.2.
   4. Push: `git push`
   5. Reply on thread in Bryan's voice (`~/.claude/config/voice.md`; `voice_gate.py` blocks drift):
      - One short, plain sentence per item you actually addressed in this thread. Reviewer note bundles N findings → N bullets; single finding → one sentence, no bullet.
      - Style: `` `foo` handled in tests now ``, `` `_hello_world` guard added ``. One line per item, ~15 words. No preamble ("I have addressed…"), no restating the finding verbatim, no file/doc-path citations (`CLAUDE.md → …`), no justification the reviewer didn't ask for, no sha dump, no blanket paragraph.
      - **Omit** any item you didn't touch (out of scope, silently skipped) — never mention it.
      - For an item you deliberately did **not** do (contradicts a design decision / known reason from the branch work, or you're keeping as-is), add one bullet stating the decision + one reason, nothing more. Examples: `` `app.logger` is the repo standard, leaving as-is for now ``, `` email-in-logs intentional for rollout; TODO already flags it for revisit ``, `schema migration not needed: already handled`.

      Write the body (newline-separated bullets) to `<scratchpad>/reply-<discussion_id>.md`, then:
      ```
      glab api -X POST "projects/<project_id>/merge_requests/<iid>/discussions/<discussion_id>/notes" -F body=@<scratchpad>/reply-<discussion_id>.md
      ```
   6. Resolve thread if `resolvable=true`:
      ```
      glab api -X PUT "projects/<project_id>/merge_requests/<iid>/discussions/<discussion_id>" -f resolved=true
      ```
      MR-level notes (`resolvable=false`) can't be resolved via API — reply only.
   7. **`contradicts_design` threads** — no edit, no commit, no resolve. Skip 6.1–6.4 and 6.6. Post only the decline-with-reason bullet (6.5 decline branch) and leave the thread **unresolved**, so the human can accept or contest the rationale.

7. **Raise or clear attention** — once, at end of every run. If anything is still left for you (NEEDS-SIGN-OFF threads still unresolved, including ones from earlier runs, `actionable_complex` ambiguous, push rejected, pipeline red, rebase conflict), raise it with the total pending count:
   ```
   python3 ~/.claude/hooks/request_attention.py "MR !<iid> (<branch>): <n> thread(s) need your sign-off"
   ```
   Otherwise clear it:
   ```
   python3 ~/.claude/hooks/request_attention.py --clear
   ```
   Raise every run while something is pending: each `/loop` tick clears the flag on submit, and an unchanged reason does not re-notify. Step 9 owns the READY and BLOCKED signals and runs after this.

8. **Pipeline check** — after final push, query:
   ```
   glab api "projects/<project_id>/pipelines?ref=$BRANCH&order_by=updated_at&per_page=1"
   ```
   If pipeline newly red from this push, report `pipeline red after my fix — <job-url>` in chat, raise attention (step 7), and bail. If pipeline green or unrelated red, nothing to report.

9. **Gate** — every run ends here, including zero-thread runs. Decides whether this babysit instance is finished.

   **Greptile-aware** iff step 2's discussions include a note containing `<!-- greptile_summary -->`, or the repo root has `.greptile/` or `greptile.json` (covers a new MR Greptile has not reached yet). Reviewed sha = the `/commit/<sha>` in that note's "Last reviewed commit" line. Read it from step 2's payload, not a fresh fetch, so a review landing mid-run can't mark READY over threads this run never saw. Re-reviews are manual (`@greptile review`), so every push leaves the review stale and blocks auto-approve.

   Inputs: MR head `sha` and `head_pipeline.status` (`glab api "projects/<project_id>/merge_requests/<iid>"`, fetched after the last push), threads still actionable this run, state file `_greptile`. Green = `success`, `manual`, `skipped`, or no pipeline in a repo without `.gitlab-ci.yml`. No pipeline with `.gitlab-ci.yml` = not created yet, so neither. Red = `failed`, `canceled`.

   First match wins:

   | State | Condition | Action |
   |---|---|---|
   | BLOCKED | MR is Draft without `[babysit-ok]`, pipeline red on head, rebase conflict, push rejected, "greptile due" with `_greptile.rounds >= 3`, or `requested_sha == head` and `requested_at` > 15 min ago with no review | raise attention (step 7) with the reason, **stop loop** |
   | working | actionable threads left past the 5-thread cap | continue |
   | sign-off | deferred state-file threads remain | continue, slow cadence |
   | greptile due | greptile-aware, head != reviewed sha, head != `requested_sha`, and a summary note exists or the MR is 15+ min old | post via the `greptile` skill's **review** mode (babysit run = user authorization, no ask). Set `requested_sha=head`, `requested_at=now`, `rounds+=1`. Continue |
   | waiting | pipeline neither green nor red, `requested_sha == head` and not yet reviewed, or greptile-aware with no summary note on an MR under 15 min old (Greptile reviews on open) | continue |
   | READY | pipeline green on head, head == reviewed sha (or not greptile-aware) | run the `doit-prune` skill with `--mr <iid> --auto` (no owed merge item: glmon and `giantmem mr list` show READY MRs), raise attention `<repo>!<iid> ready: pipeline green, greptile <score>/5[, approved][, <n> declined threads await you]` with the MR `web_url` on its own line as the last line, **stop loop**. Count = your declined threads still unresolved; they block merge where the MR's `blocking_discussions_resolved` is false |

   Greptile's new findings arrive as fresh unresolved discussions; the next run handles them through steps 2-8 like any reviewer's. Approved = a note with `<!-- greptile_auto_approval_sha:<head> -->`. A sub-5 score with no open Greptile threads is still READY; report the score.

   "Greptile due" fires while the pipeline runs, so review and CI overlap. A red pipeline from babysit's own push is already BLOCKED via step 8, so that is the only path that wastes a Greptile run.

   **Stop loop** (deferred tools, load via ToolSearch first):
   - interval `/loop <n> /babysit` → `CronList`, then `CronDelete` the job whose prompt is `/babysit` plus this run's path (`/babysit` or `/babysit <path>`), never another path's job. A fork sees and deletes the session's jobs.
   - dynamic `/loop /babysit` → the loop runner owns `ScheduleWakeup`, not this fork: the output's tail state tells it to stop (`READY`, `BLOCKED`) or the cadence (working/greptile due/waiting → 300s, sign-off → 1800s).
   - one-shot `/babysit` → nothing to stop; report the state.

## Safety rails

- **Never push to** `main` / `master` / `stage`. Step 0 should already prevent this.
- **Never force-push.** If `git push` rejects (non-fast-forward), do not `--force` — report `push rejected — branch diverged` in chat, raise attention, exit clean.
- **Never amend** existing commits.
- **Never check out a different branch.** Stay on `$BRANCH` for the whole run.
- **Cap**: max 5 threads addressed per run. Leave the rest untouched (no note, no state entry) for the next run, and name them in chat.
- **MR comments are for reviewers only**: the 6.5 fix confirmation and the 6.7 decline reply. Nothing else gets posted.
- **Skip if MR is Draft** unless MR description contains `[babysit-ok]`: go straight to step 9, which stops the loop.

## Output

Single line:
```
remi!1234 (feat-xyz): 2 addressed, 1 declined (design), 1 needs sign-off, pipeline green, greptile requested (round 2/3) → waiting
```
`READY` and `BLOCKED` lines are followed by the MR `web_url` on its own line, last in the message. A skip or clean exit (preconditions, failure modes) prints its one reason line and nothing else.
Drop any zero-count segment (`declined`, `needs sign-off`, `doit <n> closed`). Greptile segment: `greptile requested (round n/3)` | `greptile pending` | `greptile <score>/5[, approved]`; omit when not greptile-aware. Tail is the step 9 state (`working`, `sign-off`, `waiting`, `READY`, `BLOCKED: <reason>`).
Below it, one entry per deferred thread, numbered by its state-file `n`: URL, why it was deferred, the plan or open question with options. Close with the sign-off line: `/babysit <path> signoff <n>[: plan edits]`. That run picks the thread up as `signed_off`.

## Failure modes — exit clean, never error

- glab auth expired → log + exit 0
- network error → log + exit 0
- merge conflict → report in chat + exit 0
- ambiguous review thread → defer to chat + skip
- multiple MRs from same branch → log + exit 0

Loop runners require clean exits. Stack traces here kill the loop next iteration.
