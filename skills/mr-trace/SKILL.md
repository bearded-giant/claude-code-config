---
name: mr-trace
description: Find the Claude session and worktree behind an MR/PR, or list the MRs/PRs that sessions opened or touched, with live status. Backed by giantmem's index of the harness `pr-link` records and `glab mr create` / `gh pr create` calls. Auto-fires when user says "which session opened X", "where did this MR come from", "where did this PR come from", "find the session for MR", "what MRs do I have open", "my open MRs", "what MRs did this session open", or invokes /mr-trace. Read-only.
---

Every MR/PR a Claude session creates, pushes to, or updates is already in giantmem. Ask giantmem. Never grep `~/.claude/projects/**/*.jsonl` by hand: it is slow, and a URL mention is not authorship.

## Lookup: one MR → its sessions

```bash
giantmem mr whose <ref>            # live status
giantmem mr whose <ref> --json     # for further processing
giantmem mr whose <ref> --no-status  # offline, skip glab/gh
```

`<ref>` forms:

| Form | Example | Matches |
|---|---|---|
| full URL | `https://gitlab.rechargeapps.net/identity/recharge-auth/-/merge_requests/63` | exactly one |
| `repo!N` / `group/repo!N` | `recharge-auth!63` | that repo's MR |
| `repo#N` | `frost#45` | that repo's GitHub PR |
| bare `!N` / `#N` | `!62` | every repo with that number |

A bare `!N` that matches more than one repo returns all of them. List every match. Never pick one, since repos share ids (`recharge-auth!62` and `investigator-agent!62` both exist).

## List: running MRs

```bash
giantmem mr list                       # open MRs/PRs, last 30d, live status
giantmem mr list --project <repo>      # opened from this repo's sessions, or targeting it
giantmem mr list --since 7d --all      # include merged/closed
giantmem mr list --json
```

Columns: `MR  STATE  TITLE  BRANCH  OPENER  DIR  URL`. STATE comes from a live glab/gh read. Merged and closed states are cached and never re-fetched.

## CLI unavailable

Use the giantmem-search MCP tool `find_mr` instead. Its args are `ref`, `project`, `since`, `include_closed`, and `live` (default true). Load it with ToolSearch `select:mcp__giantmem-search__find_mr` first.

## Report

One block per MR. Refs are always `repo!N` (GitHub `repo#N`) or the full URL, never a bare `!N`.

```
recharge-auth!63  conflicts  "Google ID token sign-in"
url       https://gitlab.rechargeapps.net/identity/recharge-auth/-/merge_requests/63
branch    google-id-token-service-auth   checkout: <path or none>
opened    f8943589  <ts>  dir <session cwd>
          resume: cd <session cwd> && claude --resume <full sid>
touched   4c72c55a  <ts>  dir <session cwd>
```

- `opened` means the session ran the create call. `first touched` means no create call was seen: the MR was opened outside Claude (web UI, plain terminal), or before the index had the record. The earliest session that pushed to it or updated it stands in. Say which one applies.
- The session dir is where to resume. The checkout is where the source branch lives now. They differ when a session opened an MR from a scratch clone or from another repo's worktree. Report both. `(ran in <dir>)` after the session dir is where the session's shell sat when it linked the MR (a `cd` into another repo or a scratch clone); resume still uses the session dir.
- `mr list` table markers: `~sid` opener = first touched, `state*` = cached state, `state!` = the live read failed.
- The state line is a live read. With `--no-status` or `live: false`, label it as cached.
