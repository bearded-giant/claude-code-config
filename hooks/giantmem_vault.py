#!/usr/bin/env python3
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path.home()
VAULT = Path.home() / "giantmem-vault"
PRUNE = {
    "Library",
    "cache",
    "giantmem-vault",
    "giantmem_archive",
    "node_modules",
    "target",
    "vendor",
    "venv",
}
MAX_DEPTH = 7
SELF = "_giantmem"


def find_workspaces(root, max_depth=MAX_DEPTH):
    found = []
    for dirpath, dirnames, _ in os.walk(root):
        if ".giantmem" in dirnames:
            found.append(Path(dirpath))
        depth = len(Path(dirpath).relative_to(root).parts)
        dirnames[:] = (
            []
            if depth >= max_depth
            else [d for d in dirnames if d not in PRUNE and not d.startswith(".")]
        )
    return found


def desired_links(root, repos):
    rels = {r.relative_to(root) for r in repos}
    ancestors = {p for r in rels for p in r.parents}
    # a workspace with workspaces below it stays a real dir, or their links would land inside its .giantmem
    links = {}
    for rel in rels:
        name = rel / SELF if rel in ancestors or not rel.parts else rel
        links[name] = root / rel / ".giantmem"
    return links


def sync(root=ROOT, vault=VAULT):
    want = {
        vault / k: str(v) for k, v in desired_links(root, find_workspaces(root)).items()
    }
    vault.mkdir(exist_ok=True)
    for dirpath, dirnames, filenames in os.walk(vault):
        dirnames[:] = [d for d in dirnames if d != ".obsidian"]
        for n in dirnames + filenames:
            p = Path(dirpath) / n
            if p.is_symlink() and want.get(p) != os.readlink(p):
                p.unlink()
    for dirpath, _, _ in os.walk(vault, topdown=False):
        p = Path(dirpath)
        if p != vault and ".obsidian" not in p.parts and not any(p.iterdir()):
            p.rmdir()
    for link, target in want.items():
        if os.path.lexists(link):
            continue
        link.parent.mkdir(parents=True, exist_ok=True)
        link.symlink_to(target)
    return want


def main():
    # the ~/dev walk takes over a second; detach so SessionStart does not wait on it
    try:
        subprocess.Popen(
            [sys.executable, __file__, "--sync"],
            start_new_session=True,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    except Exception:  # pylint: disable=broad-exception-caught
        pass


if __name__ == "__main__":
    if sys.argv[1:] == ["--sync"]:
        if ROOT.is_dir():
            sync()
    else:
        main()
