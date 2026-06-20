---
description: "Start a pending feature: promote to in_progress, expand spec, set as active work"
argument-hint: "[feature-name] [--branch=X] [--base=Y]"
---

Delegates to the feature CLI. Do NOT walk the steps by hand.

```bash
python3 ~/dev/giant-tooling/workspace/scripts/feature.py start [feature] [--branch=X] [--base=Y] --cwd "$(pwd)"
```

If no feature given and multiple `pending` exist → list them (`feature.py migrate` then read `features.json`, or just `list-features`) and ask which. One pending → it's safe to pass it.

The CLI flips status pending→in_progress across proposal.md/facts.md/meta.json/features.json/_index.md, resolves+checks out the branch (defaults to the feature name off the detected base), reindexes, pins topic. Prints JSON.

After it runs: summarize branch+base+checkout from JSON. If the user wants the proposal's working sections expanded (Scope/Key Decisions/Acceptance Criteria/Files) or plans/current.md set as active, do that as a follow-up edit — the CLI leaves prose to you.
