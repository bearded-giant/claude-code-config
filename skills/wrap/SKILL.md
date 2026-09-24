---
name: wrap
description: Pre-exit gate for any one-way door, with or without a feature: ending a session, moving to a new one, or completing / abandoning a feature. Checks git and MR state, syncs the doit list, updates feature or repo docs, settles running processes, writes the handoff, and ends with `safe to exit: yes|no`. Auto-fires when user says "wrap up", "wrap this up", "update feature docs and I'll end session", "once you confirm I'll exit", "I'll end the session", "starting a new session", "create a handoff", "new session prompt", "close this out", or invokes /wrap. Also runs before /complete-feature and /abandon-feature. Flags: --feature, --no-handoff.
---

The user is about to lose this session's context or close a feature. Anything not written down is gone. Run the checklist, fix what is safe to fix, and report the rest.

Never commit, push, merge, delete, or kill a process on your own. Every such action goes into ONE batched AskUserQuestion at the end of the checklist. A bare "commit" answer means commit only.

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
   - open MRs: state, pipeline, unresolved threads
   - Uncommitted or unpushed work is a gap. Offer commit, or commit and push, in the batched ask.
2. **doit** (always pass `list=`):
   - Items that landed this session: `complete_todo` plus a DONE note. No ask needed.
   - New user follow-ups go in the batched ask.
   - Every `claude:` item must be burnable cold: paths, commands, and identifiers in its text or description. Fill thin ones in.
   - An open item for a merged MR is stale; offer to complete it.
3. **Docs:**
   - Feature: `tasks.md` checkboxes match reality, and `{name}-notes.md` / `facts.md` hold this session's new identifiers, commands, gotchas, and decisions.
   - Bare repo: route per workspace-rules (`context/`, `plans/current.md`).
   - Docs created this session outside the scope dir (Desktop, other repos, Notion): collect absolute paths and URLs for the handoff's `External docs`.
   - Shared docs touched this session: recheck the shared-docs rule (no dates, changelogs, or local paths).
4. **Running processes** started this session (tunnels, dev servers, background shells, watchers): name, how started, port/pid. If the next session can reuse one, leave it up; otherwise offer teardown in the batched ask. Record each one in the handoff either way.
5. **Handoff:** write or overwrite it per workspace-rules `## Handoff`. Skip it with `--no-handoff`. If nothing is left open, skip it and set any existing handoff to `status: done`.
6. **Batched ask**, then the verdict.

## Output

Gaps lead.

```
wrap: <feature or repo>  mode: session

Gaps
- recharge-auth: 2 unpushed commits on better-redis-search
- ngrok :4040 running, next session reuses it (recorded)
Fixed
- doit #12, #14 completed
- tasks.md 3.2 checked
Handoff
- /abs/path/.giantmem/features/<name>/handoff.md
safe to exit: no: push recharge-auth
```

`safe to exit: yes` requires all of these:
- no uncommitted or unpushed work the user hasn't waived
- the handoff is written, or nothing is open
- the doit list is synced

A gap the user waives in the ask is marked `waived`, stops blocking, and goes into the handoff's `Open edges`.
