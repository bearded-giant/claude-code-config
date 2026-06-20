---
description: Quick lookup of feature facts (beta flags, config keys, endpoints, test commands) from .giantmem/features/{name}/facts.md. Auto-fires before answering "what beta flag is X", "how do I test feature Y", "what's the config key for Z", "where's the endpoint for the W feature", "how do I run the tests for X" — match against features.json before guessing.
---

Delegates to the feature CLI (partial name match supported):

```bash
python3 ~/dev/giant-tooling/workspace/scripts/feature.py facts <name> --cwd "$(pwd)"
```

Prints `# feature: {name}  last_session: {date}` then the full facts.md. If the name is ambiguous it prints `{"ambiguous": [...]}` — show those and ask which. Then answer the user's actual question (beta flag / config key / endpoint / test command) from the facts content.
