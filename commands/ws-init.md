Bootstrap workspace in current directory.

## Steps

1. Run workspace bootstrap:
```bash
source ~/.claude/lib/workspace/workspace-lib.sh && workspace_bootstrap
```

This will:
- Create .giantmem/ structure if missing
- Migrate loose files IN .giantmem/ to subdirs (context/, plans/, etc.)
- Generate tree.md

2. If CLAUDE.md exists in current directory, read it briefly to get project purpose.

3. Update .giantmem/WORKSPACE.md with:
   - Project name (from directory)
   - Branch name (if git)
   - Brief purpose (1-2 lines from CLAUDE.md if present)

4. Show the workspace status.

Keep it minimal - just bootstrap structure and add basic context. Do NOT analyze the entire repo or process files outside .giantmem/.
