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

### /session-search

Search actual Claude conversation content:

```bash
/session-search "foo validation"
/session-search "bar config" my-project
```

This searches the JSONL files where Claude's full responses live.

---

## Direct Grep Commands

For more control, grep the files directly.

### Search workspace session files

```bash
# search all session summaries
grep -r "foo" ~/dev/my-project/.giantmem/history/sessions/

# search with context
grep -r -B2 -A2 "validation" ~/dev/my-project/.giantmem/history/sessions/

# find sessions that touched a specific file
grep -l "router.lua" ~/dev/my-project/.giantmem/history/sessions/*.md

# search discoveries
grep "discovery" ~/dev/my-project/.giantmem/context/discoveries.md
```

### Search JSONL conversations

```bash
# find sessions mentioning a topic
rg -l "foo" ~/.claude/projects/*my-project*/*.jsonl

# extract assistant text with context
rg -i "bar" ~/.claude/projects/*my-project*/*.jsonl | head -20

# search across all projects
rg -i "baz validation" ~/.claude/projects/*/*.jsonl

# extract and search assistant content (slower but cleaner)
for f in ~/.claude/projects/*my-project*/*.jsonl; do
  jq -r 'select(.type == "assistant") | .message.content[]? | select(.type == "text") | .text' "$f" 2>/dev/null | rg -i "foo" -C1
done
```

### Find files created in sessions

```bash
# list all files created across sessions
grep -h "^- /Users" ~/dev/my-project/.giantmem/history/sessions/*.md | sort -u

# find sessions that created md files
grep -l "\.md$" ~/dev/my-project/.giantmem/history/sessions/*.md
```

---

## Common Searches

| Goal | Command |
|------|---------|
| Find where I discussed X | `/session-search "X"` |
| What files did I create for feature Y | `/ws-history-search Y` then check "Files Touched" |
| Find a doc Opus wrote | `grep -r "topic" ~/dev/project/.giantmem/` |
| List recent work in project | `/ws-history` |
| Resume a specific session | `claude --resume <session-id>` |

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
