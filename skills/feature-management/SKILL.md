---
name: feature-management
description: Feature folder lifecycle, scoping, and feature-scoped output routing for .giantmem/features/. Auto-fires when user says "create a plan", "draft a plan", "plan this out", "new feature", or invokes /new-feature, /plan-feature, /start-feature, /pause-feature, /complete-feature, /abandon-feature, /reopen-feature, /list-features, /feature-facts, /feature-report. Also fires before writing to .giantmem/features/** or when checking which feature is active, when user says "feature todos" / "add to the feature todo list" / "sync feature todos", or when multi-step work hits code that must wait on the user (operator detail or a dangerous change) and needs a doit item.
---

Feature system for `.giantmem/features/`. Persistent capabilities that span sessions.

## Folder structure

```
features/
├── features.json          # cache, every command reads/writes
├── _index.md              # human-readable registry
├── {feature-name}/
│   ├── proposal.md        # intent + scope + approach (renamed from spec.md)
│   ├── design.md          # optional — technical approach + architecture decisions
│   ├── specs/{domain}/    # delta-specs — ADDED/MODIFIED/REMOVED Requirements
│   │   └── spec.md        # behavior contract relative to source-of-truth
│   ├── tasks.md           # checkbox list, status auto-derives from %
│   ├── facts.md           # beta flags, config, test commands
│   ├── meta.json          # machine-readable (swarm)
│   ├── plan.md            # /plan-feature output
│   ├── plans/current.md   # transient session scratchpad (deleted on complete)
│   ├── research/          # scoped research
│   ├── reviews/           # scoped reviews
│   └── filebox/           # scoped data
```

## Three-spec split (post-OpenSpec-hybrid)

| Artifact | Role | When written |
|---|---|---|
| `features/{name}/proposal.md` | Intent — why this exists, scope, approach. NOT behavior. | `/new-feature` scaffolds. User refines. |
| `features/{name}/specs/{domain}/spec.md` | Delta-spec — `## ADDED` / `## MODIFIED` / `## REMOVED Requirements`. Behavior contract. Each Requirement has Given/When/Then scenarios (RFC 2119). | User/Claude writes when designing behavior. Empty allowed. |
| `.giantmem/specs/{domain}/spec.md` | Source-of-truth. Accumulated behavior across all completed features. | `/complete-feature` merges delta-specs in. Never hand-edited mid-feature. |

Legacy `features/{name}/spec.md` symlinks → `proposal.md` for 30-day muscle-memory back-compat (set by `migrate_spec_to_proposal.py`).

## Lifecycle (per-artifact)

Every artifact written under `features/{name}/` carries a `lifecycle:` field in addition to `status:`. Defaults stamped by `/new-feature` templates:

| Lifecycle | Used for | Behavior |
|---|---|---|
| `durable` | All `/new-feature` scaffolds (proposal, delta-spec, tasks, design, facts). Source-specs after `/complete-feature` merge. | Never auto-pruned. |
| `candidate` | AI-captured research, mid-session notes. | Listed by `/review-memory`. User promotes → durable or demotes → deprecated. |
| `deprecated` | Previously useful, now rejected. | Kept on disk. Excluded from stale reports. |

`/complete-feature` flips merged delta-specs to `lifecycle: durable` if not already (they should be — they came from a durable template).

## Cache discipline — CRITICAL

Every feature command (new/start/pause/complete/abandon/reopen) MUST update both:
- `.giantmem/features/features.json`
- `.giantmem/features/_index.md`

When adding beta flags or key config, add to Quick Reference section.

## When to create a feature folder

- Distinct capability, not a bug fix
- Spans multiple sessions
- Has identifiable artifacts (beta flag, endpoints)

## Commands

| Command | Purpose |
|---|---|
| `/list-features` | display registry |
| `/new-feature <name>` | scaffold folder (auto-detects pending vs in_progress) |
| `/plan-feature [name]` | ground on the code areas a feature touches, draft plan |
| `/feature-facts <name>` | quick lookup |
| `/feature-report [feature]` | validation report (parses delta-spec Requirements) |
| `/feature-validate <name> [--fix]` | lint structure; `--fix` auto-repairs |
| `/feature-next [name]` | informational status: DAG next artifact + doit list + open MRs, next split user vs claude |
| `/wrap [--feature]` | pre-exit gate (session end or feature close): git/MR, doit, docs, processes, handoff; runs before complete/abandon |
| `/start-feature <name>` | promote pending → in_progress |
| `/pause-feature` | mark current paused |
| `/complete-feature` | mark complete, merge delta-specs to source-of-truth |
| `/abandon-feature <name>` | framed but not building it: mark abandoned, NO spec merge, then archive (docs stay in live.db) |
| `/reopen-feature <name>` | complete → in_progress |

`complete` works from any status except `archived` — a `pending` feature can be closed out without walking it through `/start-feature`. Use `/abandon-feature` instead of `/complete-feature` when the work never happened: complete merges delta-specs into the source-spec (claiming behavior that does not exist), abandon does not.

Adjacent CLI surface (not Claude commands — terminal):

| Command | Purpose |
|---|---|
| `giantmem artifact list` | typed artifact query in current repo |
| `giantmem artifact list -f {feature}` | per-feature view |
| `giantmem artifact list --type delta-spec --status ready` | filter |
| `giantmem artifact reindex` | rebuild `.giantmem/artifacts.json` |
| `giantmem artifact show {id}` | print frontmatter + body |
| `giantmem artifact orphans` | files lacking frontmatter |

## "Create a plan" disambiguation — CRITICAL

When user says "create a plan", "plan this out", "draft a plan", or similar, MUST emit AskUserQuestion BEFORE any file write:

```
Question: feature (persistent, spans sessions) or session work (transient)?
Options:
  1. feature → /new-feature → features/{name}/proposal.md (+ delta-specs in specs/)
  2. session work → plans/current.md
```

Ask first. Write second. User often forgets which context they're in.

## Feature-scoped output routing

When a feature has status `in_progress` in `features.json`, it is the **active feature**. All session output that would normally go to top-level `.giantmem/` subdirectories MUST instead go inside the active feature's directory:

| Without active feature | With active feature `{name}` |
|---|---|
| `.giantmem/plans/current.md` | `.giantmem/features/{name}/plans/current.md` |
| `.giantmem/research/{topic}.md` | `.giantmem/features/{name}/research/{topic}.md` |
| `.giantmem/reviews/{subject}.md` | `.giantmem/features/{name}/reviews/{subject}.md` |
| `.giantmem/filebox/*` | `.giantmem/features/{name}/filebox/*` |

## Living feature notes (`{name}-notes.md`) — append during work

`/new-feature` seeds `features/{name}/{name}-notes.md` with minimal frontmatter and a single hint comment. Treat it as a **living cheat sheet**. Append silently as work happens — no permission ask, no chat announcement.

### Silent-background contract (CRITICAL — overrides default no-write bias)

When the active feature has status `in_progress` and an append trigger fires below, the model MUST:

1. **Append without asking.** Skip "should I save this?" — the trigger list IS the permission. Notes file exists (seeded), so it's an `Edit`, not a new-file `Write` — the global no-write-without-permission rule does not apply.
2. **Append silently.** Do NOT mention the append in chat. No "saved to notes", no "added to cheat sheet". Pure background. User reads the file when they want.
3. **Append in the same tool batch as the action being captured.** Don't defer to end-of-turn — model forgets. The Bash that runs a `kubectl` command and the Edit that appends it ship in one batch.
4. **Tiebreaker: append.** When unsure if a command is "reusable enough," append. Cost of noise in notes < cost of forgetting the command. Only skip if confidently single-use boilerplate.

### When to append (moderate — reusable signal)

- Bash / shell one-liner authored together OR pasted by the user (will likely re-run)
- `redis-cli`, `kubectl`, `gcloud`, `gh`, `glab`, `psql`, `mysql`, `curl`, `bq`, `vault`, `aws` commands that returned useful state or are worth re-running
- DB query that surfaced a non-obvious row / state worth re-querying
- env var, config knob, beta flag, or feature flag discovered mid-session (also mirror flag/endpoints into `facts.md`)
- Specific identifier worth keeping (e.g. `shop_id 47281 reproduces the bug`, `job_id abc123 = stuck task`, customer email, MR URL, Jira ticket)
- Script / function written for the feature, even tiny
- Path to a useful log file, dashboard URL, monitoring query, repro endpoint
- User explicitly says "save this" / "good for later" / "note that" / "we'll need this again" — append immediately, override every skip rule

### When NOT to append

- Single-use debug command obviously throwaway (e.g. one-shot `ls`, `cat <file>` to peek)
- Generic Linux commands every dev already knows (`git status`, `ls -la`)
- Content that belongs in another feature artifact — put it there instead:
  - intent / scope / approach → `proposal.md`
  - beta flag / endpoints / test commands / key files → `facts.md`
  - checkbox work items → `tasks.md`
  - behavior contracts (Requirements / Scenarios) → `specs/{domain}/spec.md`
- Spec quote, RFC 2119 wording — those are normative, live in delta-specs
- Anything inside `/complete-feature` execution — see Lifecycle below

### Sensitive data — REDACT before append

NEVER append raw:
- `Authorization: Bearer ...` tokens, API keys, vault tokens, OAuth secrets
- DB connection strings with embedded passwords
- Customer PII (email, phone, address) unless the user explicitly said save it
- `.env` file contents, GPG keys, SSH private keys

Redact with `<REDACTED:token>`, `<REDACTED:password>`, `<REDACTED:pii>` placeholders. Keep the surrounding command shape so it's still re-runnable after the user re-injects the secret.

### Format — VERY loose, no prescribed structure

- Append-only. Never reorder past entries. Never reformat past entries. Never delete past entries unless user explicitly asks.
- Group loosely by topic if helpful, otherwise chronological is fine.
- Code blocks for commands — preserve EXACTLY, no caveman compression inside fenced blocks.
- Prose around the block: caveman style, one short line, *why* not *what*.
- No section banners (`# === foo ===`), no decorative headers.
- Do NOT touch the seed frontmatter — append below it.

### Read on session resume — `non-empty` semantics

Read `{name}-notes.md` on resume when file has **content past the seed line** — i.e. >1 line of body beyond the frontmatter + seed `<!-- ... -->` comment. A file containing only frontmatter + seed comment counts as empty for resume purposes; skip it, do not surface the seed comment in chat.

When body content exists and resumed work touches a captured command/snippet, surface the relevant entry once ("last session we used: `<cmd>`") so it gets reused. Don't dump the whole file.

### When no feature is `in_progress`

Skip notes capture entirely. Do NOT buffer to a scratch file, do NOT prompt user to create a feature. Useful commands from session work go in `.giantmem/plans/current.md` if relevant to the current task, otherwise let them go. Notes file is feature-scoped by design.

### Lifecycle

- **During in_progress:** append per rules above.
- **During `/pause-feature`:** stop appending. Resume on `/start-feature` or `/reopen-feature`.
- **During `/complete-feature` execution itself:** do NOT append further. File freezes as durable reference at the moment `/complete-feature` starts.
- **After complete:** file stays in `features/{name}/`. Not merged into source-specs. Not pruned by `giantmem artifact stale`. Treated as `lifecycle: durable` per its frontmatter.

## Feature todos → doit sync

Hard link between multi-step feature work and the doit MCP. Code work blocked on the user (operator detail, or approval of a dangerous change), and decisions mirrored from doc Open Questions, get parked in a per-feature doit list. Everything else found during the work gets done this session (CLAUDE.md `### Proactive execution`). Docs and MRs are the source of truth; the doit item is the reminder. Once code is pushed in an MR, the MR tracks it and the item is landed. doit data lives at `~/.local/share/nvim/doit/lists/` — only ever touch it via the doit MCP tools, never by reading/writing JSON.

### Trigger — when a code item is written

Default is proactive (CLAUDE.md `### Proactive execution`). Code follow-ups found during the work, feature OR bare repo (bug found in passing, parity gap, stale doc or comment, test gap, split-out fix), get done this session. They never become doit items and never get an ask.

A code item is written only when the work waits on the user, or on explicit request:
- needs detail only the user has (product or design choice, credentials, access): the question goes in the doc's Open Questions (decision mirror) or an owed item, and the code item deps on it.
- dangerous (one-way door, data corruption or loss, security, outward-facing): an owed item to approve or decide, and the code item deps on it.

No ask; the owed or decision item is the gate. Name each in the open edges.
- Three item kinds only:
  - code work: a repo, a file or symbol, a change. `claude:` when the model can do it; no prefix when the user keeps it.
  - `decision`: mirror of one doc Open Question, per `### Decision mirror`. Never a free-standing decision item.
  - owed: an action only the user can do, per `### Owed items → daily twin`.
- Mixed item → only the code half becomes the code item. A decision half goes into the doc's Open Questions and mirrors from there; a user-action half becomes an owed item.
- Model-only next-steps (things the model does this turn) are NOT todos — skip them.
- No active feature → use the bare `{repo}` list. User works outside features often — do NOT skip. `daily` is written only through `owe=true` twins or on explicit user request.
- Also fires on explicit phrasing: "feature todos", "add to the feature list", "sync feature todos".

### Decision mirror — doc Open Questions ↔ doit, 1:1

The doc is the source of truth; the item is the reminder. Every `## Open Questions for User` entry in a `.giantmem/` doc has exactly one `decision` item, and every `decision` item points at exactly one entry.

- Write in the same turn the doc gains or rewords an entry. No ask. Say `mirrored N decisions to <list>` in chat.
- List: the doc's feature list (`--feature <name>` derivation below), or the bare `{repo}` list for a repo-level doc.
- Item: `add_todo type=decision` on that list, no `owe`. A design decision is feature work, not an inbox action, so it never twins into `daily`. Text = the question (≤ 80 chars); description opens `ref: <doc abs path>`, then `why` (what it blocks) and `links`. `[BLOCKING]` → priority `urgent`, `[non-blocking]` → none. No `claude:`.
- Resolve doc first: the answer lands in the doc and the entry leaves Open Questions, then `complete_todo` + `add_note` append `DONE {ts} resolved in <doc path>: <one-line answer>`. Same order when the user answers in chat or in the doit note.
- Match items to entries on question text; entry numbers shift as others resolve.
- Drift either way (orphan item, unmirrored entry, a decision carrying a `daily` twin) → `/doit-prune` repairs it.

### Owed items → daily twin

`daily` is the user's one inbox for everything they owe across 4-6 parallel projects. The project list keeps the work record; `daily` holds its twin, so the user never has to remember which list holds their next action.

- What: anything only the user can do that the work waits on. Run / confirm / verify (stage check, manual login, eval run), review / approve / merge an MR, comms (ping, share, announce), console / admin / DNS / cert / vault / beta-admin settings, BLOCKED `/burn` items, READY MRs from `/babysit`, and resuming work `/wrap` paused.
- Not: model next-steps, code work the model can do (`claude:` code item), design decisions (`decision` mirrors on the feature list, per `### Decision mirror`), FYIs or suggestions that block nothing.
- How: `add_todo owe=true list=<project list>`, one call. The MCP writes `[type] N. owed in daily #M: <action>` in the project list and `[type] M. <project list>: <action>` in `daily`. Each carries a `twin` field and a first description line naming the other. Never write the twin by hand, never `claude:`.
- Gate: none. Write when the need appears, then name it in the chat report's open edges as `daily #M`. Dedupe first: `search_todos` on the action's key noun; an open twin for the same action → update it instead.
- Type: `gate` (run / confirm / verify), `review`, `merge`, `ping`, `setting`, `unblock`, `resume`.
- Priority: blocks the critical path → `urgent`; else none. `due` only for a real date.
- Text: the action as an imperative the user can do cold, ≤ 80 chars. Name the thing (`merge !812 auth0 callback fix`), not the activity (`check MR`).
- Description, for the user reading it days later. Labeled sections, blank line between, empty rows omitted:

  ```
  why:
  <one line: what is waiting on this>

  do:
  <exact command / URL / click path>
  expect: <what success looks like>

  links:
  - repo: <worktree abs path> [branch <name>]
  - mr: <url>
  - handoff: <abs path>
  - doc: <abs path of the .giantmem doc>
  - vault: <abs path of the vault note>
  - artifact: <claude.ai url>

  resume:
  tmux: <session>:<window>
  cd <worktree abs path> && claude --resume <session id>
  giantmem://session/<session id>
  ```

  The SessionStart `doit session list` block prints the session id, the tmux `session:window`, and the ready-made resume line. Link every vault note, artifact, and `.giantmem` doc this session wrote that the action touches.
- Close: action done (user says so, MR merged, doc resolved) → `complete_todo` on either twin; both close. Dropped (won't-fix, MR closed unmerged, superseded, target gone) → `complete_todo` on either twin plus a `WONTFIX {ts} <reason>` note; both close. `delete_todo` only for noise, duplicates, or a delete-and-re-add. `update_todo` done / priority / due also follow.
- Drift: a twin checked off or deleted in the tmux or nvim UI does not sync. SessionStart prints `DRIFT` lines for the session list; fix those first. `/doit-prune` repairs the rest.

### List resolution — repo-qualified, worktree-aware

List name carries repo (+ worktree) so it stays legible across 4-6 parallel sessions — bare feature names lose context. Derive:

`hooks/doit_session_prime.py` owns this derivation and prints the resolved name at SessionStart (`doit session list ... list: <name>`) — use that name verbatim. Re-derive only if cwd / worktree / feature changed mid-session:

```bash
python3 ~/.claude/hooks/doit_session_prime.py --name-only --cwd "$(pwd)"
python3 ~/.claude/hooks/doit_session_prime.py --name-only --feature <name> --cwd "$(pwd)"
```

First form follows the `in_progress` feature (same as SessionStart). Second pins a named feature of any status — use it whenever work is for a feature other than the primed one, incl. a `pending` feature just made by `/new-feature` (which creates that list).

| cwd | active feature | list name |
|---|---|---|
| `~/dev/claude-code-config` | `oauth-ttl` | `claude-oauth-ttl` |
| `~/dev/claude-code-config` | none | `claude` |
| `~/dev/python/cc-wt/local-dev-runner` | `retry-loop` | `cc-retry-loop` |
| `~/dev/python/cc-wt/local-dev-runner` | none | `cc-local-dev-runner` |
| `~/dev/python/cc-wt/main` | none | `cc` |

- Repo = worktree parent minus `-wt` (parent ends `-wt`), else `{leaf}`; `recharge-` dropped; over 14 chars → first word. A name that comes out as bare `claude` keeps two words (`claude-code`), since a `claude:` twin label in `daily` reads as a burn item.
- Then `-{feature}`, else `-{worktree}` unless it is `main`/`master`/`develop`. `feat-`/`fix-`/`chore-` dropped.
- Capped at 24 chars (the MCP rejects longer): trailing words shed, never cut mid-word.
- Reuse the list if it already exists, else `create_list` (hyphens, no spaces — names already kebab).
- Proactive todo ASK fires in OR out of a feature: feature active → `{repo}-{feature}`, none → bare `{repo}`. Don't gate on a feature.
- Todos belong to the feature the work is for, not the one SessionStart primed. Work on a `pending` feature while another is `in_progress` → that feature's list (`--feature <name>`), never the primed list.
- Session start: the `doit_session_prime` hook prints this session's derived list name + every pending item (priority bucket → do-order, first description line, `in_progress` marker, truncated past 15). Items already in context — `list_todos` only to refresh after a write or see past truncation. Re-derive on cwd / worktree / feature change. Several features `in_progress` → the hook picks the one whose `branch` matches HEAD, else the first. ALWAYS pass `list=` explicitly on every doit call; the MCP's active-list default is `daily` (or a `DOIT_ACTIVE_LIST` export), not this derivation; tmux window links steer only the user's views.
- Pending items are the feature's open work. Land one this session → `start_todo` on pickup, `complete_todo` + DONE record when it lands. Never leave a landed item open.
- `daily` is the user's cross-repo inbox. Qualified lists reach it only through `owe=true` twins, never by copying items.

### Bucket → doit priority

| Bucket | doit `priority` | Means |
|---|---|---|
| critical | `critical` | blocks ship / on critical path / breaks if skipped |
| urgent | `urgent` | time-sensitive, do soon |
| important | `important` | matters, not time-boxed |
| default | omit (none) | nice-to-have / someday |

Code and `claude:` items live only in the feature list. Only owed items twin into `daily`.

### Numbering

Prefix every item text with `N.` = do-order / critical-path sequence across the whole list (`1. wire token refresh`, `2. add ttl config`). The number is the explicit priority signal the user reads — doit exposes no visible ordinal. Bucket conveys urgency; number conveys "do this Nth". Skip `order_index` unless the visible sort drifts from the numbers.

### Description — more than a post-it

Every item gets a `description`: the `ref:` line below, then whatever it carries of:
- doc link — repo path or URL
- script / command to run — exact, fenced or backticked
- identifier — MR URL, Jira ticket, `shop_id`, `job_id`, dashboard link

Preserve commands / paths / URLs EXACTLY (no caveman inside them). Redact secrets per the notes rules above (`<REDACTED:token>` etc.).

First description line is always `ref: <repo abs path> [branch <name>] [mr <url>]` (`decision` items: `ref: <doc abs path>`). `/doit-prune` and `/babysit` match staleness on it, and the session-prime hook prints it.

Notes are not a status log. When scope shrinks or names change, rewrite the text with `update_todo`; don't append dated status paragraphs.

### Create vs update (idempotent)

1. `list_todos list={feature}` first.
2. Dedupe — skip items whose text fuzzy-matches an existing todo.
3. Append new items; continue numbering from current max `N`.
4. Re-bucket / add notes on existing items via `update_todo` / `add_note` only when their priority or context changed.

Never silently renumber the whole list — append-extend. Reorder only on explicit user request.

### Model-assignable items (`claude:` prefix)

Code items the model can execute carry `claude:` so a later `/burn` picks them up. Code items the user keeps and `decision` mirrors carry no prefix; `/burn` skips them. Full burn-down loop → `burn` skill. Cleanup of stale or non-code items → `doit-prune` skill.

## Always global — NEVER feature-scoped

- `history/` — session log spans all features
- `prompts/` — reusable templates
- `context/patterns.md` — curated architectural patterns (repo-level)
- `WORKSPACE.md`, `features/_index.md`, `features.json`

Create subdirectories inside feature folder on first write. Don't require upfront.

When no feature is `in_progress`, use top-level `.giantmem/` subdirectories.

## Session start check

SessionStart hooks already inject WORKSPACE.md, top-level `plans/current.md`, and the active feature name; do not re-read them unless the injected block is truncated. When resuming active-feature work, read only:
1. Active feature's `plans/current.md`
2. Active feature's `{name}-notes.md` if non-empty — living cheat sheet, surface relevant commands when resuming related work

## Todos → doit (repo / feature list)

Code follow-ups found during multi-step work get done this session (CLAUDE.md `### Proactive execution`); no ask, no item. Code items exist only for work blocked on the user (operator detail or a dangerous change) or on explicit request, written without an ask next to the owed or decision item they dep on. Doc-mirrored `decision`s go on the feature or project list without an ask (no `owe`, no `daily` twin); owed user actions (run / confirm, review / merge, comms, settings, resume) are written without an ask as `owe=true` twins; full rule → `### Trigger — when a code item is written`, `### Decision mirror`, `### Owed items → daily twin` above. Fires in OR out of a feature — bare-repo work counts (you work outside features often).

- List = `{repo}-{feature}` capped at 24 chars (e.g. `claude-oauth-ttl`, `cc-retry-loop`); no feature → `{repo}` or `{repo}-{worktree}`. Reuse if exists, else `create_list`. `daily` only via `owe=true` twins or explicit request. Derivation → `feature-management` skill.
- Bucket → doit `priority`: critical→`critical`, urgent→`urgent`, important→`important`, default→omit. Classify by urgency + critical-path.
- Number each item in text (`1. …`, `2. …`) = do-order / critical-path sequence — the visible priority signal (doit has no ordinal field user sees).
- Item `description` opens with `ref: <repo abs path> [branch <name>] [mr <url>]`, then any doc link, exact script/command, or identifier (MR URL, ticket, shop_id) — preserve those EXACTLY, redact secrets.
- Update existing list: `list_todos` first, dedupe vs current items, append new, continue numbering from max. Only owed items twin into `daily`.
- Session start: `doit_session_prime` hook injects the list name AND every pending item (priority bucket → do-order, first description line, `in_progress` claim marker, truncated past 15 with a count). Items are already in context — no `list_todos` needed to see them; call it only to refresh after a write, to see past the truncation, or when cwd / worktree / feature changed mid-session (re-derive the name then). ALWAYS pass `list=` explicitly on every doit call — the MCP's active-list default is `daily` (or a `DOIT_ACTIVE_LIST` export), not this name.

## Three-Spec Model (per-feature → repo-truth)

| Artifact | Lives at | Holds |
|---|---|---|
| `proposal` | `features/{name}/proposal.md` | intent + scope + approach (NOT behavior) |
| `delta-spec` | `features/{name}/specs/{domain}/spec.md` | `## ADDED / MODIFIED / REMOVED Requirements` blocks. Each `### Requirement:` carries one or more `#### Scenario:` (GIVEN / WHEN / THEN, RFC 2119). |
| `source-spec` | `.giantmem/specs/{domain}/spec.md` | accumulated behavior across all completed features. Written ONLY by `/complete-feature` merging delta-specs in. Never hand-edit mid-feature. |

Legacy `features/{name}/spec.md` is a symlink → `proposal.md` (30-day muscle-memory back-compat from the `migrate_spec_to_proposal.py` rename).
