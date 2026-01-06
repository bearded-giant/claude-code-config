Archive scratch directory to central ~/scratch_archive location.

## Steps

1. Check if `scratch/` exists in current directory. If not, error.

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

SCRATCH_DIR="$PWD/scratch"
if [ ! -d "$SCRATCH_DIR" ] || [ -L "$SCRATCH_DIR" ]; then
    echo "No scratch directory to archive (or already symlinked)"
    exit 1
fi

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

ARCHIVE_BASE="$HOME/scratch_archive/$PROJECT"
ARCHIVE_DIR="$ARCHIVE_BASE/$BRANCH"

# If archive already exists, create timestamped backup
if [ -d "$ARCHIVE_DIR" ]; then
    TIMESTAMP=$(date '+%Y%m%d_%H%M%S')
    BACKUP="$ARCHIVE_DIR.backup_$TIMESTAMP"
    echo "Existing archive found, backing up to: $BACKUP"
    mv "$ARCHIVE_DIR" "$BACKUP"
fi

mkdir -p "$ARCHIVE_BASE"
echo "Moving scratch/ to: $ARCHIVE_DIR"
mv "$SCRATCH_DIR" "$ARCHIVE_DIR"

echo "Creating symlink: scratch/ -> $ARCHIVE_DIR"
ln -s "$ARCHIVE_DIR" "$SCRATCH_DIR"

echo "Archive complete. scratch/ now symlinked to archive."
ls -la "$SCRATCH_DIR"
```

5. Report the archive location and confirm symlink is working.

This ensures:
- Active scratch/ continues to work (via symlink)
- All writes go directly to archive
- When worktree is deleted, archive persists
