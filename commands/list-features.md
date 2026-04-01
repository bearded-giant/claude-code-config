List all features in the current workspace from the features cache.

## Steps

1. Check if `.giantmem/features/features.json` exists.
   - If not, check if `.giantmem/features/` exists. If the directory has feature subdirectories but no `features.json`, build the cache by scanning feature directories (read each `meta.json` or `spec.md` for status, branch, dates) and write `features.json`. Then proceed.
   - If `.giantmem/features/` doesn't exist, inform user to run `/ws-init` first.

2. Read `.giantmem/features/features.json` and parse it.

3. Display a table with these columns, sorted by last_session descending (most recent first):

```
| Feature | Status | Branch | FE | Last Modified |
```

The `FE` column shows:
- The frontend branch name if `frontend.enabled` is `true`
- `-` if frontend is `null` or `frontend.enabled` is `false`

4. If the cache is empty, display "no features found".

5. If user asks about a specific feature, read its `spec.md` and `facts.md` from `.giantmem/features/{name}/`. When the feature has frontend enabled, also show the frontend worktree path.
