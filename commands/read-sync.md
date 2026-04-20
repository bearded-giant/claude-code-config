---
description: "Read the sync file for the current feature. Surface only deltas since last read (new handoffs addressed here, shared state changes, new decisions)."
argument-hint: "[--full]"
---

Pull updates from the cross-repo sync file for the active feature. Delta-only by default — compares entries to `meta.json.sync_last_read` timestamp and surfaces only what's new.

## Arguments

- `--full`: show entire sync file instead of deltas. Use when user wants full context (e.g., first read in a new session even if timestamp looks recent).

## Steps

1. **Locate sync file**
   - Read active feature's `meta.json` → `sync_refs[0]`.
   - If empty: "No sync file attached. Run /sync-feature <topic> first." Stop.

2. **Handle missing file (auto-detach)**
   - If path doesn't exist, check `~/giantmem_archive/sync/archive/` for matching `<topic>_*.md`.
   - If archived match found: strip `sync_refs` from meta.json, `sync_file:` from facts.md, `sync_refs` from features.json. Tell user: "Sync `<topic>` archived by peer — detached." Stop.
   - If no archive match: surface to user, do NOT auto-clean.

3. **Read sync file + extract repo identity**
   - Current repo short name: `basename $(git rev-parse --show-toplevel)`.
   - Read last-read timestamp from `meta.json.sync_last_read` (ISO format). If missing, treat as epoch 0.

4. **Compute deltas** (skip if `--full`)
   - Parse `Participants` → show current participant list (always, it's small).
   - Parse `Handoff` section: extract timestamped lines. Filter to entries with timestamp > `sync_last_read` AND targeted at current repo (`[* -> <current-repo>]` or `[* -> all]`).
   - Parse `Decisions`: filter entries with date >= `sync_last_read` date.
   - `Shared State`: no timestamps, so diff by comparing file mtime to `sync_last_read`. If mtime > last_read, surface entire `Shared State` section with note: "Shared State changed since last read — review in full."
   - Peer scratch sections: NOT surfaced by default (too noisy). Note only if user passes `--full`.

5. **Output**
   - If no deltas: "Sync clean. Last read: <timestamp>. No new handoffs, decisions, or shared state changes."
   - Else: print each delta section with header. Terse. Quote handoff entries verbatim.

6. **Update `sync_last_read`**
   - Set `meta.json.sync_last_read` to current ISO timestamp (`date -u +"%Y-%m-%dT%H:%M:%SZ"`).
   - Mirror to `features.json` entry.

## Example output (deltas)

```
Sync: 2-1-orchstrator-svc
Last read: 2026-04-20T10:02:00Z
Now:       2026-04-20T14:30:12Z

## New handoffs (to langgraph-harness)
- 2026-04-20 11:02 [agent-chat -> langgraph-harness]: JWT payload now includes `session_tier`. Handle missing field for backward compat.
- 2026-04-20 13:45 [agent-chat -> langgraph-harness]: Auth contract finalized. See Shared State → Auth.

## New decisions
- 2026-04-20: Adopt `trace_id` on all inbound envelopes. Rationale: observability parity with monolith.

## Shared State (changed)
[full section dumped]

Updated sync_last_read.
```
