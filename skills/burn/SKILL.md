---
name: burn
description: >-
  Burn down `claude:`-marked todos from a doit list, sequence-first then priority, each worked end-to-end and closed with an outcome note (normal git/confirm gates still apply). Defaults to the active session's feature/project list; `--list` targets another. Auto-fires when user says "burn my todos", "burn down", "burn the queue", "work my todos", or invokes /burn. Flags: --list, --priority, --max, --dry-run.
---
<!-- caveman:compressed -->

Worker queue. User assigns tasks by prefixing a doit todo with `claude:`. `/burn` picks them up in sequence order, then by priority, and works them down. doit data at `~/.local/share/nvim/doit/lists/` — touch only via doit MCP tools, never raw JSON.

## Marker

Todo text starts `claude:` (case-insensitive) → assigned to model.
- `claude: fix token expiry check in auth middleware`
- Instruction = text after `claude:`. The todo's `description`/note = doc link / script / identifiers / context.
- Non-`claude:` todos = user's own. `/burn` NEVER touches them.

## Target list (resolve in order)

1. `--list <name>` arg → use verbatim
2. else derive the repo-qualified, worktree-aware name:

`hooks/doit_session_prime.py` owns this derivation and the SessionStart reminder already prints the answer (`doit session list ... list: <name>`) — use that name verbatim. Re-derive only if cwd / worktree / feature changed mid-session:

```bash
python3 ~/.claude/hooks/doit_session_prime.py --name-only --cwd "$(pwd)"
python3 ~/.claude/hooks/doit_session_prime.py --name-only --feature <name> --cwd "$(pwd)"
```

   - `~/dev/claude-code-config` + feature `oauth-ttl` → `claude-code-config-oauth-ttl`
   - `~/dev/claude-code-config`, no feature → `claude-code-config`
   - `~/dev/python/cc-wt/local-dev-runner` + feature → `cc-wt-local-dev-runner-{feature}`
3. List doesn't exist → nothing to burn, report it. Don't `create_list` on a read.

ONE list per run. Other lists untouched — safe across 4-6 parallel sessions.

## Build the queue

1. `list_todos list={target} filter=in_progress`, then `filter=pending`. An `in_progress` `claude:` item is the active one a prior turn or session left next: it heads the queue.
2. Keep only items whose text matches `^\s*claude:` (case-insensitive)
3. Order: sequenced items first, ascending (`list_todos` shows `[seq N]`, already listed first). Rest: critical → urgent → important → none, within a priority `order_index`. `N.` text prefix = fixed handle for deps, NOT order.
4. `--priority <level>` → that level and above only (`urgent` = critical+urgent).
5. `--max <N>` → cap items this run.

## Burn loop (per item — autonomous)

1. **Claim** — `start_todo` (→ in_progress) FIRST, before any work, as its own tool call. MUST land before reading/working the item — never skip, never batch, never go straight to `complete_todo`. The user tracks the live item in their tmux chip. One item per list is `in_progress` (`start_todo` moves it), so it is a marker, not a lock. Item stays in_progress for its whole work window, until step 4/5 closes it.
2. **Read** — strip `claude:`; read instruction + the todo's note (doc / script / ids).
3. **Work** — end-to-end. Existing gates HOLD:
   - commit / push / MR → CLAUDE.md git_rules: commit each item on green, push when the branch is the user's own (feature branch, or main of their personal repos); opening or updating an MR waits for "ship it" or a todo that says so.
   - destructive / irreversible / outward-facing NOT named in the todo → pause, surface, don't execute.
   - sev-5 (data loss, security, prod mutation) → stop, flag for human.
