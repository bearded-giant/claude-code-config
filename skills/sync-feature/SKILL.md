---
name: sync-feature
description: >-
  Read/write discipline for cross-repo sync files created by /sync-feature.
  Use when the active feature's meta.json has `sync_refs` pointing at a file
  in ~/giantmem_archive/sync/, or when user mentions "the sync file",
  "the other session", "peer session", or cross-repo coordination on a feature.
---

# sync-feature

Two or more Claude Code sessions working the same feature in different repos/worktrees coordinate through a shared markdown file at `~/giantmem_archive/sync/<topic>.md`. This skill governs how to use it so sessions don't stomp each other and don't burn tokens polling.

## Commands (user-driven; skill does not auto-read or auto-write)

| Command | Purpose |
|---------|---------|
| `/sync-feature <topic>` | Init file or attach current feature (idempotent) |
| `/read-sync [--full]` | Pull deltas since last read. Updates `sync_last_read` |
| `/update-sync [section content]` | Push update. Interactive menu or direct args |
| `/sync-stop [topic]` | Archive file, strip refs from current feature |

**The skill never tails, polls, or auto-reads.** Reads and writes only happen via these commands. This keeps token usage bounded and control in the user's hands.

## When to suggest a command (not execute)

- User references peer work ("what did the other session do?", "any updates?") AND `sync_last_read` is older than sync file's mtime → suggest `/read-sync`.
- User describes a decision, contract change, or handoff-worthy event AND has NOT run `/update-sync` for it → suggest `/update-sync`.
- User mentions cross-repo work AND no `sync_refs` on active feature → suggest `/sync-feature <topic>`.

Never run these commands on your own initiative. Always let user invoke.

## State tracking

Feature's `meta.json` carries:
```json
{
  "sync_refs": ["/abs/path/to/sync.md"],
  "sync_last_read": "2026-04-20T14:30:12Z"
}
```
Mirrored to `features.json`. `sync_last_read` updates on both `/read-sync` and `/update-sync` (writing implies you know current state).

## Missing sync file (auto-detach)

If `sync_refs` points at a path that no longer exists (peer session ran `/sync-stop` and archived it):

1. Check `~/giantmem_archive/sync/archive/` for matching `<topic>_*.md`. If found, sync was intentionally closed.
2. Strip stale pointer:
   - `meta.json.sync_refs` → remove path
   - `meta.json.sync_last_read` → remove key
   - `facts.md` → remove `sync_file:` line
   - `features.json` → remove `sync_refs` + `sync_last_read` from entry
3. One-line to user: "Sync `<topic>` archived by peer — detached this feature."
4. If file gone AND no archive match, surface to user. Possible manual delete. Do NOT auto-clean metadata.

This auto-detach runs only when a sync command is invoked and finds the file missing. Skill does not background-check.

## File structure (canonical sections)

```markdown
# Sync: <topic>

Created: <YYYY-MM-DD>
Status: active

## Participants
- <repo>: <abs-path> :: features/<feature-name>

## Shared State
<!-- facts both sessions agree on. edit in place, preserve structure -->

## Handoff
<!-- append-only timestamped lines: YYYY-MM-DD HH:MM [from -> to]: msg -->

## Decisions
<!-- append-only dated entries: - YYYY-MM-DD: content -->

## <repo> scratch
<!-- per-participant scratch. peers never edit each other's -->
```

## Write discipline (enforced by /update-sync, stated here for reference)

1. **Own scratch only.** Never edit peer's scratch section.
2. **Handoff + Decisions are append-only.** Never rewrite existing entries. To correct, append a new entry that supersedes.
3. **Shared State is editable in place.** Preserve section structure. Cite commit/file when changing a fact.
4. **Contract changes require a Handoff entry pointing at the Shared State update.** Peer won't notice a Shared State diff alone — the handoff is the signal.
5. **Terse.** Short sentences, bullets, tables. Sync is coordination, not a journal.
6. **Timestamps always.** Handoff uses `YYYY-MM-DD HH:MM` (local). Decisions use `YYYY-MM-DD` (local). `sync_last_read` uses UTC ISO.

## Conflict handling

**Scratch stomp** (your scratch section contains content you didn't write):
- Do NOT delete. Peer may have mis-sectioned a note.
- Move content to `Handoff` via `/update-sync handoff "(moved from <my-repo> scratch) <content>" --to <peer>`.
- Flag to user.

**Shared State vs code divergence** (sync says `/foo`, code says `/bar`):
- Trust code, not sync.
- Update Shared State via `/update-sync shared "<corrected fact>"` + add Decision via `/update-sync decision "<rationale for divergence resolution>"`.

## Example handoff flow

Session A (agent-chat) finalizes auth contract:
```
/update-sync shared "JWT payload now includes session_tier. See auth/jwt.py:42."
/update-sync handoff "Auth contract finalized. session_tier added. Handle missing for backward compat." --to langgraph-harness
```

Session B (langgraph-harness) later:
```
/read-sync
# surfaces both the shared state change and the handoff
```

## Completion

When feature complete in both repos:
- Final Decision via `/update-sync decision "Feature complete. Sync closing."`
- Then `/sync-stop <topic>` to archive.
