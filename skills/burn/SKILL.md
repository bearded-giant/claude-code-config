---
name: burn
description: Burn down `claude:`-marked todos from a doit list, priority-first. Model claims each via in_progress, works it end-to-end (normal git/confirm gates still apply), marks done with an outcome note, moves to next. Defaults to the active session's feature/project list; `--list` targets another. Auto-fires when user says "burn my todos", "burn down", "burn the queue", "work my todos", or invokes /burn. Flags: --list, --priority, --max, --dry-run.
---
<!-- caveman:compressed -->

Worker queue. User assigns tasks by prefixing a doit todo with `claude:`. `/burn` picks them up by priority and works them down. doit data at `~/.local/share/nvim/doit/lists/` — touch only via doit MCP tools, never raw JSON.

## Marker

Todo text starts `claude:` (case-insensitive) → assigned to model.
- `claude: fix token expiry check in auth middleware`
- Instruction = text after `claude:`. The todo's `description`/note = doc link / script / identifiers / context.
- Non-`claude:` todos = user's own. `/burn` NEVER touches them.

## Target list (resolve in order)

1. `--list <name>` arg → use verbatim
2. else derive the repo-qualified, worktree-aware name:

```bash
root=$(git rev-parse --show-toplevel 2>/dev/null || pwd)
leaf=$(basename "$root"); par=$(basename "$(dirname "$root")")
case "$par" in *-wt) base="$par-$leaf";; *) base="$leaf";; esac
# active in_progress feature → "$base-$feature", else "$base"
```

   - `~/dev/claude-code-config` + feature `oauth-ttl` → `claude-code-config-oauth-ttl`
   - `~/dev/claude-code-config`, no feature → `claude-code-config`
   - `~/dev/python/cc-wt/local-dev-runner` + feature → `cc-wt-local-dev-runner-{feature}`
3. List doesn't exist → nothing to burn, report it. Don't `create_list` on a read.

ONE list per run. Other lists untouched — safe across 4-6 parallel sessions.

## Build the queue

1. `list_todos list={target} filter=pending`
2. Keep only items whose text matches `^\s*claude:` (case-insensitive)
3. Order: critical → urgent → important → none. Within a priority: numbered prefix / `order_index`.
4. `--priority <level>` → that level and above only (`urgent` = critical+urgent).
5. `--max <N>` → cap items this run.

## Burn loop (per item — autonomous)

1. **Claim** — `start_todo` (→ in_progress). This IS the lock: parallel sessions see it taken, won't double-grab.
2. **Read** — strip `claude:`; read instruction + the todo's note (doc / script / ids).
3. **Work** — end-to-end. Existing gates HOLD:
   - commit / push / MR → normal git rules. A todo that explicitly says "commit & push X" IS the authorization; silent default = no push.
   - destructive / irreversible / outward-facing NOT named in the todo → pause, surface, don't execute.
   - sev-5 (data loss, security, prod mutation) → stop, flag for human.
4. **Close (success)** — `complete_todo` (mark done) + `add_note` mode=`append` with the completion record (below). `append` keeps the user's original note (doc / script / context) intact.
5. **Blocked** (missing info / needs decision / external dep) → `add_note` (append) `BLOCKED {ts} — {what's needed}`, `revert_todo` (→ pending, re-queueable), collect for end summary, continue.
6. Next item.

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

## Flags

| Flag | Effect |
|---|---|
| `--list <name>` | target list override |
| `--priority <level>` | burn this level + above (`critical` / `urgent` / `important`) |
| `--max <N>` | cap items this run |
| `--dry-run` | print the ordered queue + per-item plan, execute nothing |

## End summary

Table: `# | priority | item | result (done / blocked / skipped) | note`. Blockers listed with what's needed from the user.

## Recurring

`/loop 10m /burn` → periodic drain. The `loop` skill owns scheduling; `/burn` runs once per fire (idempotent — claimed items are in_progress, completed items drop out of the pending queue).

## Ties to feature-todos

When the model proposes a feature-todo batch (`feature-management` → Feature todos → doit), items it can execute itself get the `claude:` prefix so a later `/burn` picks them up. User-only items get no prefix.
