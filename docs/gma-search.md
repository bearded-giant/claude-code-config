# gma + giantmem artifact search — cheat sheet

How to find typed artifacts (proposal/delta-spec/tasks/plan/research/...) AND keyword/phrase content. Two engines:

- **`giantmem artifact ...`** — typed query by frontmatter (type, status, feature, domain, repo, branch, updated). Cross-repo.
- **`giantmem find ...`** — FTS5 content search across live workspaces + archives + Claude session transcripts.
- **`gma`** — fzf-driven interactive picker over `giantmem artifact list --json`.

Pick the engine by what you have. Frontmatter known → `artifact`. Just a phrase → `find`.

## 1. By metadata (artifact)

### Current worktree (default scope)

```bash
giantmem artifact list                          # everything in this worktree
giantmem artifact list -t proposal              # one type
giantmem artifact list -t proposal,delta-spec   # multiple types (CSV)
giantmem artifact list -s ready                 # status filter
giantmem artifact list -f openspec-compare      # one feature
giantmem artifact list -d auth                  # one domain
```

### Across worktrees of the same repo

```bash
giantmem artifact list --repo claude-code-config --branch feat/openspec-compare
```

Branch filter is the disambiguator when a repo has multiple worktrees on disk.

### Cross-repo

```bash
giantmem artifact list --repo all -t delta-spec               # every delta-spec everywhere
giantmem artifact list --repo all --include-archived          # +~/giantmem_archive/*/latest/
giantmem artifact list --repo all -f session-cookie           # one feature name across repos
```

### Stale / orphans

```bash
giantmem artifact stale --days 30                # this repo, not touched in 30d, status != done
giantmem artifact stale --all-repos --days 90    # cross-repo
giantmem artifact orphans                        # files in artifact slots lacking frontmatter
```

### JSON for piping

```bash
giantmem artifact list --json | jq .             # pretty print
giantmem artifact list --json | jq '.artifacts | length'
```

## 2. By content (keyword / phrase)

`giantmem find` runs FTS5 across **live** workspace docs (live.db) and **archived** workspaces + Claude session transcripts (archives.db).

### Plain queries

```bash
giantmem find "session timeout"            # phrase
giantmem find redis OR memcache            # FTS5 operators pass through
giantmem find auth NOT logout              # boolean
giantmem find "exact phrase here"          # double-quoted = literal substring
giantmem find prefix*                      # FTS5 prefix match
```

Plain text is auto-quoted so punctuation works: `giantmem find hub-and-spoke` is safe.

### Scope filters

```bash
giantmem find "session" --project claude-code-config        # LIKE match on project name
giantmem find "redis" --source workspace                    # workspace | session | domain
giantmem find "auth" --type research                        # dir_type filter
giantmem find "jwt" --feature jwt-session-cookie            # live-only feature filter
giantmem find "rate limit" --since 7d                       # last 7 days
giantmem find "panic" --until 2026-04-01                    # before date or e.g. 30d ago
giantmem find "x" --live                                    # live.db only (current workspaces)
giantmem find "x" --archive                                 # archives.db only
```

### Session-transcript per-line expansion

When searching session transcripts, `--tool` / `--ext` flips results from file-level to per-line matches. Each row = one Claude tool_use line decoded into role + tool + file + excerpt.

```bash
giantmem find "session_id" --source session --tool Write,Edit       # find writes
giantmem find "TODO" --source session --tool Bash                   # bash commands
giantmem find "import" --source session --ext py                    # python files touched
giantmem find "session" --source session --tool Read --include-read # Read calls (hidden by default)
```

### Output modes

```bash
giantmem find x --json           # JSON
giantmem find x --paths          # absolute paths only
giantmem find x --full           # include matched-content snippet
giantmem find x -n 50            # bump limit (default 20)
giantmem find x --no-interactive # disable fzf even in a TTY
```

In a TTY, `find` defaults to an fzf picker with a preview pane (`bat` highlight, `jq`-decoded for JSONL session lines).

