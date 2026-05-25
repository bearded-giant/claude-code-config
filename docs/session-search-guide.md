# Session search

Find past work across workspaces and Claude session transcripts. **Different corpus from artifacts** — see [gma-search.md](gma-search.md) for typed artifact search.

## Workspace sessions (current project)

```bash
/ws-history                 # last 10 sessions
/ws-history 20              # last 20
/ws-history abc12345        # details by 8-char id
/ws-history --search foo    # keyword over prompts + files + commands + discoveries
```

Reads `.giantmem/history/sessions.md` + `.giantmem/history/sessions/*.md`.

## Global sessions (all projects, JSONL transcripts)

```bash
/session-search --list                          # all recent
/session-search --list --project my-project
/session-search --list --limit 30

css -q cookie                                   # last 30d, alias for /session-search
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
| Files I created for feature Y | `/ws-history --search Y` |
| Find Opus prose | `grep -r "topic" ~/dev/project/.giantmem/` |
| Recent project work | `/ws-history` |
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
- `/session-search` for Claude's explanations. `/ws-history --search` for what files were touched.
- Session IDs are 8-char hex; use full UUID for `claude --resume`.

## See also

- [gma-search.md](gma-search.md) — typed artifact search (different corpus: proposals, delta-specs, tasks, etc.)
- [usage-summary.md](usage-summary.md) — artifact + spec workflow
