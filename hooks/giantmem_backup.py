#!/usr/bin/env python3
"""SessionEnd hook: back up durable memory SOURCES into the giantmem backup repo.

Sources are truth; sqlite is a derived index (rebuildable). The one source not
backed up anywhere is the harness memory md files. This mirrors them into the
giantmem backup repo and commits (local). If a git remote is configured, pushes.

Deliberately does NOT snapshot archives.db here -- it's 80MB and committing it
every session bloats the git history. Use `giantmem backup push` on a schedule
for that. Add a remote to ~/giantmem_archive_backup for off-machine durability:
    git -C ~/giantmem_archive_backup remote add origin <private-repo-url>
"""

import glob
import os
import shutil
import subprocess

BACKUP_DIR = os.path.expanduser(
    os.getenv("GIANTMEM_BACKUP_DIR", "~/giantmem_archive_backup")
)
MEM_GLOB = os.path.expanduser("~/.claude/projects/*/memory/*.md")
MIRROR_SUBDIR = "claude-memory"


def run(args):
    return subprocess.run(args, capture_output=True, text=True, timeout=60, check=False)


def main():
    if not os.path.isdir(os.path.join(BACKUP_DIR, ".git")):
        return  # not initialized; run `giantmem backup init` first

    dest_root = os.path.join(BACKUP_DIR, MIRROR_SUBDIR)
    for src in glob.glob(MEM_GLOB):
        rel = src.split("/.claude/projects/", 1)[-1]
        dest = os.path.join(dest_root, rel)
        os.makedirs(os.path.dirname(dest), exist_ok=True)
        try:
            shutil.copy2(src, dest)
        except OSError:
            pass

    run(["git", "-C", BACKUP_DIR, "add", MIRROR_SUBDIR])
    status = run(["git", "-C", BACKUP_DIR, "status", "--porcelain", MIRROR_SUBDIR])
    if not status.stdout.strip():
        return

    run(["git", "-C", BACKUP_DIR, "commit", "-m", "claude memory snapshot"])
    if run(["git", "-C", BACKUP_DIR, "remote"]).stdout.strip():
        run(["git", "-C", BACKUP_DIR, "push"])


if __name__ == "__main__":
    try:
        main()
    except Exception:  # pylint: disable=broad-exception-caught
        pass
