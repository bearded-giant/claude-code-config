---
name: sync-feature
description: >-
  Read/write discipline for cross-repo sync files created by /sync-feature.
  Use when the active feature's meta.json has `sync_refs` pointing at a file
  in ~/giantmem_archive/sync/, or when user mentions "the sync file",
  "the other session", "peer session", or cross-repo coordination on a feature.
---

# sync-feature

Two or more Claude Code sessions working the same feature in different repos/worktrees coordinate through a shared markdown file at `~/giantmem_archive/sync/<topic>.md`. This skill governs how to use it so sessions don't stomp each other.

## Detect the sync file

On session start or when user references cross-repo work:

1. Read active feature's `meta.json`. If `sync_refs` is non-empty, that's the sync file path.
2. Or check `facts.md` for a `sync_file:` line.
3. If neither exists but user describes cross-repo work, suggest running `/sync-feature <topic>`.

## Missing sync file (auto-detach)

If `sync_refs` points at a path that no longer exists (peer session ran `/sync-stop` and archived it):

1. Check `~/giantmem_archive/sync/archive/` for a file matching `<topic>_*.md`. If found, the sync was intentionally closed.
2. Strip the stale pointer from current session's feature:
   - Remove path from `meta.json.sync_refs`.
   - Remove `sync_file:` line from `facts.md`.
   - Remove `sync_refs` from `features.json` entry.
3. Tell user in one line: "Sync `<topic>` was archived by peer — detached this feature." Do not re-create or re-attach unless user asks.
4. If file is gone AND no archive match exists, surface to user — possible manual delete, don't auto-clean metadata.

## Read cadence

- **Session start**: read the sync file fully. Internalize `Shared State`, `Handoff`, `Decisions`.
- **Before big decisions**: re-read `Shared State` + `Decisions` — peer may have updated while you worked.
- **User asks "check sync" / "what did the other session do"**: read fully, summarize diff from last read if useful.
- Do NOT poll every turn. Sync is not a chat channel; it's a shared state doc.

## Write discipline

Rules that keep two sessions from fighting:

1. **Own your scratch section only.** File has `## <repo-short-name> scratch` per participant. Write your notes there. Never edit peer's scratch.
2. **Shared sections are append-or-structured-edit.** `Shared State`, `Decisions`, `Handoff` are joint. When editing:
   - `Handoff`: append timestamped lines. Never rewrite peer's handoff entries.
     Format: `YYYY-MM-DD HH:MM [<from-repo> -> <to-repo>]: <message>`
   - `Decisions`: append dated entry. Never retroactively edit a decision — add a new dated one that supersedes it.
   - `Shared State`: this is the "source of truth" section. Edit in place when facts change, but preserve structure and cite the commit/file that prompted the change.
3. **Contract changes require a Handoff entry.** If you change an interface/schema/endpoint the peer depends on, write both the updated contract in `Shared State` AND a `Handoff` note pointing at it.
4. **No long narrative.** Keep entries terse. Tables, bullet points, short sentences. Sync file is coordination, not a journal.
5. **Always include timestamps** on handoff + decision entries. Use user's local date (`date +"%Y-%m-%d %H:%M"`).

## Conflict handling

If you open the sync file and see your scratch section contains content you didn't write:
- **Do not delete it.** Peer may have mis-sectioned a note there.
- Move the stray content into `Handoff` with a note: `YYYY-MM-DD HH:MM [<peer-repo> -> <me>]: (moved from my scratch section) <content>`.
- Flag in chat to user.

If a `Shared State` fact conflicts with what your repo shows (e.g., sync says endpoint is `/foo`, code says `/bar`):
- Trust the code, not the sync.
- Update `Shared State` with the correct fact + a `Decisions` entry noting the divergence and resolution.

## Example handoff entries

```
2026-04-20 10:15 [agent-chat -> langgraph-harness]: Auth contract finalized in Shared State. JWT payload now includes `session_tier`. Consumer must handle missing field for backward compat.

2026-04-20 11:02 [langgraph-harness -> agent-chat]: Orchestrator requires `trace_id` on every inbound. Please add to request envelope. Blocking integration test.
```

## When to prompt user to update sync

Prompt the user (don't silently write) when:
- You're about to publish a breaking contract change to `Shared State`.
- You're closing out a `Handoff` item the peer raised.
- A `Decision` would supersede a prior one.

Silent writes (OK without prompting) are: your own scratch notes, clarifying questions to peer under your scratch, typo fixes in your own prior entries.

## Completion

When the feature is complete in both repos:
- Add final `Decisions` entry: "Feature complete. Sync closed <date>."
- User can archive manually (move to `~/giantmem_archive/sync/archive/`) — skill does not auto-archive.
