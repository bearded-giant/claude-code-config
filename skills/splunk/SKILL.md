---
name: splunk
description: >-
  Generate Splunk Dashboard Studio JSON or individual SPL queries for a feature.
  Auto-detects metrics from feature context (specs, facts, research, logs) and
  confirms with the user before generating. Use when building observability for
  a feature or investigating production behavior.
argument-hint: "dashboard|queries|query [feature_name] [--docs=path1,path2] [--manual]"
---

# Splunk: Dashboard & Query Generator

Generate Splunk Dashboard Studio JSON dashboards or individual SPL queries grounded in feature context from the workspace.

## Subcommands

Parse the first positional arg from `$ARGUMENTS`:

| Subcommand | What it does |
|---|---|
| `dashboard` | Full Dashboard Studio JSON with tabs, panels, data sources, and a global time picker |
| `queries` | Set of named SPL queries with descriptions, written to a markdown checklist |
| `query` | Single SPL query from a plain-English description (no feature detection, just generate) |

If no subcommand is provided, ask the user which they want.

## Arguments

After the subcommand, parse remaining `$ARGUMENTS`:

- `feature_name` -- name of a feature in `.giantmem/features/`. Optional. If omitted and `.giantmem/features/` exists, list features and ask.
- `--docs=path1,path2` -- additional files to read for context (research docs, log maps, CSV data, etc.)
- `--manual` -- skip auto-detection, use guided questionnaire instead
- `--index=<index_pattern>` -- override the default Splunk index. If not provided, ask the user for their index pattern.

## Workflow: `dashboard` and `queries`

### Phase 1: Gather context

**Auto-detect mode (default):**

Read feature context in this order. Stop when you have enough to identify metrics.

1. `.giantmem/features/{feature}/facts.md` -- beta flags, config keys, log events
2. `.giantmem/features/{feature}/spec.md` -- what the feature does, acceptance criteria
3. `.giantmem/features/{feature}/plan.md` -- implementation plan, file paths
4. Any files passed via `--docs`
5. If still thin, search `.giantmem/research/` for files referencing the feature name
6. If the feature has log events, search the codebase for the log message strings to find extra fields (the structured logging extras that become top-level Splunk fields)

From these sources, extract:
- **Log event names** -- the message strings emitted by the feature (e.g., `redis_session_manager session_created`)
- **Structured fields** -- extras logged alongside each event (e.g., store_id, user_id, auth_method, location)
- **Rex pattern** -- how to extract the event name from the message text if events share a common prefix
- **Lifecycle phases** -- group events by phase (creation, validation, error, cleanup, etc.)
- **Key dimensions** -- fields worth splitting/grouping by (auth_method, location, store_id, etc.)
- **Success vs failure events** -- which events represent healthy behavior vs problems

**Manual mode (`--manual`):**

Skip auto-detection. Ask the user directly:
1. What log events does this feature emit? (event names and log message patterns)
2. What structured fields are available as Splunk extras?
3. What dimensions should panels group by?
4. What time granularity? (5m, 15m, 1h)
5. What's the Splunk index pattern?

### Phase 2: Confirm metrics

Present the auto-detected (or manually gathered) metrics to the user in a table:

```
Detected metrics for [feature_name]:

| Event | Phase | Suggested Panel Type | Group By |
|---|---|---|---|
| session_created | creation | timechart (line) | auth_method |
| session_miss | validation | timechart (line) | location, auth_method |
| ... | ... | ... | ... |

Fields available: store_id, user_id, session_id, auth_method, location, source

Proposed tabs: [list of logical groupings]
```

Ask the user to confirm, adjust, or add. Use AskUserQuestion for structured choices when appropriate (e.g., "Which fields should be primary grouping dimensions?").

### Phase 3: Guide the user

Before generating, surface recommendations for maximum query efficacy:

1. **Index specificity** -- narrow the index pattern as much as possible. Broader = slower.
2. **Time span selection** -- recommend span values based on expected event volume:
   - High volume (>1000/hr): `span=5m` or `span=15m`
   - Medium volume (100-1000/hr): `span=15m` or `span=1h`
   - Low volume (<100/hr): `span=1h` or `span=4h`
