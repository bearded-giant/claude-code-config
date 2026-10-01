---
description: Auto-address open review threads on the MR for the CURRENT worktree branch. Scoped to one MR — the one whose source branch == current branch. Idempotent — safe to /loop inside a worktree. Trigger phrases - "babysit this MR", "address review comments", "/babysit", or invoked via `/loop 5m /babysit`.
allowed-tools: Bash, Read, Edit, Write, Grep, Glob
---

Address open review comments on the MR for **this** worktree's branch.

## Worktree scoping model

This command is worktree-scoped by design. One session/loop handles exactly one MR — the one matching the current branch. Run separate `/loop /babysit` instances in each worktree to cover multiple MRs in parallel.

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
   - Zero results → exit clean: `no open MR for branch <BRANCH>`
   - Multiple results → exit clean: `ambiguous: <n> MRs from this branch — manual triage needed`
   - One result → proceed. Capture `iid`, `project_id`, `web_url`.

2. **Fetch unresolved discussions**:
   ```
   glab api "projects/<project_id>/merge_requests/<iid>/discussions" --paginate
   ```
   Keep a thread if `system=false` AND it still requests a change (`resolved=false`, or a `resolvable=false` MR-level note that asks for one) AND its last non-system note author is someone other than you. Skip a thread whose last note is yours — you are mid-conversation, leave it.

   **Deferred state** lives in `$(git rev-parse --git-dir)/babysit-<iid>.json`: `{discussion_id: {reason, plan, url}}`. Skip any kept thread already in it unless the user signed it off in chat this session. Zero kept threads → exit clean.

   **Never run the sign-off handshake through MR comments.** No `[babysit]` notes, no asking the user to reply on a thread. Deferrals go to the state file and to chat; the user signs off in chat.

3. **Classify each kept thread** before touching code. Read the thread context (file path + line if present). Bucket into:
   - `signed_off` — a deferred thread the user approved in chat (`signed off`, `do it`, or edits to the plan). Implement the plan as approved. Highest priority, overrides the buckets below; drop its state-file entry once pushed.
   - `actionable_simple` — rename, typo, missing test case, obvious null check, dead code, lint-style nit. Safe to one-shot.
   - `actionable_complex` — design or refactor request. Split by how concrete the direction is:
     - **concrete direction** (reviewer named the target, e.g. "use request hooks for `internal_chat_api_bp`", "move to its own blueprint") → attempt it, scoped strictly to what was asked.
     - **ambiguous / open question** (e.g. "is this the right layer?", "should this live elsewhere?") → defer: state file + chat, with the open question and 1–3 options. No thread reply.
   - `informational` — "looks good", "nit just FYI", no requested change. Skip.
   - `contradicts_design` — the ask runs counter to a design decision or known reason established in **this session / branch work**. Do not implement. The thread still gets a one-line decline-with-reason reply (step 6.7). Only use this when a concrete established reason actually exists — never fabricate a rationale to dodge work; absent a real reason, fall back to `actionable_*`.

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
   5. Reply on thread with a **casual confirmation** — write like a teammate dropping a quick note, not an LLM summary:
      - One short, plain sentence per item you actually addressed in this thread. Reviewer note bundles N findings → N bullets; single finding → one sentence, no bullet.
      - Style: `` `foo` handled in tests now ``, `` `_hello_world` guard added ``. One line per item, ~15 words. No preamble ("I have addressed…"), no restating the finding verbatim, no file/doc-path citations (`CLAUDE.md → …`), no justification the reviewer didn't ask for, no sha dump, no blanket paragraph.
      - **Omit** any item you didn't touch (out of scope, silently skipped) — never mention it.
      - For an item you deliberately did **not** do (contradicts a design decision / known reason from this session, or you're keeping as-is), add one bullet stating the decision + one reason, nothing more. Examples: `` `app.logger` is the repo standard — leaving as-is, will revisit in a follow-up ``, `` email-in-logs intentional for rollout; TODO already flags it for revisit ``, `schema migration not needed: already handled`.

      Build the body (newline-separated bullets) in `$REPLY`, then:
      ```
      glab api -X POST "projects/<project_id>/merge_requests/<iid>/discussions/<discussion_id>/notes" -f body="$REPLY"
      ```
   6. Resolve thread if `resolvable=true`:
      ```
      glab api -X PUT "projects/<project_id>/merge_requests/<iid>/discussions/<discussion_id>" -f resolved=true
      ```
      MR-level notes (`resolvable=false`) can't be resolved via API — reply only.
   7. **`contradicts_design` threads** — no edit, no commit, no resolve. Skip 6.1–6.4 and 6.6. Post only the decline-with-reason bullet (6.5 decline branch) and leave the thread **unresolved**, so the human can accept or contest the rationale.

7. **Raise attention if anything was left for you** — once, at end of run. If anything was newly deferred this run (NEEDS-SIGN-OFF, `actionable_complex` ambiguous, push rejected, pipeline red, rebase conflict):
   ```
   python3 ~/.claude/hooks/request_attention.py "MR !<iid> (<branch>): <n> thread(s) need your sign-off"
   ```
   Flags the tmux window + sends a desktop notification when the session stops. Threads already in the state file from an earlier run do not re-fire it. If babysit fully handled every thread, do **not** call it — silent success.

8. **Pipeline check** — after final push, query:
   ```
   glab api "projects/<project_id>/pipelines?ref=$BRANCH&order_by=updated_at&per_page=1"
   ```
   If pipeline newly red from this push, report `pipeline red after my fix — <job-url>` in chat, raise attention (step 7), and bail. If pipeline green or unrelated red, nothing to report.

## Safety rails

- **Never push to** `main` / `master` / `stage`. Step 0 should already prevent this.
- **Never force-push.** If `git push` rejects (non-fast-forward), do not `--force` — report `push rejected — branch diverged` in chat, raise attention, exit clean.
- **Never amend** existing commits.
- **Never check out a different branch.** Stay on `$BRANCH` for the whole run.
- **Cap**: max 5 threads addressed per run. Leave the rest untouched (no note, no state entry) for the next run, and name them in chat.
- **MR comments are for reviewers only**: the 6.5 fix confirmation and the 6.7 decline reply. Nothing else gets posted.
- **Skip if MR is Draft** unless MR description contains `[babysit-ok]`.

## Output

Single line:
```
MR !1234 (feat-xyz): 2 addressed, 1 declined (design), 1 needs sign-off, pipeline green
```
Drop any zero-count segment (`declined`, `needs sign-off`).
Below it, one numbered entry per deferred thread: URL, why it was deferred, the plan or open question with options. The user signs off in chat by number (`signed off 1`, or plan edits); the next run picks it up as `signed_off`.

## Failure modes — exit clean, never error

- glab auth expired → log + exit 0
- network error → log + exit 0
- merge conflict → report in chat + exit 0
- ambiguous review thread → defer to chat + skip
- multiple MRs from same branch → log + exit 0

Loop runners require clean exits. Stack traces here kill the loop next iteration.
