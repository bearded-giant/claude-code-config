---
name: greptile
description: >-
  Own a repo's `.greptile/` review config: scaffold it when missing, turn
  invalid Greptile suggestions into repo rules (ask first), and keep
  auto-approve risk config in step with what MRs actually touch. Auto-fires
  when user says "set up greptile", "init greptile", "greptile rule", "tell
  greptile to stop flagging X", "tune greptile", "greptile re-review",
  "ask greptile to review", "@greptile review", invokes /greptile, when
  processing an MR thread authored by `greptile` (babysit, manual review
  triage), or before editing `.greptile/**`. Modes: review, init, rule, sync.
argument-hint: "[review [mr] [--force] | init | rule <note-url> | sync [mr-url]]"
---
<!-- caveman:compressed -->

Four jobs: **review** (post the re-review trigger), **init** (no `.greptile/`), **rule** (Greptile suggestion wrong for this repo), **sync** (risk config vs what MRs touch). No mode given → `.greptile/` missing ? init : sync on the current branch's MR.

## review

Auto re-review is off; Greptile reviews on MR open only. Trigger is the comment `@greptile review`. `@greptileai` (the docs' handle) also works on GitLab; use the former.

1. MR: arg (iid or URL) else `glab mr list --source-branch="$(git branch --show-current)" -F json`. Zero or many → stop, say so.
2. Skip if already reviewed: latest `greptile_summary` note's "Last reviewed commit" link ends in the MR's `sha` → report `head <sha7> already reviewed`, stop. `--force` posts anyway.
3. Unpushed local commits (`git rev-list @{u}..HEAD` non-empty) → warn: Greptile reviews the pushed head only.
4. Post: `glab mr note <iid> --message "@greptile review"`. Report the note URL.
5. Review lands in ~2-3 min. Summary note is edited in place (`Reviews (N)` increments, `updated_at` moves); new findings arrive as fresh DiffNotes.

User invoking review = authorization to post; so is `/babysit` step 9 (it tracks rounds and caps at 3). Any other model-initiated post (fixes pushed, want fresh eyes) → AskUserQuestion first; it is an outward-facing post and spends a Greptile run.

## Greptile facts

Docs: https://www.greptile.com/docs/code-review/greptile-config, `-reference`, `auto-approve-prs`.

- GitLab bot: username `greptile` (also a project bot whose display name is `greptile`). Match `author.username == "greptile"` or `author.name` casefold `greptile`.
- Note markers: `<!-- greptile_summary -->`, `<!-- greptile_confidence_score:N -->`, `<!-- greptile_auto_approval_sha:<sha> -->` ("Greptile approved these changes."), `<!-- greptile_outside_diff -->`. Inline finding = DiffNote, P0/P1/P2 badge (`badges/p1.svg`) + bold title.
- `.greptile/` = `config.json` (settings, `rules`, `disabledRules`, `instructions`, `ignorePatterns`, `autoApprove`), `rules.md` (prose context), `files.json` (context files, paths relative to the dir holding `.greptile/`).
- Cascade root → nearest dir. Settings: nearest wins. Rules, files, instructions: accumulate. Kill a parent rule from a child via `disabledRules: ["<id>"]`.
- Root `greptile.json` is IGNORED once `.greptile/` exists in the same dir.
- Auto-approve = clean 5/5 review AND risk tier ≤ `riskCeiling`. Risk comes from what the diff does: low docs/tests/style, medium business logic, high deps/build config/shared core, critical auth/secrets/billing/migrations/infra/CI/public APIs. `instructions` can shift risk, never past the ceiling. New commits after review, `do-not-merge`/`manual-review` labels, or a change request block it.
- Dashboard vs `.greptile` on `autoApprove`: stricter value wins per field. So NEVER write `autoApprove.enabled` or `riskCeiling` (repo can only lower what the dashboard set). Only `autoApprove.filters.excludePaths`/`includePaths` go in repo config.

## init

1. `.greptile/` exists → stop, run sync. Root `greptile.json` exists → carry every field into `.greptile/config.json` (same names), list `greptile.json` for deletion, delete only on confirm.
2. Seed from repo evidence only, never placeholders. Read CLAUDE.md / AGENTS.md / ARCHITECTURE.md / README / Makefile first.
   - `config.json`: `strictness: 2`, `commentTypes: ["logic","syntax"]`, `autoReview: ["open","push"]`, `ignorePatterns` (generated, vendored, fixtures, `.giantmem/`), `instructions` (one line: docs to review against + the gate command; "linters own style"), `rules` from hard invariants the docs state AND the code confirms (`id` kebab, `rule`, `scope` globs, `severity`). `autoApprove.filters.excludePaths` = repo's High-Risk Files list, if one exists.
   - `rules.md`: `# Review notes for <repo>`, one stack paragraph, numbered "What matters in a review here", closing "Things that look wrong but are not:" line.
   - `files.json`: the convention docs above, one-line `description` each.
3. `ignorePatterns`: match an existing file's form. New file: newline-separated string (docs type it `string`).
4. `python3 -m json.tool .greptile/config.json >/dev/null && python3 -m json.tool .greptile/files.json >/dev/null`
5. Commit alone: `chore: add greptile review config`.

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
   ```

## sync (risk config)

Run after reading Greptile's summary for the MR and after pushing review fixes. Repo without `.greptile/` → skip.

1. Read the latest `greptile_summary` note (score, findings) and whether a `greptile_auto_approval_sha` note matches the current head sha.
2. **Tighten, no ask:** diff touches a path repo docs or the code mark as critical (auth, secrets, billing, migrations, infra, CI, public API) and no `excludePaths` glob covers it → add the narrowest glob. Generated/vendored file drew findings → add to `ignorePatterns`. One line in chat per change.
3. **Ask first** (AskUserQuestion; in loops → babysit state + chat):
   - Greptile rated the MR above what the diff does (test-only held at medium, internal tooling treated as core) → `instructions` clause: "Changes confined to `<glob>` are low risk: <reason>."
   - A human reviewer caught a repo-invariant break Greptile missed → new enforcing rule (`"... is a finding"`, with `severity`).
   - Removing or widening any `excludePaths` entry, or any rule deletion.
4. Commit with the review fixes' push: `review: greptile <what>`.

## Edges

- `.greptile/` edits are build-config-shaped. Adding them to an MR that is otherwise auto-approve-eligible may raise its risk tier. MR near approval → offer a separate MR off the base branch instead.
- Whether Greptile reads `.greptile/` from the MR head or the target branch is undocumented. Count a rule as live only after merge.
