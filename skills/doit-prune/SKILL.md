---
name: doit-prune
description: >-
  Verify a doit list against live code, MR state, and its docs, then clean it: complete items whose code landed or whose doc decision resolved, turn live user actions (comms, review/merge asks, console settings, manual confirms) into owed items twinned into `daily`, repair twin drift, delete stale items, keep `decision` items 1:1 with doc Open Questions, rewrite drifted ones, and offer to delete a list left empty. Defaults to the session list. Auto-fires when user says "prune my todos", "prune the list", "clean up the list", "tidy doit", "is this list still valid", "what's stale on my list", or invokes /doit-prune. /babysit calls it with --mr --auto; /wrap runs its classify pass. Flags: --list, --all, --mr, --auto, --dry-run.
---

Docs and MRs are the source of truth; doit is the reminder. Code items close once their code is pushed in an MR. `decision` items mirror doc Open Questions 1:1. User actions live as owed items, twinned into `daily` (`twin` field, `daily:` / `from:` first description line). Creation rules it enforces → `feature-management` → `### Trigger — when a code item is written`, `### Decision mirror`, `### Owed items → daily twin`. doit MCP tools only, never raw JSON.

## Target

- `--list <name>` → verbatim. Else the session list from the SessionStart `doit session list` line. Re-derive on cwd / worktree / feature change: `python3 ~/.claude/hooks/doit_session_prime.py --name-only --cwd "$(pwd)"`.
- `--list daily` → classify only items that carry a `from:` line (owed twins): its project item done → `complete_todo`, gone → delete. Everything else in `daily` is the user's own: untouched.
- `--all` → every list in `list_lists` with pending > 0, `daily` included (per the rule above). One general-purpose subagent per list, in parallel, classify only (no doit writes). Each returns one line per item: `rank | verdict | evidence | action`. Main context applies after the single ask.
- `--mr <iid|url>` → only items whose text or description names that MR (URL or `!iid`) or its source branch. Skips the unmirrored scan.
- List missing → report it, stop. Never `create_list`.

## Classify

Every pending item. `in_progress` items may be claimed by another session: classify them, but act only on `landed` and `resolved`.

Evidence is live, this run: `glab mr view` / `gh pr view` for any MR or PR named; `git -C <repo> fetch` then `git log` / `git grep` against the default branch and the item's branch; reads of the files, symbols, and docs it names. Notes are hints, not proof. Repo comes from the item's `ref:` line, else its notes, else the list name matched against `config/repos.csv`.

| verdict | when | action |
|---|---|---|
| landed | code item: the change it names is committed and pushed in an open or merged MR/PR, or already on the default branch; or its whole job was an MR that has since merged | `complete_todo` + `add_note` append `DONE {ts} landed: <mr url or sha>` |
| resolved | `decision` item: its `ref:` doc exists and no longer lists the question under Open Questions | `complete_todo` + `add_note` append `DONE {ts} resolved in <doc path>: <answer, if the doc states one>` |
| twin-drift | owed item whose `daily` twin is done, or whose twin is gone | twin done → `complete_todo`. Twin gone and the action is still open → `delete_todo` + re-add with `owe=true`; else delete |
| moot | its MR closed unmerged, its branch is gone with nothing landed, the file/symbol it targets no longer exists, its `ref:` doc is gone, another item supersedes it (name the rank), or it is a POINTER/handoff to another list | delete |
| orphan | `decision` item with no `ref:` doc behind it | still open → adopt: add the entry to the feature's proposal/plan Open Questions, set `ref:`, and owe it if it has no twin. Else delete |
| owe | live user action with no `daily` twin: comms/share/ping, review/approve/merge an MR, console/admin/DNS/cert/vault/beta-admin settings, manual confirm/verify, ops runbook steps; also an open `decision` mirror with no twin | `add_todo owe=true` with the same type, text, and priority, description in the owed format (why / do / links / resume, pulled from the old notes); then `delete_todo` the old item. Holds an unlanded code half → that half stays a code item |
| noise | an FYI, a model next-step, or a user action already done (MR merged, step ran) | delete |
| drifted | open code work whose text names stale files/symbols/flags or whose notes are a dated status log; or a `decision` whose question was reworded or whose priority no longer matches `[BLOCKING]` | `update_todo`: accurate text and priority, `claude:` on if model work, description opens with the `ref:` line, the log collapsed to what is left |
| open | target exists, text accurate | keep |
| unknown | evidence unreachable (glab auth, repo not on disk, network) | keep; name what is missing |

User-authored items (the nvim/tmux `Mine` block: `source` set to anything but `mcp`, or no `source`, no `twin`, and text not starting with `claude:`, a `[type]` tag, or an `N.` rank) take only `landed` or `moot`, never `owe` or `noise`. They are the user's call.

**Unmirrored scan** (skipped with `--mr`): read `## Open Questions for User` in every `.md` under the list's scope dir: the feature dir for a feature list, or `.giantmem/` minus `features/` for a bare repo list. An entry with no matching `decision` item (match on question text) → add the mirror per `### Decision mirror`.

## Apply

1. `--dry-run` → table only, no writes. Stop.
2. `landed`, `resolved`, `twin-drift` completes, and unmirrored adds → apply now, no ask. All reversible (`revert_todo`, `delete_todo`).
3. `--auto` (babysit and other loops) → stop after step 2. No asks, no deletes, no rewrites. Output one line: `doit <list>: <n> closed, <m> to prune (/doit-prune)`.
4. Everything else → print the table, then ONE `AskUserQuestion`: apply all / apply except ranks I name / none. Run owe conversions, deletes, adoptions, and rewrites after the answer. With `--all`, one ask covers every list. If the list would end with 0 pending, put `clear_done` + `delete_list` in the same ask and name any tmux window `list_lists` shows linked to it.

## Output

Unknowns lead.

```
doit-prune: recharge-auth  14 pending -> 5 kept
unknown   #30  cc-wt/stage not on disk
landed    #7 #11  (!5 merged) closed
resolved  #9  (proposal.md Q2) closed
mirrored  +2 from plan.md
owe       #13 #14 -> daily #5 #6
drift     #20  twin done in daily, closed
noise     #15 #16  deleted
moot      POINTER  deleted
drifted   #22  rewritten
open      #18 #19 #34
```
