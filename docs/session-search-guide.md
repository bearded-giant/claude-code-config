# Session History & Search Guide

Quick reference for finding past work across workspaces and Claude sessions.

## Workspace Commands (current project)

### /ws-history

Show recent sessions from `.giantmem/history/sessions.md`:

```bash
/ws-history              # last 10 sessions
/ws-history 20           # last 20 sessions
/ws-history abc12345     # show session details by ID
```

### /ws-history-search

Search workspace session files for keywords:

```bash
/ws-history-search foo-service
/ws-history-search "validation"
```

Searches: user prompts, files touched, commands run, discoveries.

---

## Global Commands (all projects)

### /session-history

List JSONL sessions from `~/.claude/projects/`:

```bash
/session-history                  # all recent sessions
/session-history my-project       # filter by project name
/session-history 30               # last 30 sessions
```

### /session-search (`css`)

Search actual Claude conversation content. Alias: `css`.

```bash
css -q cookie                          # last 30 days
css -q cookie --days 7                 # last 7 days
css -q cookie --project agent-chat     # filter to project
css -q "preprod session" --all         # search all time
css -q cookie --limit 5               # cap results
css -q cookie --paths                  # output only JSONL paths (for piping)
```

Extracts only human/assistant text from JSONL (filters out tool results, diffs, patches), ranks sessions by match count, shows clean snippets with `[YOU]`/`[CLAUDE]` tags. Each result includes `cd <dir> && claude --resume <id>` and the raw JSONL path.

### session-read (`csr`)

Drill into a specific session JSONL with clean filtered output. Alias: `csr`.

```bash
csr -f <path.jsonl> -q preprod_session       # show matches + 2 surrounding messages
csr -f <path.jsonl> -q cookie -C 5           # more context around matches
csr -f <path.jsonl> --no-filter              # dump entire conversation clean
```

Strips tool results, diffs, and system reminders. Marks matching messages with `<<`.

### Chaining css + csr

Use `--paths` on `css` to pipe the top result into `csr`:

```bash
# find sessions about cookies, then read the top hit for "preprod_session"
csr -f "$(css -q cookie --days 3 --paths | head -1)" -q preprod_session

# pick the 2nd result instead
csr -f "$(css -q cookie --paths | sed -n 2p)" -q preprod_session

# dump the full conversation of the top hit (no query filter)
csr -f "$(css -q cookie --paths | head -1)" --no-filter | less
```

The workflow is: `css` finds which session, `--paths` gives a pipeable path, `csr` reads it clean.

---

## Common Searches

| Goal | Command |
|------|---------|
| Find where I discussed X | `css -q "X"` |
| Drill into a specific match | `csr -f "$(css -q X --paths \| head -1)" -q "Y"` |
| What files did I create for feature Y | `/ws-history-search Y` then check "Files Touched" |
| Find a doc Opus wrote | `grep -r "topic" ~/dev/project/.giantmem/` |
| List recent work in project | `/ws-history` |
| Resume a specific session | `cd <project-dir> && claude --resume <session-id>` |

---

## Data Locations

| Data | Location |
|------|----------|
| Workspace session index | `.giantmem/history/sessions.md` |
| Workspace session details | `.giantmem/history/sessions/*.md` |
| Workspace discoveries | `.giantmem/context/discoveries.md` |
| JSONL conversations | `~/.claude/projects/{project}/*.jsonl` |
| Global history index | `~/.claude/history.jsonl` |

---

## Tips

- Session files contain: user prompts, files modified/created/read, bash commands, discoveries
- JSONL files contain: full conversation including Claude's thinking and responses
- Use `/session-search` when looking for Claude's explanations
- Use `/ws-history-search` when looking for what files were touched
- Session IDs are 8-char hex (e.g., `abc12345`) - use full UUID for `claude --resume`
