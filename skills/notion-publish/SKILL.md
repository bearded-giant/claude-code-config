---
name: notion-publish
description: Push .giantmem/ docs (research, context notes, designs, proposals, reviews, feature .md files) into the Notion database `Claude Artifacts` in the personal workspace through the local notion-multi-mcp server (MCP `notion-personal`, account `personal`). Upserts by the `notion:` URL in frontmatter and writes the URL back after publish. Auto-fires when user says "publish to notion", "push to notion", "notion this", "send this to notion", or invokes /notion-publish. Also the follow-through after the user says yes to the end-of-task publish ask raised by hooks/notion_publish_nudge.py. Never publishes without an explicit user yes. Plans, tasks, facts, specs are outside the allowlist (config/notion-publish.yaml) and skip silently.
---

# notion-publish

Model-driven push. Hooks cannot reach Notion; this skill makes the MCP calls. Server: `notion-personal` (wrangler on localhost:8787, kept up by launchd `com.bryan.notion-mcp`). Tools surface as `mcp__notion-personal__notion_*`. Never the hosted `notion` server; that is the Skio workspace.

## Args

```
/notion-publish [path ...] [--feature X] [--dirty] [--dry-run] [--force]
```

| Arg | Means |
|---|---|
| `path ...` | publish these files |
| `--feature X` | every publishable `.md` under `.giantmem/features/X/` |
| `--dirty` | every publishable doc with no `notion:` or edited after `notion_synced` |
| `--dry-run` | print gate decisions, push nothing |
| `--force` | publish a path the gate rejects (explicit user ask beats allowlist) |

No args and no nudge context → run `--scan`, show publishable + dirty rows, AskUserQuestion (multiSelect) which to push.

## Config

`config/notion-publish.yaml`: `account` (server account name, every call), `data_source_id` (parent for every create), `types` (frontmatter or path type that qualifies), `exclude` (regexes on `.giantmem`-relative path). Hook and skill read the same file. Not in `types` = silent skip. Frontmatter `publish: true|false` overrides.

## Procedure

1. Resolve targets.
   - paths given → use as is
   - `--feature X` → `python3 ~/.claude/scripts/md_to_notion.py --scan .giantmem/features/X`, keep `publishable`
   - `--dirty` → `python3 ~/.claude/scripts/md_to_notion.py --scan .giantmem`, keep `publishable && dirty`
2. `--dry-run` → table `source | type | publishable | reason | dirty | notion`. Stop.
3. Per target: `python3 ~/.claude/scripts/md_to_notion.py <path>` → JSON with `publishable`, `reason`, `page_id`, `properties`, `content`. `publishable` false and no `--force` → skip, keep the reason for the report.
4. Push. `content` and `properties` go in verbatim; never hand-edit converter output. Every call carries `account: <cfg.account>`.
   - `page_id` set → `notion_update_page` `command: replace_content`, `new_str: <content>`, then `notion_update_page` `command: update_properties`, `properties: <properties>`.
   - `page_id` empty → `notion_create_pages` with `parent: {"data_source_id": <cfg.data_source_id>}`, `pages: [{"properties": <properties>, "content": <content>}]`. Take `url` from the result.
   - `page_id` set but the update 404s (page lives in another workspace, or was deleted) → treat as empty: create, and step 5 overwrites the stale URL. Say so in the report.
5. `python3 ~/.claude/scripts/md_to_notion.py --mark <url> <path>` writes `notion:` + `notion_synced:` into frontmatter.
6. Report one table: `path | url` for pushed, `path | skipped: reason` for the rest. Nothing else.

## Server down

`mcp__notion-personal__*` tools missing or every call fails to connect → stop and report. Do not fall back to the hosted `notion` server. Recovery, for the user:

```bash
curl -s localhost:8787/health
launchctl kickstart -k gui/$(id -u)/com.bryan.notion-mcp
tail -20 ~/dev/ai/notion-multi-mcp/.wrangler/dev.log
```

Tools missing in a session that started while the server was down → restart the session; Claude Code dials MCP servers once at boot.

## Rules

- Never `notion_move_pages`. Never any parent but the config data source. The database stays in the personal workspace; sharing is per row page, by the user, in Notion.
- Unknown select values (new Repo, Feature) are created on the fly by Notion on create and update. No retry logic needed.
- Converter self-check: `python3 ~/.claude/scripts/md_to_notion.py --selftest`.
- Rendering, verified 2026-09-09 against the local server: pipe tables pass through raw and render as tables; mermaid fences render natively; `> [!NOTE]` → callout; `<details>` → toggle; `\<` `\>` `\[\[` come back as plain characters.
