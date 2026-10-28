---
name: wrap
description: >-
  Pre-exit gate for any one-way door, with or without a feature: ending a session, moving to a new one, or completing / abandoning a feature. Checks git and MR state, syncs the doit list, updates feature or repo docs, settles running processes, writes the handoff, and ends with `safe to exit: yes|no`. Auto-fires when user says "wrap up", "wrap this up", "update feature docs and I'll end session", "once you confirm I'll exit", "I'll end the session", "starting a new session", "create a handoff", "new session prompt", "close this out", or invokes /wrap. Also runs before /complete-feature and /abandon-feature. Flags: --feature, --no-handoff.
---

The user is about to lose this session's context or close a feature. Anything not written down is gone. Run the checklist, fix what is safe to fix, and report the rest.

Without asking: commit and push tested work (CLAUDE.md git_rules), run branch cleanup (CLAUDE.md `## Branches and Worktrees`), and delete what this session created. Never remove a worktree or offer to, including the one this session runs in. Merge, opening or updating an MR ("ship it"), killing a process, and any other deletion go into ONE batched AskUserQuestion at the end of the checklist, and only when one of them is live.

## Mode

| Mode | When | Extra checks |
|---|---|---|
| `session` (default) | ending or restarting a session, in a bare repo or a feature | none |
| `feature` | `--feature`, "close out this feature", or before `/complete-feature` / `/abandon-feature` | every `tasks.md` box checked, feature MRs merged; on pass, offer `/complete-feature` (or `/abandon-feature`) in the batched ask |

Scope is the active `in_progress` feature (the one whose `branch` matches HEAD). With no feature, scope is the repo's `.giantmem/`.

## Checklist

Gather first, in parallel, using the same sources as `/feature-next` Gather steps 1 to 3: artifacts, the doit list, and MRs. Then walk:

1. **Git**, for every repo touched this session: cwd, any repo edited or named this session, and the repos of paired sessions.
   - `git status --short`, `git log @{u}.. --oneline`, branch, HEAD sha
   - open MRs: state, pipeline, unresolved threads. Include MRs this session opened on other repos: `giantmem mr list --project <repo>` (the `/feature-next` gather already runs it)
   - Uncommitted or unpushed work: tested → commit and push it. Untested, or another live session's → a gap, left as is.
   - Branch cleanup per CLAUDE.md `## Branches and Worktrees`: delete branches of MRs/PRs merged or closed as unneeded, then the merged-branch sweep. List what went under `Fixed`.
   - Links: every MR/PR this session opened (`giantmem mr list --project <repo>`) and every dashboard, artifact, or ticket it created, with URL.
2. **doit** (always pass `list=`):
   - Run the `doit-prune` skill's classify + `landed` steps on the session list (pushed in an MR counts as landed). Its deletes and rewrites ride the batched ask, not a second ask.
   - New items: code follow-ups should already be done (CLAUDE.md `### Proactive execution`). Work the session could do but did not finish goes in the handoff's `Start here`, not doit. Code blocked on me (operator detail, dangerous change) gets a code item that deps on its owed or decision item, no ask. Open decisions go in the doc's Open Questions and mirror per `feature-management` → `### Decision mirror`. User actions that pass the daily bar (`feature-management` → `### Owed items → daily twin`) become owed items (`add_todo owe=true`), no ask; the handoff's `Open edges` lists them by `daily #N`. Review/merge asks, tags, deploys, conditional confirms, and "say ship it" go in the handoff's `Open edges` as plain lines, never owed. Last doit call: leave the next item `in_progress` (`start_todo`): the one waiting on me, else the top pending one; when no item covers the ask the session stops on, `add_todo type=gate` (no `owe`) and start it.
   - Every `claude:` item must be burnable cold: `ref:` line, paths, commands, and identifiers in its text or description. Fill thin ones in.
   - Empty list, any mode: once the batched ask's closes and deletes have run, a session list left with 0 pending (no gate item added above) → `delete_list`, no ask; its done items go with it. List it under `Fixed`. Never `daily`; a refusal (list pinned active via `DOIT_ACTIVE_LIST`) goes under `Gaps`. The next session's SessionStart prime says `exists: no` and has it `create_list` on its first todo.
3. **Docs:**
   - Feature: `tasks.md` checkboxes match reality, and `{name}-notes.md` / `facts.md` hold this session's new identifiers, commands, gotchas, and decisions.
   - Bare repo: route per workspace-rules (`context/`, `plans/current.md`).
   - Docs created this session outside the scope dir (vault notes, other repos, claude.ai artifacts): collect absolute paths and URLs for the handoff's `External docs`, plus this session's bundle dir `~/giantmem_archive/bundles/<slug>/<session id>/` (scripts and drafts from the scratchpad land there).
   - Shared docs touched this session: recheck the shared-docs rule (no dates, changelogs, or local paths).
4. **Running processes** started this session (tunnels, dev servers, background shells, watchers): name, how started, port/pid. If the next session can reuse one, leave it up; otherwise offer teardown in the batched ask. Record each one in the handoff either way.
5. **Handoff:** write or overwrite it per workspace-rules `## Handoff`. Skip it with `--no-handoff`. If nothing is left open, skip it and set any existing handoff to `status: done`. A written handoff gets no doit item: SessionStart lists every `status: ready` handoff in the repo, and the handoff's `Start here` carries the resume. An open `resume` item on this list is a pointer: `delete_todo` it (its `daily` twin goes with it). The `daily_note` hook logs the handoff in the vault daily note on its own.
6. **Batched ask**, then the empty-list delete (step 2), then the verdict.

## Output

Gaps lead.

```
wrap: <feature or repo>  mode: session

Gaps
- recharge-auth: 2 unpushed commits on better-redis-search
- ngrok :4040 running, next session reuses it (recorded)
Fixed
- recharge-auth #12, #14 completed
- tasks.md 3.2 checked
- recharge-auth: deleted merged branches session-index-reads, sec-3897-logout-cutoff
Handoff
- ~/Recharge-Notes/handoffs/<project>/features/<name>.md
safe to exit: no: push recharge-auth

recharge-auth!47 https://gitlab.rechargeapps.net/<group>/recharge-auth/-/merge_requests/47
splunk dashboard https://<tenant>.splunkcloud.com/en-US/app/search/<id>
```

The links close the output, one per line, after `safe to exit`. Omit the block when the session created none.

`safe to exit: yes` requires all of these:
- no uncommitted or unpushed work the user hasn't waived
- the handoff is written, or nothing is open
- the doit list is synced

A gap the user waives in the ask is marked `waived`, stops blocking, and goes into the handoff's `Open edges`.
