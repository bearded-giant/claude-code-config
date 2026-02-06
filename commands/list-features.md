List all features in the current workspace with last modified dates.

## Steps

1. Check if scratch/features/_index.md exists. If not, inform user to run /ws-init first.
2. Read scratch/features/_index.md to get feature names and statuses.
3. For each feature directory in scratch/features/ (excluding _index.md), run `stat -f '%Sm' -t '%Y-%m-%d' scratch/features/{name}/spec.md` (macOS) to get last modified date. Use the most recently modified file in the feature folder as the date.
4. Display a table with these columns:

```
| Feature | Status | Last Modified |
```

5. Sort by last modified descending (most recent first).
6. If user asks about a specific feature, read its spec.md and facts.md from scratch/features/{name}/
