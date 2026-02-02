---
allowed-tools:
  - Read
  - Write
  - Task
  - Glob
  - Grep
  - Bash
description: "Categorize gl search code results via parallel LLM workers"
argument-hint: "[csv-path] (default: ~/.cache/gitlab-cli/last_search.csv)"
model: opus
---

# Categorize Search Results

You are the **Opus Orchestrator** for search result categorization. You dispatch haiku workers that write batch results to files, then a Python script merges everything.

**Pattern**: Follows `/swarm` architecture - workers write files, script merges, orchestrator reads summary.

**Context budget**: Workers and merge script handle data. You only see summary stats.

## Phase 0: Load Input

Input path: $ARGUMENTS

If no path provided, default to `~/.cache/gitlab-cli/last_search.csv`.
If that doesn't exist, check for `~/.cache/gitlab-cli/last_search.txt` and inform user they need `--format csv`.

Read the CSV file. Expected columns: `project,file,line,ref,snippet`

Count total rows (excluding header). Report:
```
Input: [path] ([N] rows)
```

If > 400 rows, warn user about cost and ask to proceed.

## Phase 0.5: Create Output Directory

Create the swarm output directory for worker artifacts:

Location priority:
1. If project has `scratch/features/search-result-processing/`: use `scratch/features/search-result-processing/swarm-categorize-{timestamp}/`
2. Otherwise: same directory as input file, `swarm-categorize-{timestamp}/`

Create subdirectories:
```
swarm-categorize-{timestamp}/
  workers/          # worker JSON outputs
  merged/           # final merged CSV
```

Store this path as `SWARM_DIR`.

## Phase 1: Write Merge Script

Write a Python script to `SWARM_DIR/merge.py` that handles Phase 4 (merge) and Phase 5 (summary) outside of LLM context.

The script should:
1. Accept args: `--input-csv`, `--workers-dir`, `--output-csv`, `--batch-size`
2. Read original CSV
3. Read all `batch-*.json` files from workers dir
4. Map batch-local row numbers to global rows
5. Merge categorization columns into original CSV
6. Write output CSV with columns: `project,file,line,ref,type,method,confidence,snippet`
7. Print JSON summary to stdout (type counts, confidence stats, top methods)
8. Exit 0 on success, 1 on error

```python
#!/usr/bin/env python3
import csv
import json
import os
import sys
import argparse
from collections import Counter, defaultdict
from pathlib import Path


def load_worker_files(workers_dir, batch_size, total_rows):
    categorizations = {}
    failed_batches = []

    for f in sorted(Path(workers_dir).glob("batch-*.json")):
        batch_idx = int(f.stem.split("-")[1])
        try:
            data = json.loads(f.read_text())
            for item in data:
                global_row = (batch_idx - 1) * batch_size + item["row"]
                if global_row <= total_rows:
                    categorizations[global_row] = item
        except (json.JSONDecodeError, KeyError) as e:
            failed_batches.append({"batch": batch_idx, "error": str(e)})

    return categorizations, failed_batches


def merge_csv(input_csv, categorizations, output_csv, total_rows):
    with open(input_csv, "r") as fin, open(output_csv, "w", newline="") as fout:
        reader = csv.DictReader(fin)
        writer = csv.writer(fout)
        writer.writerow(["project", "file", "line", "ref", "type", "method", "confidence", "snippet"])

        for i, row in enumerate(reader, start=1):
            cat = categorizations.get(i, {"type": "UNKNOWN", "method": "", "confidence": 0.0})
            writer.writerow([
                row["project"], row["file"], row["line"], row["ref"],
                cat.get("type", "UNKNOWN"),
                cat.get("method", ""),
                cat.get("confidence", 0.0),
                row["snippet"]
            ])


def build_summary(categorizations, total_rows):
    type_counts = Counter()
    method_type_counts = defaultdict(lambda: Counter())
    confidences = []

    for i in range(1, total_rows + 1):
        cat = categorizations.get(i, {"type": "UNKNOWN", "method": "", "confidence": 0.0})
        t = cat.get("type", "UNKNOWN")
        m = cat.get("method", "")
        c = cat.get("confidence", 0.0)
        type_counts[t] += 1
        if m:
            method_type_counts[m][t] += 1
        confidences.append(c)

    low_conf = sum(1 for c in confidences if c < 0.7)
    unknown = type_counts.get("UNKNOWN", 0)

    top_methods = sorted(method_type_counts.items(), key=lambda x: sum(x[1].values()), reverse=True)[:10]
    top_methods_out = []
    for method, tcounts in top_methods:
        total = sum(tcounts.values())
        breakdown = ", ".join(f"{cnt} {tp}" for tp, cnt in tcounts.most_common())
        top_methods_out.append({"method": method, "total": total, "breakdown": breakdown})

    type_summary = []
    for t, cnt in type_counts.most_common():
        type_summary.append({"type": t, "count": cnt, "pct": round(cnt / total_rows * 100, 1)})

    return {
        "total_rows": total_rows,
        "types": type_summary,
        "unique_methods": len(method_type_counts),
        "low_confidence_count": low_conf,
        "low_confidence_pct": round(low_conf / total_rows * 100, 1) if total_rows else 0,
        "unknown_count": unknown,
        "top_methods": top_methods_out,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input-csv", required=True)
    parser.add_argument("--workers-dir", required=True)
    parser.add_argument("--output-csv", required=True)
    parser.add_argument("--batch-size", type=int, required=True)
    args = parser.parse_args()

    with open(args.input_csv) as f:
        total_rows = sum(1 for _ in f) - 1

    categorizations, failed_batches = load_worker_files(args.workers_dir, args.batch_size, total_rows)
    merge_csv(args.input_csv, categorizations, args.output_csv, total_rows)
    summary = build_summary(categorizations, total_rows)
    summary["failed_batches"] = failed_batches
    summary["output_csv"] = args.output_csv

    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
```

