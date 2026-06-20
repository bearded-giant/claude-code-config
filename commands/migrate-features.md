---
description: "Build features.json cache from existing feature directories"
argument-hint: ""
---

Delegates to the feature CLI. Run it, show output:

```bash
python3 ~/dev/giant-tooling/workspace/scripts/feature.py migrate --cwd "$(pwd)"
```

Scans `.giantmem/features/`, reads each `meta.json` (falling back to proposal.md/facts.md frontmatter, then file mtime for `last_session`), rebuilds `features.json`. Prints JSON: `indexed` count + per-feature status. Nothing else to do.
