---
name: notion-publish
description: Push .giantmem/ docs into the personal Notion page tree under `Claude Artifacts` (repo > worktree > feature > doc) through the local notion-multi-mcp server (MCP `notion-personal`, account `personal`). Policy in config/notion-publish.yaml decides what publishes, never a question. Class `auto` docs (frontmatter `publish: true`, or `kind:`/`type:` in the `auto` list) publish on write when the PostToolUse hook says `publish now`. Class `on_request` docs (research, pattern, notes, design, proposal, review, grill-run, grill-final, file) publish when the user says "publish to notion", "push to notion", "notion this", "send this to notion", or invokes /notion-publish. Upserts by the `notion:` URL in frontmatter and writes the URL back. Plans, tasks, facts, specs are outside both lists and skip silently.
---

# notion-publish

Model-driven push. Hooks cannot reach Notion; this skill makes the MCP calls. Server: `notion-personal` (wrangler on localhost:8787, kept up by launchd `com.bryan.notion-mcp`). Tools surface as `mcp__notion-personal__notion_*`. Never the hosted `notion` server; that is the Skio workspace.

## Triggers

| Trigger | Targets |
|---|---|
| hook context `publish now: <rel>` | that path, same turn |
| user says publish / `/notion-publish` | args below |

No AskUserQuestion anywhere in this skill. `config/notion-publish.yaml` already decided.

## Args

```
/notion-publish [path ...] [--feature X] [--dirty] [--dry-run] [--force]
```

| Arg | Means |
|---|---|
| `path ...` | publish these files |
| `--feature X` | every publishable `.md` under `.giantmem/features/X/` |
| `--dirty` | every publishable doc with no `notion:` or edited after `notion_synced` |
| `--dry-run` | print gate decisions + `parent_path`, push nothing |
| `--force` | publish a path the gate rejects (explicit user ask beats policy) |

No args and no hook context → `--dirty`.

## Config

`config/notion-publish.yaml`: `account` (server account name, every call), `root_page_id` (tree root `Claude Artifacts`), `auto` (kinds that publish on write), `on_request` (types that publish on user ask), `exclude` (regexes on `.giantmem`-relative path). Frontmatter `publish: true|false` overrides both lists. Hook and skill read the same file.

`config/notion-publish-tree.json`: `parent_path` prefix → page id. Written by this skill. Delete an entry to force re-resolution.

## Procedure

1. Resolve targets.
   - paths given → use as is
   - `--feature X` → `python3 ~/.claude/scripts/md_to_notion.py --scan .giantmem/features/X`, keep `publishable`
   - `--dirty` → `python3 ~/.claude/scripts/md_to_notion.py --scan .giantmem`, keep `publishable && dirty`
2. `--dry-run` → table `source | class | publishable | reason | dirty | parent_path | notion`. Stop.
3. Per target: `python3 ~/.claude/scripts/md_to_notion.py <path>` → JSON with `publishable`, `reason`, `class`, `page_id`, `parent_path`, `title`, `content`. `publishable` false and no `--force` → skip, keep the reason for the report.
4. Resolve parent. Split `parent_path` on `/`, walk prefixes from the root (`root_page_id` is the parent of the first segment).
   - cache hit → page id
   - miss → `notion_fetch` the parent page; a child page titled exactly the segment → its id. None → `notion_create_pages` `parent: {"page_id": <parent id>}`, `pages: [{"properties": {"title": "<segment>"}}]`, no content. Write the id to the cache.
5. Push. `content` goes in verbatim; never hand-edit converter output. Every call carries `account: <cfg.account>`.
   - `page_id` set → `notion_update_page` `command: replace_content`, `new_str: <content>`.
   - `page_id` empty → `notion_create_pages` `parent: {"page_id": <resolved parent>}`, `pages: [{"properties": {"title": "<title>"}, "content": <content>}]`. Take `url` from the result.
   - 404 on `page_id` → treat as empty: create under the resolved parent; step 6 overwrites the stale URL. Say so in the report.
   - 404 on a cached container id → delete that cache entry, redo step 4 for that prefix once, retry.
6. `python3 ~/.claude/scripts/md_to_notion.py --mark <url> <path>` writes `notion:` + `notion_synced:` into frontmatter.
7. Report. User-triggered: one table `path | url` pushed, `path | skipped: reason` rest. Hook-triggered: one line `published <rel> → <url>`. Nothing else.

## Server down

`mcp__notion-personal__*` tools missing or every call fails to connect → stop and report. Do not fall back to the hosted `notion` server. Auto-class docs stay local and dirty; `--dirty` catches them next time. Recovery, for the user:

```bash
curl -s localhost:8787/health
launchctl kickstart -k gui/$(id -u)/com.bryan.notion-mcp
tail -20 ~/dev/ai/notion-multi-mcp/.wrangler/dev.log
```

Tools missing in a session that started while the server was down → restart the session; Claude Code dials MCP servers once at boot.

## Rules

- Parent is always the resolved tree page. Never a database.
- Local file is canonical. Republish overwrites the Notion body. Notion-side edits are the user's to backport by hand.
- Every page ends with the converter's footer callout `giantmem: repo[@worktree]/path · synced · sha`. That is the reverse link. Do not strip it.
- Steady state never moves pages. Migration one-offs use `notion_move_pages` with `new_parent: {type: "page_id", page_id}`.
- Converter self-check: `python3 ~/.claude/scripts/md_to_notion.py --selftest`.
- Rendering, verified 2026-09-09 against the local server: pipe tables pass through raw and render as tables; mermaid fences render natively; `> [!NOTE]` → callout; `<details>` → toggle; `\<` `\>` `\[\[` come back as plain characters.
