---
name: notion-publish
description: Push .giantmem/ docs (research, context notes, designs, proposals, reviews, feature .md files) into the private Notion database `Claude Artifacts` through the Notion MCP. Upserts by the `notion:` URL in frontmatter and writes the URL back after publish. Auto-fires when user says "publish to notion", "push to notion", "notion this", "send this to notion", or invokes /notion-publish. Also the follow-through after the user says yes to the end-of-task publish ask raised by hooks/notion_publish_nudge.py. Never publishes without an explicit user yes. Plans, tasks, facts, specs are outside the allowlist (config/notion-publish.yaml) and skip silently.
---

# notion-publish

Model-driven push. Hooks cannot reach Notion (MCP is OAuth only), so this skill does the calls.

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

`config/notion-publish.yaml`: `data_source_id` (parent for every create), `types` (frontmatter or path type that qualifies), `exclude` (regexes on `.giantmem`-relative path). Hook and skill read the same file. Not in `types` = silent skip. Frontmatter `publish: true|false` overrides.

## Procedure

1. Resolve targets.
   - paths given → use as is
   - `--feature X` → `python3 ~/.claude/scripts/md_to_notion.py --scan .giantmem/features/X`, keep `publishable`
   - `--dirty` → `python3 ~/.claude/scripts/md_to_notion.py --scan .giantmem`, keep `publishable && dirty`
2. `--dry-run` → table `source | type | publishable | reason | dirty | notion`. Stop.
3. Per target: `python3 ~/.claude/scripts/md_to_notion.py <path>` → JSON with `publishable`, `reason`, `page_id`, `properties`, `content`. `publishable` false and no `--force` → skip, keep the reason for the report.
4. Push. `content` and `properties` go in verbatim; never hand-edit converter output.
   - `page_id` set → `notion-update-page` `command: replace_content`, `new_str: <content>`, then `notion-update-page` `command: update_properties`, `properties: <properties>`. `allow_async: false`.
   - `page_id` empty → `notion-create-pages` with `parent: {"type": "data_source_id", "data_source_id": <cfg.data_source_id>}`, `pages: [{"properties": <properties>, "content": <content>}]`, `allow_async: false`. Take `url` from the result.
5. `python3 ~/.claude/scripts/md_to_notion.py --mark <url> <path>` writes `notion:` + `notion_synced:` into frontmatter.
6. Report one table: `path | url` for pushed, `path | skipped: reason` for the rest. Nothing else.

## Rules

- Never `notion-move-pages`. Never `creation_mode: draft`. Never any parent but the config data source. The database stays in the Private section; sharing is per row page, by the user, in Notion.
- Notion rejects an unknown select value (new Repo, Feature, Status) → retry once without that property and say so in the report.
- Converter self-check: `python3 ~/.claude/scripts/md_to_notion.py --selftest`.
- Rendering, verified 2026-09-04: mermaid fences render natively; pipe tables become `<table>` (converter); `\+` `\<` `\>` `\[\[` come back as plain characters. Two cosmetic quirks, unexplained: ` + ` sitting between two inline code spans shows as a bullet glyph in fetch output (escaping does not change it); Notion autolinks the Source property text.
