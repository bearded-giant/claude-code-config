import os
from pathlib import Path

import giantmem_vault as gv


def mk(root, *rels):
    for rel in rels:
        (root / rel / ".giantmem").mkdir(parents=True)
        (root / rel / ".giantmem" / "WORKSPACE.md").write_text("# ws\n")


def repo(root, *rels):
    for rel in rels:
        (root / rel / ".git").mkdir(parents=True)


def container(root, rel, *worktrees):
    (root / rel / ".bare").mkdir(parents=True)
    for wt in worktrees:
        (root / rel / wt).mkdir(parents=True, exist_ok=True)
        (root / rel / wt / ".git").write_text(f"gitdir: {root / rel}/.bare\n")


def links(vault):
    out = {}
    for dirpath, dirnames, filenames in os.walk(vault):
        for n in dirnames + filenames:
            p = Path(dirpath) / n
            if p.is_symlink():
                out[str(p.relative_to(vault))] = os.readlink(p)
    return out


def test_project_first_layout_and_prune(tmp_path):
    root, vault = tmp_path / "home", tmp_path / "vault"
    repo(root, "dev/ai/kai", "old/kai", "dev/ai/cerebro", "dev/ai/remi")
    container(root, "dev/ai/inv-wt", "main", "feat/x")
    container(root, "dev/ai/remi-wt", "main")
    mk(
        root,
        ".",
        "Desktop/notes",
        "dev/ai/kai",
        "old/kai",
        "dev/ai/cerebro",
        "dev/ai/cerebro/projects",
        "dev/ai/inv-wt",
        "dev/ai/inv-wt/main",
        "dev/ai/inv-wt/feat/x",
        "dev/ai/remi",
        "dev/ai/remi-wt/main",
        "x/node_modules/pkg",
        "cfg/.mdlive/history",
        "Library/app",
        "giantmem_archive/old",
    )
    (root / "deep/a/b/c/d/e/f").mkdir(parents=True)
    mk(root, "deep/a/b/c/d/e/f/g")

    gv.sync(root, vault)
    got = links(vault)
    assert got == {
        "_other/home": str(root / ".giantmem"),
        "_other/Desktop-notes": str(root / "Desktop/notes/.giantmem"),
        "kai (dev-ai-kai)": str(root / "dev/ai/kai/.giantmem"),
        "kai (old-kai)": str(root / "old/kai/.giantmem"),
        "cerebro/_repo": str(root / "dev/ai/cerebro/.giantmem"),
        "cerebro/projects": str(root / "dev/ai/cerebro/projects/.giantmem"),
        "inv/_repo": str(root / "dev/ai/inv-wt/.giantmem"),
        "inv/main": str(root / "dev/ai/inv-wt/main/.giantmem"),
        "inv/feat-x": str(root / "dev/ai/inv-wt/feat/x/.giantmem"),
        "remi (dev-ai-remi)": str(root / "dev/ai/remi/.giantmem"),
        "remi (dev-ai-remi-wt)/main": str(root / "dev/ai/remi-wt/main/.giantmem"),
    }, got
    assert (vault / "inv/main/WORKSPACE.md").read_text() == "# ws\n"

    (vault / ".obsidian").mkdir()
    (vault / ".obsidian/app.json").write_text("{}")
    (vault / "mine.md").write_text("keep")
    (root / "dev/ai/inv-wt/feat/x/.giantmem/WORKSPACE.md").unlink()
    (root / "dev/ai/inv-wt/feat/x/.giantmem").rmdir()
    gv.sync(root, vault)
    got = links(vault)
    assert "inv/feat-x" not in got and "inv/main" in got, got
    assert (vault / "mine.md").read_text() == "keep"
    assert (vault / ".obsidian/app.json").exists()
    assert (root / "dev/ai/inv-wt/main/.giantmem/WORKSPACE.md").exists()


def test_old_mirror_layout_is_replaced(tmp_path):
    root, vault = tmp_path / "home", tmp_path / "vault"
    repo(root, "dev/ai/kai")
    mk(root, "dev/ai/kai")
    (vault / "dev/ai").mkdir(parents=True)
    (vault / "dev/ai/kai").symlink_to(root / "dev/ai/kai/.giantmem")
    (vault / "_giantmem").symlink_to(root / ".giantmem")
    gv.sync(root, vault)
    assert links(vault) == {"kai": str(root / "dev/ai/kai/.giantmem")}
    assert not (vault / "dev").exists()


def test_project_gaining_root_workspace_relinks_sub(tmp_path):
    root, vault = tmp_path / "home", tmp_path / "vault"
    repo(root, "a")
    mk(root, "a/b")
    gv.sync(root, vault)
    assert links(vault) == {"a/b": str(root / "a/b/.giantmem")}
    mk(root, "a")
    gv.sync(root, vault)
    assert links(vault) == {
        "a/_repo": str(root / "a/.giantmem"),
        "a/b": str(root / "a/b/.giantmem"),
    }
    assert (root / "a/b/.giantmem/WORKSPACE.md").exists()
    for rel in ("a/b", "a"):
        (root / rel / ".giantmem/WORKSPACE.md").unlink()
        (root / rel / ".giantmem").rmdir()
    mk(root, "a")
    gv.sync(root, vault)
    assert links(vault) == {"a": str(root / "a/.giantmem")}


def test_lone_root_workspace(tmp_path):
    root, vault = tmp_path / "home", tmp_path / "vault"
    mk(root, ".")
    gv.sync(root, vault)
    assert links(vault) == {"_other/home": str(root / ".giantmem")}


def test_real_dir_in_the_way_is_left_alone(tmp_path):
    root, vault = tmp_path / "home", tmp_path / "vault"
    repo(root, "a")
    mk(root, "a")
    (vault / "a").mkdir(parents=True)
    (vault / "a/notes.md").write_text("mine")
    gv.sync(root, vault)
    assert (vault / "a/notes.md").read_text() == "mine"
    assert not (vault / "a").is_symlink()


def test_empty_stray_files_removed(tmp_path):
    root, vault = tmp_path / "home", tmp_path / "vault"
    repo(root, "a")
    mk(root, "a")
    gv.sync(root, vault)
    (root / "a/.giantmem/blank.md").write_text("")
    (vault / "~/dev/x").mkdir(parents=True)
    (vault / "~/dev/x/stray.md").write_text("")
    (vault / "empty.md").write_text("")
    (vault / "mine.md").write_text("keep")
    (vault / ".obsidian").mkdir()
    (vault / ".obsidian/empty.json").write_text("")
    gv.sync(root, vault)
    assert not (vault / "~").exists()
    assert not (vault / "empty.md").exists()
    assert (vault / "mine.md").read_text() == "keep"
    assert (vault / ".obsidian/empty.json").exists()
    assert (root / "a/.giantmem/blank.md").exists()
    assert links(vault) == {"a": str(root / "a/.giantmem")}
