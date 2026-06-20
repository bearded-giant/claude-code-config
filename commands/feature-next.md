---
description: "Show the next ready artifact for a feature (informational, derived from artifacts.json + artifact_dag.yaml)."
argument-hint: "[feature-name]"
---

Delegates to the feature CLI. Read-only, informational — never enforces.

```bash
python3 ~/dev/giant-tooling/workspace/scripts/feature.py next [feature] --cwd "$(pwd)"
```

Feature inferred from the single in_progress one if omitted. The CLI loads the artifact DAG (`~/.claude/config/artifact_dag.yaml`, or a built-in proposal→tasks→review default when absent), reads `.giantmem/artifacts.json` for the feature's present artifact types + statuses, and prints next-ready / also-ready / blocked / done. Show its output verbatim. The user can skip any artifact — never push back.
