import importlib.util
from pathlib import Path

spec = importlib.util.spec_from_file_location(
    "greptile_rereview", Path(__file__).with_name("greptile_rereview.py")
)
assert spec and spec.loader
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

CWD = "/repo"

# push_dir: where the push ran
assert mod.push_dir("ls -la", CWD) is None
assert mod.push_dir("git push", CWD) == CWD
assert mod.push_dir("git -C /other/repo push -u origin feat", CWD) == "/other/repo"
assert mod.push_dir("cd /x/y && git push", CWD) == "/x/y"
assert mod.push_dir("cd sub && git add -A && git commit -m x && git push", CWD) == "/repo/sub"
assert mod.push_dir("echo pushing", CWD) is None

# pushes_branch: only branch pushes count, never tags or deletes
assert mod.pushes_branch("git push", "feat")
assert mod.pushes_branch("git push -u origin feat", "feat")
assert mod.pushes_branch("git push origin HEAD", "feat")
assert mod.pushes_branch("git push -q 2>&1 | grep -v remote", "feat")
assert mod.pushes_branch("git push origin feat:feat && echo ok", "feat")
assert not mod.pushes_branch("git push origin 0.1.1", "feat")
assert not mod.pushes_branch("git push --tags", "feat")
assert not mod.pushes_branch("git push origin --delete feat", "feat")
assert not mod.pushes_branch("git push origin other-branch", "feat")

print("ok")
