---
description: Archive the current workspace `.giantmem/` (or `scratch/`) directory to central `~/giantmem_archive`. Auto-fires when user invokes /ws-archive or says "archive this workspace", "back up giantmem", "stash this session".
---

Archive workspace directory to central ~/giantmem_archive location.

## Steps

1. Check if `.giantmem/` exists in current directory (fallback: `scratch/`). If neither, error.

2. Determine project name:
   - If in a worktree under `cc-wt/`, use `cc-wt`
   - If in a worktree under `mas/`, use `mas`
   - Otherwise use current directory basename

3. Determine branch/context name:
   - If git worktree, use branch name
   - Otherwise use directory basename or timestamp

4. Run this command to move and symlink:
```bash
#!/bin/bash
set -e

WORKSPACE_DIR="$PWD/.giantmem"
if [ ! -d "$WORKSPACE_DIR" ]; then
    WORKSPACE_DIR="$PWD/scratch"
fi
if [ ! -d "$WORKSPACE_DIR" ] || [ -L "$WORKSPACE_DIR" ]; then
    echo "No workspace directory to archive (or already symlinked)"
    exit 1
fi

WORKSPACE_NAME=$(basename "$WORKSPACE_DIR")

# Determine project name from path
case "$PWD" in
    */cc-wt/*) PROJECT="cc-wt" ;;
    */mas/*) PROJECT="mas" ;;
    *) PROJECT=$(basename "$PWD") ;;
esac

# Determine branch/context name
if git rev-parse --is-inside-work-tree &>/dev/null; then
    BRANCH=$(git rev-parse --abbrev-ref HEAD 2>/dev/null)
else
    BRANCH=$(basename "$PWD")
fi

ARCHIVE_BASE="$HOME/giantmem_archive/$PROJECT"
ARCHIVE_DIR="$ARCHIVE_BASE/$BRANCH"

# If archive already exists, create timestamped backup
if [ -d "$ARCHIVE_DIR" ]; then
    TIMESTAMP=$(date '+%Y%m%d_%H%M%S')
    BACKUP="$ARCHIVE_DIR.backup_$TIMESTAMP"
    echo "Existing archive found, backing up to: $BACKUP"
    mv "$ARCHIVE_DIR" "$BACKUP"
fi

mkdir -p "$ARCHIVE_BASE"
echo "Moving $WORKSPACE_NAME/ to: $ARCHIVE_DIR"
mv "$WORKSPACE_DIR" "$ARCHIVE_DIR"

echo "Creating symlink: $WORKSPACE_NAME/ -> $ARCHIVE_DIR"
ln -s "$ARCHIVE_DIR" "$WORKSPACE_DIR"

echo "Archive complete. $WORKSPACE_NAME/ now symlinked to archive."
ls -la "$WORKSPACE_DIR"
```

5. Report the archive location and confirm symlink is working.

This ensures:
- Active .giantmem/ continues to work (via symlink)
- All writes go directly to archive
- When worktree is deleted, archive persists