3. **Rex vs field search** -- if events share a prefix, one rex extraction is cheaper than N separate searches. But for single-event panels, direct string match in the search is faster.
4. **dc() for unique counts** -- always include `dc(user_id)` alongside raw counts for user-facing metrics. Raw counts inflate due to concurrent requests; unique users is the real impact number.
5. **stats vs timechart** -- use timechart for trend panels, stats for summary/table panels. Don't timechart low-volume events (noisy).
6. **Top-N with head** -- for "top stores" or "top users" panels, always add `| head 20` to avoid overwhelming tables.
7. **Single value panels** -- use for key health indicators (total events, error count, success rate). Keep to 4-6 per dashboard max.

Present these as contextual notes alongside the proposed panels, not as a separate lecture. Weave them into the confirmation step.

### Phase 4: Generate

**For `dashboard`:**

Generate a complete Dashboard Studio JSON file following the schema in @reference/dashboard_studio_schema.md and using @templates/dashboard_studio.json as the base structure.

Requirements:
- Global time picker input wired to all data sources via tokens
- Tabs for each logical grouping of panels
- Appropriate visualization types per panel (see reference)
- Panel titles that describe what the panel shows
- Data source names that match the panel purpose

Write to: `.giantmem/filebox/splunk_{feature_slug}_dashboard.json`

**For `queries`:**

Generate a markdown file with each query as a named, described block:

```markdown
# Splunk Queries: [Feature Name]

## [Tab/Section Name]

### [Query Name]
[1-2 sentence description of what it shows and why it matters]
\`\`\`
[SPL query]
\`\`\`
```

Write to: `.giantmem/research/splunk_{feature_slug}_queries.md`

### Phase 5: Present

After writing:
- Show the output file path
- Summarize: N tabs, N panels (for dashboard) or N queries (for queries)
- For dashboards: remind the user how to import (Splunk > Dashboards > Create New Dashboard > Source JSON)
- Ask if adjustments are needed

## Workflow: `query`

The `query` subcommand is a quick-fire mode. No feature detection.

1. Read the description from `$ARGUMENTS` (everything after `query`)
2. Ask for the index pattern if not provided via `--index`
3. Ask what fields are available (or infer from description)
4. Generate the SPL query
5. Output directly in chat (no file write unless the user asks)

Example: `/splunk query "count of session_miss events by auth_method over time, 15m buckets"`

## Rules

- All queries must use parameterized time: `$global_time.earliest$` / `$global_time.latest$` for dashboards, explicit `earliest=` / `latest=` for standalone queries
- Never hardcode time ranges in dashboard queries
- Use `dc()` (distinct count) for user-impact metrics, `count` for volume metrics
- Prefer `splunk.line` for timecharts, `splunk.table` for stats/breakdowns, `splunk.column` for comparisons
- Panel titles should be short, non-alarming, and describe what the panel shows in business terms (not SPL commands or internal jargon)
- Every visualization MUST include a `description` field. The description provides context for the reader: what the panel measures, why it matters, and how to interpret the data. Descriptions are the most critical part of a dashboard -- they prevent misinterpretation of raw numbers. Write them for the least-technical person who will view the dashboard.
- **Chart descriptions must be very short** (1 short sentence, ~15 words max). Splunk truncates long descriptions on chart panels (line, area, column, bar, pie, singlevalue). Keep them tight: "Shows X per hour by Y." No jargon, no filler.
- **Table descriptions can be longer** (2-3 sentences). Splunk renders table descriptions with more space. Use this for context like column explanations and interpretation guidance.
- When a panel shows request/event counts, the description must clarify that these are requests, not users. If the dashboard also has user-level panels, cross-reference them (e.g., "Use the Impact tab for merchant-level counts")
- When a panel shows `dc(user_id)` or similar unique counts, the description should say "unique [users/merchants/etc.]" explicitly
- For rex extractions, always use a named capture group
- Quote all field values in `eval(if(...))` expressions
- Do not add comments to SPL queries -- they don't support inline comments
- Dashboard JSON must be valid JSON (no trailing commas, proper escaping of backslashes in rex patterns)
- Follow workspace output rules for file placement

$ARGUMENTS