Write this script to `SWARM_DIR/merge.py`.

## Phase 2: Batch and Dispatch Workers

### Batch Sizing

**Max 10 workers.** Scale batch size to fit:

| Rows | Batch Size | Workers |
|------|-----------|---------|
| <= 100 | 25 | 4 |
| 101-400 | 50 | 4-8 |
| 401-800 | 100 | 5-8 |
| 801+ | ceil(rows/10) | 10 |

Report:
```
Batches: [N] ([batch_size] rows each, last batch: [M] rows)
Output: [SWARM_DIR]
Dispatching [N] haiku workers...
```

### Worker Dispatch

**CRITICAL**: Spawn ALL workers in ONE message using parallel Task calls.

For each batch, spawn:

```
Task tool:
  subagent_type: "general-purpose"
  model: "haiku"
  prompt: [worker prompt with BATCH_INDEX, BATCH_DATA, OUTPUT_PATH]
```

### Worker Prompt Template

````
You are a code search result categorizer. Classify each row by usage type and extract the method/function name.

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
- `import redis` -> method: `redis`

If multiple methods appear, pick the most specific one related to the search context.

## Rules

- Check the file path first: if it contains test/fixture/conftest/spec -> TEST regardless of snippet
- For IMPORT: look for `import`, `from X import Y`, `require(`, `include`
- For DEFINITION: look for `def `, `class `, top-level assignment of the searched item
- For SIMPLE_KEY: look for f-string or format string building a cache/redis key
- If ambiguous between USAGE and CONFIG, prefer USAGE
- confidence: 0.9+ for obvious cases (IMPORT, DEFINITION, TEST), 0.7-0.9 for clear but contextual, 0.5-0.7 for ambiguous

## Input

CSV rows (batch BATCH_INDEX):
```
BATCH_DATA
```

## Output

You MUST write your results to the file: OUTPUT_PATH

Use the Write tool to write a valid JSON array to that file. One object per input row, in order:

```json
[
  {
    "row": 1,
    "type": "IMPORT",
    "method": "get_memorystore_client",
    "confidence": 0.95,
    "note": ""
  }
]
```

Row numbers are 1-based within this batch. Keep notes brief (empty string if nothing notable).

After writing the file, confirm: "Wrote [N] results to OUTPUT_PATH"
````

## Phase 3: Collect and Verify

After all workers complete, verify worker files exist:

```bash
ls -la SWARM_DIR/workers/
```

Report:
```
Worker files: [N]/[total] present
Missing: [list if any]
```

Do NOT read the worker files. The merge script handles that.

## Phase 4: Run Merge Script

Execute the merge script via Bash:

```bash
python3 SWARM_DIR/merge.py \
  --input-csv INPUT_PATH \
  --workers-dir SWARM_DIR/workers \
  --output-csv SWARM_DIR/merged/categorized-{original-filename}.csv \
  --batch-size BATCH_SIZE
```

The script prints a JSON summary to stdout. Parse that summary.

Also copy the merged CSV to the input file's directory and create/update symlink:
```bash
cp SWARM_DIR/merged/categorized-*.csv INPUT_DIR/categorized-{original-filename}.csv
ln -sf categorized-{original-filename}.csv INPUT_DIR/last_categorized.csv
```

### Write Manifest

Write `SWARM_DIR/README.md`:
```markdown
# Categorize: {original filename}

Generated: {timestamp}
Input: {path} ({N} rows)
Workers: {N} (haiku, batch size {size})

## Files
| File | Description |
|------|-------------|
| workers/batch-*.json | Worker categorization outputs |
| merged/categorized-*.csv | Final merged CSV |
| merge.py | Merge script (re-runnable) |

## Quality
Low confidence (< 0.7): {N} rows ({pct}%)
Unknown (failed): {N} rows
```

## Phase 5: Summary

Using the JSON summary from the merge script (already in stdout), print:

```
## Results

| Type | Count | % |
|------|-------|---|
| IMPORT | 45 | 32% |
| USAGE | 38 | 27% |
| ... | ... | ... |

Methods found: [N] unique
Low confidence (< 0.7): [N] rows ([pct]%)

Top methods:
  get_memorystore_client: 42 hits (28 IMPORT, 10 USAGE, 4 CONFIG)
  ConsistentCacheService: 35 hits (18 IMPORT, 12 USAGE, 5 DEFINITION)

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
- Workers WRITE their output to files in SWARM_DIR/workers/
- Merge happens in Python script, NOT in Opus context
- Orchestrator only reads the summary JSON from script stdout
- Do NOT read worker JSON files directly (let the script do it)
- Do NOT modify the original CSV
- Do NOT commit any files

## Error Handling

- CSV not found: report and stop
- Worker file missing: script marks those rows UNKNOWN
- Merge script fails: report error, suggest re-running script manually
- Empty CSV: report and stop
- All workers fail: report and stop

Task: $ARGUMENTS
