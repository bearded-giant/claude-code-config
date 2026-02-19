**`/splunk` skill** -- `~/dev/claude-code-config/skills/splunk/`

```
splunk/
  SKILL.md                              # main skill (3 subcommands)
  templates/dashboard_studio.json       # base JSON structure template
  reference/dashboard_studio_schema.md  # Dashboard Studio format reference
  reference/splunk_query_patterns.md    # SPL pattern library
```

**Three subcommands:**

| Command | What it does |
|---|---|
| `/splunk dashboard [feature]` | Auto-detects metrics from feature context, confirms with user, generates full Dashboard Studio JSON |
| `/splunk queries [feature]` | Same detection flow, outputs named SPL queries with descriptions to a markdown checklist |
| `/splunk query "description"` | Quick-fire single query from plain English, no feature detection |

**The workflow** (for `dashboard` and `queries`):
1. Reads feature's spec, facts, plan, research docs
2. Extracts log events, structured fields, lifecycle phases, key dimensions
3. Presents proposed panels/queries in a table for confirmation
4. Surfaces efficacy guidance inline (span selection, dc() for user counts, rex vs direct match, etc.)
5. Generates output to `.giantmem/filebox/` (dashboard JSON) or `.giantmem/research/` (query checklist)

Flags: `--docs=` for extra context files, `--manual` to skip auto-detection, `--index=` to set the index pattern.
