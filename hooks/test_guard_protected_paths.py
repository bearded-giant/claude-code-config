import os

import guard_protected_paths as g


def test_view_path_resolves_to_repo(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    real = tmp_path / "dev/cfg/.giantmem"
    real.mkdir(parents=True)
    (tmp_path / "giantmem-vault").mkdir()
    os.symlink(real, tmp_path / "giantmem-vault/cfg")
    assert g.view_target("~/giantmem-vault/cfg/notes.md", "/") == str(
        (real / "notes.md").resolve()
    )
    assert g.view_target("cfg/notes.md", str(tmp_path / "giantmem-vault")) == str(
        (real / "notes.md").resolve()
    )


def test_other_paths_pass(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    assert g.view_target("~/Recharge-Notes/areas/x.md", "/") is None
    assert g.view_target("~/giantmem-vault-other/x.md", "/") is None
    assert g.view_target("~/giantmem-vault/.obsidian/app.json", "/") is None
    assert g.view_target("~/giantmem-vault/stray.md", "/") is not None
    assert g.view_target(str(tmp_path / "dev/cfg/.giantmem/x.md"), "/") is None
