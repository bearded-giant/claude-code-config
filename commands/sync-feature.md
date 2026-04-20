---
description: "Create or attach a cross-repo sync file for a feature. Shared file lives at ~/giantmem_archive/sync/ and is referenced from each participant feature's metadata."
argument-hint: "<topic-slug> [--path <abs-path>]"
---

Init or attach a cross-repo sync file for coordinating two+ Claude Code sessions working the same feature in different repos/worktrees. The sync file lives OUTSIDE any repo, at `~/giantmem_archive/sync/<topic>.md`. Each participating feature's `meta.json` + `facts.md` get a pointer to it.

## Arguments

- `topic-slug`: kebab-case identifier shared across sessions (e.g., `2-1-orchstrator-svc`). Required.
- `--path <abs-path>`: (optional) override default location. Use when attaching to a sync file that already lives elsewhere.

## Behavior (idempotent)

One command, two modes, auto-detected:
- Sync file does NOT exist → **init mode**: create file + register current feature as first participant.
- Sync file EXISTS → **attach mode**: append current feature to `Participants` header, update metadata.

## Steps

1. **Resolve sync file path**
   - Default: `~/giantmem_archive/sync/<topic-slug>.md`
   - If `--path` provided, use that.
   - Ensure `~/giantmem_archive/sync/` exists (`mkdir -p`).

2. **Identify current feature**
   - Read `.giantmem/features/features.json` in current workspace.
   - Find entry with `"status": "in_progress"`. That is the participant feature.
   - If no active feature, error: "No in_progress feature found. Run /start-feature or /new-feature first."

3. **Identify current repo**
   - `git rev-parse --show-toplevel` for absolute repo path.
   - Repo short name: basename of that path.

4. **Init mode** (file missing): create sync file with this template:

```markdown
# Sync: <topic-slug>

Created: <YYYY-MM-DD>
Status: active

## Participants

- <repo-short-name>: <abs-repo-path> :: features/<feature-name>

## Shared State

<!-- facts both sessions agree on: contracts, interfaces, decisions -->

## Handoff

<!-- timestamped notes when one session needs the other to pick something up -->
<!-- format: YYYY-MM-DD HH:MM [from-repo -> to-repo]: message -->

## <repo-short-name> scratch

<!-- this session's working notes, questions, TODOs -->

## Decisions

<!-- dated log of joint decisions with rationale -->
```

5. **Attach mode** (file exists):
   - Read sync file.
   - If current repo is NOT already in `## Participants`, append a new line there: `- <repo-short-name>: <abs-repo-path> :: features/<feature-name>`
   - If `## <repo-short-name> scratch` section doesn't exist, append it at end with an empty body.
   - If already registered, no-op that part (still proceed to metadata update).

6. **Update feature metadata**

   **meta.json** — add/update `sync_refs` array + init `sync_last_read`:
   ```json
   {
     "sync_refs": ["<abs-sync-path>"],
     "sync_last_read": "<current-UTC-ISO-timestamp>"
   }
   ```
   Merge `sync_refs` with existing array; dedupe. Set `sync_last_read` to `date -u +"%Y-%m-%dT%H:%M:%SZ"` — init mode has nothing prior to read, attach mode user should run `/read-sync` next if they want peer's prior state.

   **facts.md** — add (or update) under `## Identifiers`:
   ```
   sync_file: <abs-sync-path>
   ```

7. **Update features.json cache**
   - Add `"sync_refs": ["<abs-sync-path>"]` to the current feature's entry (dedupe if present).

8. **Output summary**
   - Mode used (init / attach)
   - Sync file path
   - Current participants (parsed from header)
   - Reminder: peer session should run `/sync-feature <topic-slug>` from its own repo to attach.

## Detach / delist

If user passes `--detach`, remove current repo's participant line, remove its scratch section (ask first — may contain notes), and strip `sync_refs` entry + `sync_file` line from this feature's metadata. Do NOT delete the sync file itself unless zero participants remain AND user confirms.