## 3. gma — interactive picker

`gma` wraps `giantmem artifact list --json` through fzf with a preview pane. Default scope: `--repo all`.

```bash
gma                                          # everything across worktrees
gma -t delta-spec                            # one type
gma -t delta-spec -d workflow                # type + domain
gma -f openspec-compare                      # one feature
gma --include-archived                       # include ~/giantmem_archive/
gma --repo claude-code-config                # scope to one repo
gma --repo current                           # only the current worktree
gma --path                                   # print path on Enter (no $EDITOR open)
vim "$(gma --path)"                          # pick + edit pattern
```

Hotkeys inside fzf:

- `Enter` — open in `$EDITOR` (or print path with `--path`)
- `Esc` — cancel
- `Ctrl-/` — toggle preview window

## 4. From inside Claude (MCP, no shell)

The `giantmem-search` MCP server exposes typed-artifact tools:

| Tool | Use |
|---|---|
| `find_artifact(type, status, feature, domain, repo, branch, query, limit)` | typed search + optional fulltext `query`. Returns ID + path + status + snippet (when query matches). |
| `get_artifact(id)` | full frontmatter + body for one ID. |
| `list_features_with_artifacts(repo, artifact_types)` | "every feature with open delta-specs across all repos." |

Plus content search:

| Tool | Use |
|---|---|
| `search_archive(query, project, source_type, topic, tool_filter, ext_filter, include_read, limit)` | FTS5 across archives + sessions. Same engine as `giantmem find`. |

When Claude needs to find something, it should call these — they index typed metadata + content without 12 greps.

## 5. Common recipes

### What's active in this worktree?

```bash
giantmem artifact list -s ready
```

### What .md artifacts did I create this week?

```bash
giantmem artifact list --json \
  | jq -r '.artifacts[]
      | select(.created >= (now - 7*86400 | strftime("%Y-%m-%d")))
      | .id + "\t" + .path'
```

### What's stale across all my projects?

```bash
giantmem artifact stale --all-repos --days 60
```

### Where's that delta-spec I started for auth?

```bash
gma -t delta-spec -d auth                       # interactive
giantmem artifact list --repo all -t delta-spec -d auth   # plain
```

### Across all features in this worktree, only `.md` (skip JSON)

```bash
giantmem artifact list -t proposal,delta-spec,tasks,design,plan,research,review,notes,facts
```

(`domain` is the only JSON type in v1 taxonomy. `pattern` + `source-spec` are markdown but repo-level — drop them with the type filter or `select(.feature)` in jq.)

### Search both metadata AND content together

```bash
# typed query + fulltext within results
giantmem artifact list --repo all -t research --json \
  | jq -r '.artifacts[] | .worktree + "/.giantmem/" + .path' \
  | xargs grep -lE "session.*timeout"
```

Or with MCP:

```
find_artifact(type="research", query="session timeout", repo="all")
```

### Find every Claude session that touched a feature's specs

```bash
giantmem find "openspec-compare" --source session --tool Write,Edit
```

### Find every place I've ever proposed something about JWT

```bash
giantmem artifact list --repo all --include-archived -t proposal --json \
  | jq -r '.artifacts[] | .id + "\t" + (.worktree // "?") + "/.giantmem/" + .path' \
  | xargs -I{} sh -c 'echo "=== {} ==="; grep -li jwt "{}" 2>/dev/null'
```

## 6. When in doubt

| Question | Reach for |
|---|---|
| I know the type, status, or feature | `giantmem artifact list` |
| I just remember a phrase | `giantmem find "..."` |
| I want to click through options | `gma` |
| I'm inside Claude | `find_artifact` MCP |
| Content + frontmatter combined | JSON pipe through jq |
| Recent activity | `--since 7d` on `find`, or jq date filter on `artifact list` |
| Old / forgotten | `giantmem artifact stale` |
| What's missing frontmatter | `giantmem artifact orphans` |
