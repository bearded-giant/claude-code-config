---
description: Display or search previous workspace sessions from .giantmem/history/. Triggers when user says "what did I work on", "show recent sessions", "find sessions about X", "search history for Y", or references a session ID.
allowed-tools: Bash, Read, Grep
---

Display previous sessions from `.giantmem/history/sessions.md`, view a single session by ID, or grep all session files for a keyword.

## Arguments

`$ARGUMENTS` is parsed as:

- `--search <query>` → grep mode: search across session files for the query (case-insensitive). Looks in User Prompts, Files Touched, Commands Run, Discoveries.
- `<8-hex-id>` → detail mode: show full session details for that ID.
- `<count>` (integer) → list mode: show last N sessions. Default 10.
- empty → list mode, default 10.

Examples:
- `/ws-history` → last 10 sessions
- `/ws-history 25` → last 25 sessions
- `/ws-history cf328fa4` → details for session cf328fa4
- `/ws-history --search jwks` → all sessions mentioning jwks

## Steps

1. Check `.giantmem/history/sessions.md` and `.giantmem/history/sessions/` exist. If neither, inform user no history found.

2. **--search mode:**
   - Grep across `.giantmem/history/sessions/*` for query (case-insensitive)
   - Display matches grouped by session:
     ```
     ## Session 2026-01-28 (cf328fa4)
     - [User Prompt] "I want to add jwks validation..."
     - [File] .giantmem/features/jwks-fetch/spec.md
     ```
   - Show tip: `/ws-history {id}` for full session details

3. **Detail mode (8-hex ID):**
   - Find matching file in `.giantmem/history/sessions/`
   - Display full session details
   - Show resume hint: `claude --resume {full-session-id}`

4. **List mode (no arg or integer):**
   - Parse `sessions.md`, show last N entries as table:
     ```
     | Date       | Tag       | ID       | Description                              |
     |------------|-----------|----------|------------------------------------------|
     | 2026-01-28 | config    | cf328fa4 | ccstatusline display issue...            |
     ```
   - Tip: `/ws-history {id}` for details, `/ws-history --search <q>` to grep.

ARGUMENTS: $ARGUMENTS
