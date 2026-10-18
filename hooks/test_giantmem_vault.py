import os
from pathlib import Path

import giantmem_vault as gv


def mk(root, *rels):
    for rel in rels:
        (root / rel / ".giantmem").mkdir(parents=True)
        (root / rel / ".giantmem" / "WORKSPACE.md").write_text("# ws\n")


def links(vault):
    out = {}
    for dirpath, dirnames, filenames in os.walk(vault):
        for n in dirnames + filenames:
            p = Path(dirpath) / n
            if p.is_symlink():
                out[str(p.relative_to(vault))] = os.readlink(p)
    return out


def test_mirror_nested_root_and_prune(tmp_path):
    root, vault = tmp_path / "dev", tmp_path / "vault"
    mk(
        root,
        ".",
        "cfg",
        "cfg/plugins",
        "ai/kai",
        "python/cc-wt/stage",
        "x/node_modules/pkg",
        "cfg/.mdlive/history",
        "cfg/plugins/cache/x",
    )
    (root / "deep/a/b/c/d/e/f").mkdir(parents=True)
    mk(root, "deep/a/b/c/d/e/f/g")
    (root / "cfg/.giantmem/inner/.giantmem").mkdir(parents=True)

    gv.sync(root, vault)
    got = links(vault)
    assert got == {
        "_dev": str(root / ".giantmem"),
        "cfg": str(root / "cfg/.giantmem"),
        "cfg--plugins": str(root / "cfg/plugins/.giantmem"),
        "ai/kai": str(root / "ai/kai/.giantmem"),
        "python/cc-wt/stage": str(root / "python/cc-wt/stage/.giantmem"),
    }, got
    assert (vault / "ai/kai/WORKSPACE.md").read_text() == "# ws\n"

    (vault / ".obsidian").mkdir()
    (vault / ".obsidian/app.json").write_text("{}")
    (vault / "mine.md").write_text("keep")
    (root / "ai/kai/.giantmem/WORKSPACE.md").unlink()
    (root / "ai/kai/.giantmem").rmdir()
    gv.sync(root, vault)
    got = links(vault)
    assert "ai/kai" not in got and not (vault / "ai").exists(), got
    assert (vault / "mine.md").read_text() == "keep"
    assert (vault / ".obsidian/app.json").exists()
    assert (root / "cfg/.giantmem/WORKSPACE.md").exists()


def test_ancestor_gaining_workspace_relinks_child(tmp_path):
    root, vault = tmp_path / "dev", tmp_path / "vault"
    mk(root, "a/b")
    gv.sync(root, vault)
    assert links(vault) == {"a/b": str(root / "a/b/.giantmem")}
    mk(root, "a")
    gv.sync(root, vault)
    assert links(vault) == {
        "a": str(root / "a/.giantmem"),
        "a--b": str(root / "a/b/.giantmem"),
    }
    assert (root / "a/b/.giantmem/WORKSPACE.md").exists()


def test_real_dir_in_the_way_is_left_alone(tmp_path):
    root, vault = tmp_path / "dev", tmp_path / "vault"
    mk(root, "a")
    (vault / "a").mkdir(parents=True)
    (vault / "a/notes.md").write_text("mine")
    gv.sync(root, vault)
    assert (vault / "a/notes.md").read_text() == "mine"
    assert not (vault / "a").is_symlink()
