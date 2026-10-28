---
name: greptile
description: >-
  Own a repo's `.greptile/` review config: scaffold it when missing, turn
  invalid Greptile suggestions into repo rules (ask first), and keep
  auto-approve risk config in step with what MRs actually touch. Auto-fires
  when user says "set up greptile", "init greptile", "greptile rule", "tell
  greptile to stop flagging X", "tune greptile", "greptile re-review",
  "ask greptile to review", "@greptile review", "@greptileai review", invokes
  /greptile, when processing an MR or PR thread authored by `greptile` or
  `greptile-apps[bot]` (babysit, manual review triage), or before editing
  `.greptile/**`. GitLab MRs and GitHub PRs (orgs skio-org, RechargePayments).
  Modes: review, init, rule, sync.
argument-hint: "[review [mr] [--force] | init | rule <note-url> | sync [mr-url]]"
---
<!-- caveman:compressed -->

Four jobs: **review** (post the re-review trigger), **init** (no `.greptile/`), **rule** (Greptile suggestion wrong for this repo), **sync** (risk config vs what MRs touch). No mode given → `.greptile/` missing ? init : sync on the current branch's MR.

## review

Auto re-review is off (`autoReview` default `["open"]`); Greptile reviews on MR or PR open only. Trigger comment by host (`git remote get-url origin`): GitLab `@greptile review` (`@greptileai` also works there, use the former); GitHub `@greptileai review` only, since `@greptile` is another GitHub user. GitHub = orgs `skio-org` and `RechargePayments`; personal repos have no Greptile, stop and say so.

