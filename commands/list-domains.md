---
description: "List all indexed code domains from the knowledge base"
argument-hint: "[--verbose]"
---

Delegates to the domains CLI. Read-only.

```bash
python3 ~/dev/giant-tooling/workspace/scripts/domains.py list [--verbose] --cwd "$(pwd)"
```

Reads `.giantmem/domains/_index.json`, prints a compact table (domain, description, explored, features). `--verbose` adds paths, coverage counts (key files / entry points), and a `[STALE - N days]` marker when last_explored > 7 days. Handles "no domains indexed" itself. Show its output.
