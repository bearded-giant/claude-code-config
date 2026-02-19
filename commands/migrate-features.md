---
description: "Build features.json cache from existing feature directories"
argument-hint: ""
---

Scan `.giantmem/features/` and build `features.json` from existing `meta.json` and `spec.md` files.

## Steps

1. Validate `.giantmem/features/` exists. If not, inform user to run `/ws-init`.

2. Scan for feature directories (any subdirectory of `.giantmem/features/` that isn't `_index.md`).

3. For each feature directory, read `meta.json` if it exists. If not, fall back to `spec.md` and `facts.md` to extract:
   - `name`: directory name
   - `status`: from `status:` line in spec.md
   - `branch`: from meta.json or `branch:` line in facts.md
   - `base_branch`: from meta.json or `base:` line in facts.md
   - `builds_on`: from meta.json or `builds_on:` line in spec.md
   - `beta_flag`: from meta.json or `beta_flag:` line in facts.md
   - `created`: from meta.json or `created:` line in spec.md
   - `last_session`: from meta.json, or use file modification date of spec.md

4. Build the JSON object keyed by feature name:

```json
{
  "feature-name": {
    "name": "feature-name",
    "status": "complete",
    "branch": "some-branch",
    "base_branch": "main",
    "builds_on": "none",
    "beta_flag": "",
    "created": "2026-02-04",
    "last_session": "2026-02-05"
  }
}
```

5. Write to `.giantmem/features/features.json`.

6. Report how many features were indexed and list them with status.
