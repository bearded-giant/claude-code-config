---
allowed-tools:
  - Read
  - Write
  - Task
  - Glob
  - Grep
  - Bash
description: "Categorize gl search code results via regex + LLM workers"
argument-hint: "[csv-path] (default: ~/.cache/gitlab-cli/last_search.csv)"
model: opus
---

# Categorize Search Results (Two-Phase)

You are the **Opus Orchestrator** for search result categorization. Phase 1 uses a Python regex categorizer for deterministic rows. Phase 2 dispatches haiku workers only for ambiguous rows.

**Pattern**: regex pass -> file-based LLM workers -> Python merge -> summary.

**Context budget**: You never see raw CSV data. Scripts and workers handle data. You only see summary stats.

## Type Taxonomy (shared by regex + LLM)

| Type | When to use |
|------|-------------|
| IMPORT | import/from statements bringing in a module, function, or class |
| DEFINITION | def, class, or variable assignment that defines/creates the searched item |
| USAGE | runtime call, instantiation, or method invocation of the searched item |
| CONFIG | configuration files, settings, env vars, connection strings |
| LOG | logging/print statements that reference the search term |
| TEST | file path contains test, fixture, conftest, or spec |
| COMMENT | comment lines (starting with #, //, /*, etc.) |
| SIMPLE_KEY | cache/redis key construction patterns (f-strings, format strings building key names) |

## Phase 0: Setup

Input path: $ARGUMENTS

If no path provided, default to `~/.cache/gitlab-cli/last_search.csv`.
If that doesn't exist, check for `~/.cache/gitlab-cli/last_search.txt` and inform user they need `--format csv`.

Count rows (do NOT read the CSV into context):
```bash
wc -l INPUT_PATH
```

Report:
```
Input: [path] ([N] rows)
```

Create swarm output directory:
1. If project has `.giantmem/features/search-result-processing/`: use `.giantmem/features/search-result-processing/swarm-categorize-{timestamp}/`
2. Otherwise: same directory as input file, `swarm-categorize-{timestamp}/`

Create subdirectories:
```
swarm-categorize-{timestamp}/
  workers/          # LLM worker JSON outputs
  batches/          # batch CSV files for workers to read
  merged/           # final merged CSV
```

Store this path as `SWARM_DIR`.

## Phase 1: Copy Scripts to Swarm Dir

Scripts live in `~/dev/claude-code-config/scripts/categorize-search/`. Copy them to `SWARM_DIR` so artifacts are self-contained:

```bash
cp ~/dev/claude-code-config/scripts/categorize-search/{categorize.py,split_batches.py,merge.py} SWARM_DIR/
```

Scripts:
- `categorize.py` - regex-based categorizer, outputs classified CSV + ambiguous CSV for rows below threshold
- `split_batches.py` - splits ambiguous CSV into batch CSV files for LLM workers
- `merge.py` - overlays LLM worker results onto regex output, prints JSON summary

## Phase 2: Run Regex Categorizer

Execute the regex pass. Do NOT read any CSV data into context.

```bash
python3 SWARM_DIR/categorize.py \
  --input-csv INPUT_PATH \
  --output-csv SWARM_DIR/merged/regex-pass.csv \
  --ambiguous-csv SWARM_DIR/ambiguous.csv \
  --threshold 0.9 \
  --summary
```

Parse the JSON summary from stdout. Report:

```
## Regex Pass

Classified: [N] rows at >= 0.9 confidence
Ambiguous: [N] rows ([pct]%) need LLM review

Type distribution (regex):
  TEST: [N], IMPORT: [N], DEFINITION: [N], ...
```

If ambiguous count is 0, skip Phase 3 and go directly to Phase 4 (just copy regex output as final).

## Phase 3: LLM Workers for Ambiguous Rows

### 3a: Split Batches

```bash
python3 SWARM_DIR/split_batches.py \
  --input-csv SWARM_DIR/ambiguous.csv \
  --output-dir SWARM_DIR/batches \
  --max-workers 10
```

Parse JSON output for batch count and sizes. Report:

```
Batches: [N] ([batch_size] rows each, last batch: [M] rows)
Dispatching [N] haiku workers...
```

### 3b: Dispatch Workers

**CRITICAL**: Spawn ALL workers in ONE message using parallel Task calls.

Workers read their batch file from disk. The prompt is tiny (no inline data).

For each batch file, spawn:

```
Task tool:
  subagent_type: "general-purpose"
  model: "haiku"
  prompt: [worker prompt with BATCH_FILE_PATH and OUTPUT_PATH]
```

### Worker Prompt Template

````
You are a code search result categorizer. Read the batch CSV file and classify each row.

## Type Taxonomy

| Type | When to use |
|------|-------------|
| IMPORT | import/from statements bringing in a module, function, or class |
| DEFINITION | def, class, or variable assignment that defines/creates the searched item |
| USAGE | runtime call, instantiation, or method invocation of the searched item |
| CONFIG | configuration files, settings, env vars, connection strings |
| LOG | logging/print statements that reference the search term |
| TEST | file path contains test, fixture, conftest, or spec |
| COMMENT | comment lines (starting with #, //, /*, etc.) |
| SIMPLE_KEY | cache/redis key construction patterns (f-strings, format strings building key names) |

## Method Extraction

Extract the specific function, class, or method name being referenced. Examples:
- `from redis_cache_client import get_memorystore_client` -> method: `get_memorystore_client`
- `cache = ConsistentCacheService()` -> method: `ConsistentCacheService`
- `cache.get(key)` -> method: `cache.get`
- `def cache_get_or_create(` -> method: `cache_get_or_create`

## Rules

- Check the file path first: if it contains test/fixture/conftest/spec -> TEST regardless of snippet
- For IMPORT: look for `import`, `from X import Y`
- For DEFINITION: look for `def `, `class `, top-level assignment
- For SIMPLE_KEY: look for f-string or format string building a cache/redis key
- If ambiguous between USAGE and CONFIG, prefer USAGE
- confidence: 0.9+ for obvious cases, 0.7-0.9 for clear but contextual, 0.5-0.7 for ambiguous

## Instructions

1. Read the CSV file at: BATCH_FILE_PATH
   Columns: global_row, project, file, line, ref, snippet

2. Classify each row

3. Write results as JSON array to: OUTPUT_PATH

Format:
```json
[
  {
    "global_row": 42,
    "type": "USAGE",
    "method": "redis_client.get",
    "confidence": 0.85,
    "note": ""
  }
]
```

global_row comes from the CSV (preserves original row number). Keep notes brief (empty string if nothing notable).

After writing, confirm: "Wrote [N] results to OUTPUT_PATH"
````

### 3c: Verify Workers

After all workers complete:

```bash
ls SWARM_DIR/workers/
```

Report:
```
Worker files: [N]/[total] present
Missing: [list if any]
```

Do NOT read worker JSON files.

## Phase 4: Merge and Finalize

If there were ambiguous rows (Phase 3 ran):

```bash
python3 SWARM_DIR/merge.py \
  --regex-csv SWARM_DIR/merged/regex-pass.csv \
  --workers-dir SWARM_DIR/workers \
  --output-csv SWARM_DIR/merged/categorized-ORIGINAL_FILENAME.csv
```

If no ambiguous rows (Phase 3 skipped):

```bash
cp SWARM_DIR/merged/regex-pass.csv SWARM_DIR/merged/categorized-ORIGINAL_FILENAME.csv
```

Copy to input directory and create symlink:
```bash
cp SWARM_DIR/merged/categorized-*.csv INPUT_DIR/categorized-ORIGINAL_FILENAME.csv
ln -sf categorized-ORIGINAL_FILENAME.csv INPUT_DIR/last_categorized.csv
```

### Write Manifest

Write `SWARM_DIR/README.md`:
```markdown
# Categorize: {original filename}

Generated: {timestamp}
Input: {path} ({N} rows)
Regex pass: {N} rows at >= 0.9 confidence
LLM workers: {N} (haiku, {batches} batches of ~{size})

## Files
| File | Description |
|------|-------------|
| categorize.py | Regex categorizer (re-runnable) |
| split_batches.py | Batch splitter (re-runnable) |
| merge.py | Merge script (re-runnable) |
| ambiguous.csv | Rows sent to LLM workers |
| batches/batch-*.csv | Input files for workers |
| workers/batch-*.json | LLM worker outputs |
| merged/regex-pass.csv | Regex-only output |
| merged/categorized-*.csv | Final merged output |
```

## Phase 5: Summary

Print final summary from merge script output:

```
## Results

| Type | Count | % |
|------|-------|---|
| ... | ... | ... |

Methods found: [N] unique
Regex classified: [N] rows
LLM classified: [N] rows
Low confidence (< 0.7): [N] rows ([pct]%)

Top methods:
  method_name: [N] hits (breakdown)

Output: [path to merged CSV]
Artifacts: [SWARM_DIR]
Symlink: last_categorized.csv
```

If `low_confidence_pct > 20`:
```
Warning: [pct]% of rows have low confidence (< 0.7)
Consider re-running with more targeted search terms.
```

## Constraints

- Max 10 parallel workers (scale batch size, not worker count)
- Workers READ batch CSV files from disk (no inline data in prompts)
- All CSV/JSON processing happens in Python scripts, NOT in Opus context
- Orchestrator NEVER reads raw CSV data
- Do NOT modify the original input CSV
- Do NOT commit any files

## Error Handling

- CSV not found: report and stop
- Regex script fails: report error and stop
- 0 ambiguous rows: skip LLM phase, use regex output as final
- Worker file missing: merge script keeps regex classification for those rows
- Merge script fails: report error, suggest re-running manually
- Empty CSV: report and stop

Task: $ARGUMENTS
