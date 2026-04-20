---
description: "Push an update to the sync file for the current feature. Interactive menu or direct: /update-sync <section> <content>."
argument-hint: "[section] [content] (sections: shared | handoff | decision | scratch)"
---

Write to the cross-repo sync file for the active feature. Choose section, provide content, skill handles formatting + timestamps + write-discipline rules.

## Arguments

Two modes:

**Interactive** (no args): show menu, prompt for content.

**Direct** (2+ args): `/update-sync <section> <content>`
- `section`: one of `shared`, `handoff`, `decision`, `scratch`
- `content`: the text to write. Quoted if multi-word.

For `handoff` in direct mode, target defaults to all peers. To target a specific peer: `/update-sync handoff "<content>" --to <peer-repo>`.

## Steps

1. **Locate sync file**
   - Read active feature's `meta.json` → `sync_refs[0]`.
   - If empty or file missing: same auto-detach flow as `/read-sync`. Stop if detached.

2. **Gather identity**
   - Current repo: `basename $(git rev-parse --show-toplevel)`.
   - Timestamp: `date +"%Y-%m-%d %H:%M"` (local) for handoff/decision; `date -u +"%Y-%m-%dT%H:%M:%SZ"` (UTC) for `sync_last_read`.
   - Peer repos: parse `Participants` section, exclude current repo.

3. **Interactive mode** (no args): prompt user with menu
   ```
   Update sync for <topic>:
   1. Shared State (facts both sessions agree on)
   2. Handoff (note for peer to pick up)
   3. Decision (dated log entry)
   4. Own scratch (this repo's working notes)
   ```
   After selection:
   - Shared State: ask "what changed?" then "where in Shared State does this go? (append / replace / under subsection <name>)"
   - Handoff: ask "content?" then "target peer? (<list of peers> / all)"
   - Decision: ask "decision + rationale?"
   - Scratch: ask "content?"

4. **Write rules per section**

   **Shared State** (`## Shared State`)
   - Append mode: add new bullet/line at end, prefix with `<YYYY-MM-DD>:` for traceability.
   - Replace mode: prompt user to confirm before overwriting. Preserve the section heading.
   - Subsection mode: if subsection doesn't exist, create `### <name>` then add content. If exists, append under it.

   **Handoff** (`## Handoff`)
   - Always append. Never edit existing entries.
   - Format: `<YYYY-MM-DD HH:MM> [<current-repo> -> <target>]: <content>` where `<target>` is peer repo name or `all`.

   **Decision** (`## Decisions`)
   - Always append. Never edit existing entries.
   - Format: `- <YYYY-MM-DD>: <content>`
   - If content supersedes prior decision, user should reference it in the content itself (e.g., "Supersedes 2026-04-18 decision on X because Y").

   **Scratch** (`## <current-repo> scratch`)
   - If section missing, create at end of file.
   - Append content as new line/bullet. Never edit peer scratch.

5. **Write to file**
   - Read → modify in memory → write. Preserve all other sections verbatim.
   - Do NOT touch peer scratch sections under any circumstances.

6. **Update `sync_last_read`**
   - Bump to current UTC ISO timestamp in `meta.json` + `features.json`. You just wrote, so nothing "new" for you to read.

7. **Output**
   - Show: section written to, the line(s) added verbatim, and reminder to peer: "Peer sessions should run /read-sync to pick this up."

## Examples

Direct handoff:
```
/update-sync handoff "Auth contract finalized. JWT payload adds session_tier field." --to langgraph-harness
```

Direct decision:
```
/update-sync decision "Use trace_id on all inbound envelopes for observability parity with monolith."
```

Interactive scratch:
```
/update-sync
> 4
> Investigating why orchestrator rejects tokens missing session_tier — looks like validator enforces all fields.
```

## Anti-patterns (refuse or warn)

- Writing under peer's scratch section → refuse, suggest `handoff` instead.
- Editing existing handoff/decision entries → refuse, suggest new entry that supersedes.
- Rewriting `Shared State` wholesale in direct mode → require interactive confirmation.
