---
description: "Search across domain JSONs for code patterns, files, functions, or concepts"
argument-hint: "<query> [--load]"
---

Delegates to the domains CLI. Read-only — points you at existing domain JSONs, creates nothing.

```bash
python3 ~/dev/giant-tooling/workspace/scripts/domains.py search "<query>" [--load] --cwd "$(pwd)"
```

Quick-filters the index by description/key_paths, then deep-searches each candidate domain JSON across all fields, grouping matches by domain with the matched json-path + snippet. Top 5 shown.

Show its output. If `--load` was passed, then read the domain JSONs it named into context and give a focused summary of the parts relevant to the query (don't dump whole JSONs).
