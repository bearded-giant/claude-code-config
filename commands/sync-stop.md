---
description: "Stop a cross-repo sync: archive the sync file and strip sync refs from the current feature. Run in each participating session."
argument-hint: "[topic-slug]"
---

Archive a cross-repo sync file and detach the current feature from it. Run this in whichever session initiates the stop — other sessions will detect the missing file on next read (see sync-feature skill) and self-detach.

## Arguments

- `topic-slug`: (optional) Explicit topic. If omitted, resolve from current feature's `meta.json.sync_refs[0]`.

## Steps

1. **Resolve sync file path**
   - If arg given: `~/giantmem_archive/sync/<topic-slug>.md`.
   - Else: read active feature's `meta.json` → `sync_refs[0]`.
   - Else: error "No sync file found for current feature."

2. **Show sync state before archiving**
   - Print participants list from sync file header.
   - Print last 5 `Handoff` entries.
   - Ask user to confirm archive. Show: `Archive <path>? (y/n)`

3. **Archive**
   - `mkdir -p ~/giantmem_archive/sync/archive/`
   - Rename: `<path>` → `~/giantmem_archive/sync/archive/<topic-slug>_<YYYY-MM-DD>.md`
   - If target archive path already exists, append `_1`, `_2`, etc.

4. **Detach current feature**
   - Remove sync file path from `meta.json.sync_refs`.
   - Remove `sync_file:` line from `facts.md`.
   - Remove `sync_refs` from this feature's entry in `features.json`.

5. **Output summary**
   - Archived path.
   - Participants who still need to detach (remind user to run `/sync-stop` in each peer session, OR note that those sessions will auto-detach via the sync-feature skill when they next try to read and find the file gone).

## Notes

- This only detaches the CURRENT session's feature from the sync. Peer sessions' metadata still has `sync_refs` until they either run `/sync-stop` themselves or the skill auto-cleans on next read.
- The skill handles graceful degradation: if a session tries to read a missing sync file, it strips its own `sync_refs` / `sync_file` and stops referencing the sync. No error cascade.