1. MR: arg (iid or URL) else `glab mr list --source-branch="$(git branch --show-current)" -F json`. GitHub: `gh pr list --head "$(git branch --show-current)" --state open --json number,url,headRefOid,body`. Zero or many → stop, say so.
2. Skip if already reviewed: latest `greptile_summary` note's "Last reviewed commit" link ends in the MR's `sha` (GitHub: the same line in the PR `body` or in the bot's summary comment ends in `headRefOid`) → report `head <sha7> already reviewed`, stop. Skip too if an `@greptile review` note (GitHub: a `@greptileai review` comment in `gh api repos/<o>/<r>/issues/N/comments`) is newer than the head commit (`hooks/greptile_rereview.py` posts one after every session push) → report `review already requested for <sha7>`, stop. `--force` posts anyway.
3. Unpushed local commits (`git rev-list @{u}..HEAD` non-empty) → warn: Greptile reviews the pushed head only.
4. Post: `glab mr note <iid> --message "@greptile review"`; GitHub `gh pr comment <n> --body "@greptileai review"`. Report the note or comment URL.
5. Review lands in ~2-3 min. Summary note is edited in place (`Reviews (N)` increments, `updated_at` moves); new findings arrive as fresh DiffNotes. GitHub: the summary (body or bot comment) is edited in place; new findings arrive as one more PR review with inline comments.

User invoking review = authorization to post; so are `/babysit` step 9 (it tracks rounds and caps at 3) and `ship-it` step 4b. Any other model-initiated post (fixes pushed, want fresh eyes) → AskUserQuestion first; it is an outward-facing post and spends a Greptile run.

## Greptile facts

Docs: https://www.greptile.com/docs/code-review/greptile-config, `-reference`, `auto-approve-prs`.

- GitLab bot: username `greptile` (also a project bot whose display name is `greptile`). Match `author.username == "greptile"` or `author.name` casefold `greptile`.
- GitHub bot: `user.login == "greptile-apps[bot]"` in REST, `author.login == "greptile-apps"` in GraphQL. The summary is either edited into the PR body (skio-org/frost: `gh pr view <n> --json body`, extra markers `<!-- greptile_comment -->`, `<!-- greptile-impact-verdict -->`) or posted as an issue comment by the bot (RechargePayments/ai-agent-hub, ai-investigator: `gh api repos/<o>/<r>/issues/<n>/comments`); read both. Same `<!-- greptile_summary -->` and score markers either way. Its status check is named `Greptile Review`. Findings = one PR review (`state: COMMENTED`, empty body) carrying inline review comments with the same badge + bold title. Threads: GraphQL `pullRequest(number:N){ reviewThreads(first:100){ nodes{ id isResolved isOutdated comments(first:50){ nodes{ databaseId author{login} body createdAt path line } } } } }`; resolve with the `resolveReviewThread(input:{threadId})` mutation. Approval, where `autoApprove.enabled`, is an `APPROVED` review by the bot on the head sha. A repo with no `.greptile/` is still reviewed under org-level enablement (skio-org/frost has none), so greptile-aware on GitHub = the body marker, not the tree.
- Note markers: `<!-- greptile_summary -->`, `<!-- greptile_confidence_score:N -->`, `<!-- greptile_auto_approval_sha:<sha> -->` ("Greptile approved these changes."), `<!-- greptile_outside_diff -->`. Inline finding = DiffNote, P0/P1/P2 badge (`badges/p1.svg`) + bold title.
- `.greptile/` = `config.json` (settings, `rules`, `disabledRules`, `instructions`, `ignorePatterns`, `autoApprove`), `rules.md` (prose context), `files.json` (context files, paths relative to the dir holding `.greptile/`).
- Cascade root → nearest dir. Settings: nearest wins. Rules, files, instructions: accumulate. Kill a parent rule from a child via `disabledRules: ["<id>"]`.
- Root `greptile.json` is IGNORED once `.greptile/` exists in the same dir.
- Testing auto-approve: use a human-authored MR. Dashboard filters can exclude bot authors (Renovate posts as `gitlab-integrations`), so a 5/5 bot MR without approval proves nothing about repo config. No approval note appears when Greptile withholds; silence is the only signal.
- Auto-approve = clean 5/5 review AND risk tier ≤ `riskCeiling`. Risk comes from what the diff does: low docs/tests/style, medium business logic, high deps/build config/shared core, critical auth/secrets/billing/migrations/infra/CI/public APIs. `instructions` can shift risk, never past the ceiling. New commits after review, `do-not-merge`/`manual-review` labels, or a change request block it.
- Dashboard vs `.greptile` on `autoApprove`: stricter value wins per field, so a repo value can only lower what the dashboard set. Unprompted, write only `autoApprove.filters.excludePaths`/`includePaths`. A repo cannot loosen auto-approve: its `riskCeiling` is capped by the dashboard's, risk instructions are dashboard-only ("not read from `.greptile` files"; `autoApprove.instructions` is ignored), and top-level `instructions` is reviewer guidance, not risk. Loosening one repo = dashboard work: add it to the auto-approve Repositories include filter, and/or a dashboard custom-instruction line scoped to that repo. Raising the dashboard ceiling hits every included repo.

## init

1. `.greptile/` exists → stop, run sync. Root `greptile.json` exists → carry every field into `.greptile/config.json` (same names), list `greptile.json` for deletion, delete only on confirm.
2. Seed from repo evidence only, never placeholders. Read CLAUDE.md / AGENTS.md / ARCHITECTURE.md / README / Makefile first.
   - `config.json`: `strictness: 2`, `commentTypes: ["logic","syntax"]`, `ignorePatterns` (generated, vendored, fixtures, `.giantmem/`), `instructions` (one line: docs to review against + the gate command; "linters own style"), `rules` from hard invariants the docs state AND the code confirms (`id` kebab, `rule`, `scope` globs, `severity`). `autoApprove.filters.excludePaths` = repo's High-Risk Files list, if one exists.
   - `rules.md`: `# Review notes for <repo>`, one stack paragraph, numbered "What matters in a review here", closing "Things that look wrong but are not:" line.
   - `files.json`: the convention docs above, one-line `description` each.
3. `ignorePatterns`: match an existing file's form. New file: newline-separated string (docs type it `string`).
4. `python3 -m json.tool .greptile/config.json >/dev/null && python3 -m json.tool .greptile/files.json >/dev/null`
5. Commit alone: `chore: add greptile review config`.
6. GitHub repo you set up yourself (org `RechargePayments`): make Greptile a required approver, in this order.
   1. `config.json` gets `"autoApprove": {"enabled": true, "riskCeiling": "<pick>"}`; `statusCheck` stays at its default `true`. Greptile approves only a clean 5/5 review, there is no lower bar on this side.
   2. After the config has merged to the base branch (policy is read from there), the branch ruleset (`gh api repos/<o>/<r>/rulesets`, the one targeting `~DEFAULT_BRANCH`; ai-agent-hub and ai-investigator already have one with `pull_request` `required_approving_review_count: 1`, `required_review_thread_resolution: true`, and `required_status_checks` `test`, `test-db`). Add the Greptile check to it, payload to a scratchpad file first:
      ```bash
      gh api "repos/<o>/<r>/rulesets/<id>" > <scratchpad>/ruleset.json   # edit: append {"context": "Greptile Review"} to the required_status_checks rule's parameters.required_status_checks
      gh api -X PUT "repos/<o>/<r>/rulesets/<id>" --input <scratchpad>/ruleset.json
      ```
      Greptile's check context is `Greptile Review` (seen on ai-agent-hub PR 3). Its 5/5 approval lands as an `APPROVED` review by `greptile-apps[bot]`; whether that review alone satisfies the count is read from `gh pr view <n> --json reviewDecision` (`APPROVED` = yes) on a PR with no human review.
   3. Repo CLAUDE.md gets `greptile_min_score: 5` and `greptile_approval: required`, so `/babysit` holds READY until both are there. Lowering to 4/5 later is a one-line edit of that key; Greptile's own approval stays at 5/5, so a 4/5 PR then waits for a human approval.
   Skio and other people's repos: skip this step.

## rule (invalid suggestion)

Fires per Greptile thread you judge wrong for this repo.

1. **Evidence bar.** Cite the code or convention that makes it wrong (file:line, or a doc claim you verified in code). None → suggestion is valid, fix it instead.
2. **Classify.**
   - one-off misread (Greptile misread this line, won't recur) → no rule. Reply + thumbs-down only.
   - recurring class (repo convention, framework semantics, deliberate design) → rule.
   - finding cites or matches a parent `.greptile` rule → `disabledRules` in the nearest child dir.
3. **Draft, smallest change first:** narrow an existing rule's `scope`/text > path-scoped `config.json` rule > one clause on rules.md's "Things that look wrong but are not" line (repo-wide). New rule text: "`<pattern>` in <scope> is deliberate: <reason>. Not a finding." No `severity` on not-a-finding rules. Rule goes in the nearest `.greptile/` above the flagged file.
4. **Ask.**
   - Interactive: one AskUserQuestion per run, one question per thread (max 4). Question: `Greptile: "<title>" at <file:line> is wrong here because <reason>. Add rule?` Options: `Add rule (Recommended)` with the JSON diff as preview, `Add to rules.md`, `One-off, no rule`.
   - Inside `/babysit` or any `/loop`: never AskUserQuestion. Write `greptile_rule: {target, diff}` into that discussion's babysit state entry, list it in chat under the deferred threads. User signs off in chat.
5. **Apply** on yes: edit, json-validate (init step 4), commit `review: greptile rule <id>` on the MR branch.
6. **Train Greptile** (any branch of step 2, once the thread is declined): decline-with-reason reply per babysit 6.5 style, plus a thumbs-down award on the Greptile note:
   ```bash
   glab api -X POST "projects/<pid>/merge_requests/<iid>/notes/<note_id>/award_emoji" -f name=thumbsdown
   gh api -X POST "repos/<o>/<r>/pulls/comments/<databaseId>/reactions" -f content=-1   # GitHub
   ```

## sync (risk config)

Run after reading Greptile's summary for the MR and after pushing review fixes. Repo without `.greptile/` → skip.

1. Read the latest `greptile_summary` note (score, findings) and whether a `greptile_auto_approval_sha` note matches the current head sha. GitHub: the PR body, and an `APPROVED` review by the bot on the head.
2. **Tighten, no ask:** diff touches a path repo docs or the code mark as critical (auth, secrets, billing, migrations, infra, CI, public API) and no `excludePaths` glob covers it → add the narrowest glob. Generated/vendored file drew findings → add to `ignorePatterns`. One line in chat per change.
3. **Ask first** (AskUserQuestion; in loops → babysit state + chat):
   - Greptile rated the MR above what the diff does (test-only held at medium, internal tooling treated as core) → `instructions` clause: "Changes confined to `<glob>` are low risk: <reason>."
   - A human reviewer caught a repo-invariant break Greptile missed → new enforcing rule (`"... is a finding"`, with `severity`).
   - Removing or widening any `excludePaths` entry, or any rule deletion.
4. Commit with the review fixes' push: `review: greptile <what>`.

## Edges

- `.greptile/` edits are build-config-shaped. Adding them to an MR that is otherwise auto-approve-eligible may raise its risk tier. MR near approval → offer a separate MR off the base branch instead.
- Greptile reads auto-approve policy from the MR's base branch ("a PR that edits its own config cannot loosen it"). Assume the same for rules: a `.greptile/` change is live only after merge.
