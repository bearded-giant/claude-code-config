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
SELF = "_repo"
OTHER = "_other"


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


def flat(rel):
    return "-".join(rel.parts)


def project_of(root, ws):
    repo = None
    for a in [ws, *ws.parents]:
        if a == root:
            break
        if (a / ".bare").is_dir():
            return a, a.name.removesuffix("-wt"), True
        if repo is None and (a / ".git").exists():
            repo = a
    return (repo, repo.name, False) if repo else (None, "", False)


def desired_links(root, workspaces):
    projects = {}
    for ws in workspaces:
        proot, name, container = project_of(root, ws)
        if proot is None:
            proot, name = ws, f"{OTHER}/{flat(ws.relative_to(root)) or 'home'}"
        projects.setdefault(proot, [Path(name), container, []])[2].append(ws)
    names = [p[0] for p in projects.values()]
    links = {}
    for proot, (name, container, members) in projects.items():
        if names.count(name) > 1:
            name = Path(f"{name} ({flat(proot.relative_to(root))})")
        if not container and members == [proot]:
            links[name] = proot / ".giantmem"
            continue
        for ws in members:
            links[name / (flat(ws.relative_to(proot)) or SELF)] = ws / ".giantmem"
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
            if p.is_symlink():
                if want.get(p) != os.readlink(p):
                    p.unlink()
            # obsidian creates an empty note when an unresolved link is clicked
            elif n in filenames and p.stat().st_size == 0:
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