4. **Close (success)** — `complete_todo` (mark done) + `add_note` mode=`append` with the completion record (below). `append` keeps the user's original note (doc / script / context) intact.
5. **Blocked** (missing info / needs decision / external dep) → `add_note` (append) `BLOCKED {ts} — {what's needed}`, `revert_todo` (→ pending, re-queueable). Then: missing info only the user has → `add_todo owe=true type=unblock` on the same list (text: what the user must supply), so the ask lands in `daily`; external dep (another team, a release, an MR merge) → `deps` on the item it waits for, or a BLOCKED note naming it, no `owe` (`feature-management` → `### Owed items → daily twin` bar); needs a design decision → add it to the item's `ref:` doc Open Questions and mirror it as a `decision` on the same list, no `owe` (`feature-management` → `### Decision mirror`). Set the blocked item's `deps` to the new rank. Collect for end summary, continue.
6. Next item. Stopping (queue empty, blocked, or `--max` hit) → `start_todo` the next item first, the user's blocker when one exists (`doit_active_gate` blocks a stop with pending items and none `in_progress`).

## Completion record (appended on done)

Get the user's local clock — run `date "+%Y-%m-%d %H:%M %Z"` — then `add_note` mode=`append` this block:

```
DONE {timestamp}
- what was done
- files touched / commit sha / MR url / key output / decision made
- … (max 6 bullets)
```

- `{timestamp}` = the `date` output verbatim (the user's system time, not the model's idea of now).
- ≤ 6 bullets. Tight — what changed + identifiers, not narration.
- Identifiers (sha, MR url, shop_id) EXACT. Redact secrets.
- Append only — NEVER overwrite the original note.

## Stop conditions

- Queue empty
- sev-5 / destructive item → pause for human
- User interrupt
- 2 consecutive hard failures → stop, report

NOT stop conditions while `claude:` items stay pending: a summary naming the next item with no tool call; an offer to keep going; a decision list when none blocks the remaining items (blocked item goes to step 5, move on); a finished item or long turn. Status lines ride with the next tool call. Before the End summary, run `list_todos filter=pending` again; any unblocked `claude:` item within `--max` keeps burning. Step 3 gates still hold.

## Flags

| Flag | Effect |
|---|---|
| `--list <name>` | target list override |
| `--priority <level>` | burn this level + above (`critical` / `urgent` / `important`) |
| `--max <N>` | cap items this run |
| `--dry-run` | print the ordered queue + per-item plan, execute nothing; the one write is `start_todo` on the queue head when nothing is `in_progress` (`doit_active_gate`) |

## End summary

Table: `# | seq | priority | item | result (done / blocked / skipped) | note`. Blockers listed with what's needed from the user.

## Recurring

`/loop 10m /burn` → periodic drain. The `loop` skill owns scheduling; `/burn` runs once per fire (idempotent — completed items drop out of the queue; the `in_progress` item heads it).

## Ties to feature-todos

When the model proposes a feature-todo batch (`feature-management` → Feature todos → doit), code items the model can execute get the `claude:` prefix so a later `/burn` picks them up. User-kept code items and `decision` mirrors carry no prefix, so `/burn` skips them. Stale or noise items → `doit-prune` skill.

## Burn-down queue (`claude:` marker)

Any doit todo whose text starts `claude:` is assigned to the model. `/burn` drains them from one list, sequence-first (`[seq N]` ascending) then priority (critical→urgent→important→default), marking each `in_progress`, working it end-to-end under normal git/confirm gates, then auto-`complete_todo` + appending a DONE record (local `date` timestamp + ≤6 bullets of what was done; original note preserved). Target list = `{repo}-{feature}` capped at 24 chars (`cc-retry-loop`; no feature → `{repo}` or `{repo}-{worktree}`; rule in `feature-management`); `--list` overrides. One list per session keeps parallel sessions apart; `in_progress` is the active-item marker the user's chip shows.

- Assign: type `claude: {task}` in doit. Put doc link / script / id in the todo's note for context.
- Run: `/burn` (one drain) or `/loop 10m /burn` (periodic). Flags: `--list`, `--priority`, `--max`, `--dry-run`.
- Never auto-burns — `/burn` is the gate. Destructive / sev-5 items pause for human.
- Model-proposed code items get `claude:` when the model can execute them; `decision` items mirror doc Open Questions and never burn.

Full procedure → `burn` skill.
