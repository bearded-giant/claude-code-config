# Session search

Find past work across workspaces and Claude session transcripts. **Different corpus from artifacts** — see [gma-search.md](gma-search.md) for typed artifact search.

## Workspace sessions (current project)

`/ws-history` command removed 2026-08-30 (unused). Same data, direct reads:

```bash
grep -n foo .giantmem/history/sessions.md       # keyword over session index
ls .giantmem/history/sessions/                  # per-session details
giantmem session resume <id>                    # resume by id
```

## Global sessions (all projects, JSONL transcripts)

`/session-search` command removed 2026-08-30 — the `css` script (`scripts/session-search`) is the tool:

```bash
css -q cookie                                   # last 30d
css -q cookie --days 7
css -q cookie --project agent-chat
css -q "preprod session" --all                  # all time
css -q cookie --limit 5
css -q cookie --paths                           # pipeable paths only
```

`css` extracts human/assistant text only, filters tool results / diffs / system reminders. Each result includes `cd <dir> && claude --resume <id>` + raw JSONL path.

## Drill into one session

```bash
csr -f <path.jsonl> -q preprod_session          # matches + 2 surrounding messages
csr -f <path.jsonl> -q cookie -C 5              # more context
csr -f <path.jsonl> --no-filter                 # full conversation
```

## Chain

```bash
# top hit's "preprod_session" detail
csr -f "$(css -q cookie --days 3 --paths | head -1)" -q preprod_session

# 2nd result
csr -f "$(css -q cookie --paths | sed -n 2p)" -q preprod_session

# full conversation of top hit
csr -f "$(css -q cookie --paths | head -1)" --no-filter | less
```

## Common searches

| Goal | Command |
|---|---|
| Where I discussed X | `css -q "X"` |
| Drill into a match | `csr -f "$(css -q X --paths \| head -1)" -q "Y"` |
| Files I created for feature Y | `grep -n Y .giantmem/history/sessions.md` |
| Find Opus prose | `grep -r "topic" ~/dev/project/.giantmem/` |
| Recent project work | `tail .giantmem/history/sessions.md` |
| Resume session | `cd <dir> && claude --resume <uuid>` |

## Data locations

| Data | Path |
|---|---|
| Workspace session index | `.giantmem/history/sessions.md` |
| Workspace session details | `.giantmem/history/sessions/*.md` |
| Workspace discoveries | `.giantmem/context/discoveries.md` |
| JSONL transcripts | `~/.claude/projects/{project}/*.jsonl` |
| Global history | `~/.claude/history.jsonl` |

## Tips

- Session files = prompts + files touched + commands + discoveries.
- JSONL = full conversation including Claude thinking.
- `css` for Claude's explanations. `.giantmem/history/` for what files were touched.
- Session IDs are 8-char hex; use full UUID for `claude --resume`.

## See also

- [gma-search.md](gma-search.md) — typed artifact search (different corpus: proposals, delta-specs, tasks, etc.)
- [usage-summary.md](usage-summary.md) — artifact + spec workflow
