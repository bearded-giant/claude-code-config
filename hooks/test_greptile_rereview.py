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
# a pipe or ; between the cd and the push must not drop back to the session cwd (another repo)
assert mod.push_dir("cd /x/y && git commit -m z 2>&1 | grep -E err; git log -1 && git push 2>&1 | tail -2", CWD) == "/x/y"
assert mod.push_dir("cd /a && ls; cd /b && git push", CWD) == "/b"
# cds chain: each resolves against the directory the previous one left, `..` included
assert mod.push_dir("cd /x/y/sub && pre-commit run; cd ../.. && git add f && git commit -m z; git push", CWD) == "/x"
assert mod.push_dir("cd /x && cd sub && git push", CWD) == "/x/sub"
assert mod.push_dir("cd /x && git -C sub push", CWD) == "/x/sub"
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

# greptile_reviews / already_requested: read from the MR's notes
APPROVED = {"author": {"username": "greptile"}, "body": "approved this merge request", "created_at": "2026-10-18T17:40:25Z"}
ASKED = {"author": {"username": "dev"}, "body": "@greptile review", "created_at": "2026-10-18T18:10:00Z"}
assert mod.greptile_reviews([APPROVED])
assert not mod.greptile_reviews([ASKED])
assert not mod.greptile_reviews([])
assert mod.already_requested([ASKED], "abc", mod._ts("2026-10-18T18:06:00Z"))
assert not mod.already_requested([ASKED], "abc", mod._ts("2026-10-18T18:20:00Z"))

# request_review: a repo with no .greptile/ still gets the request once greptile has acted on its MR
def stub(notes, posted):
    def run(args, cwd, timeout=15):
        if args[0] == "git":
            return {"rev-parse": "/tmp", "remote": "git@gitlab.example:g/r.git"}.get(args[3], "")
        if args[:3] == ["glab", "mr", "list"]:
            return '[{"iid": 7}]'
        if args[:3] == ["glab", "mr", "view"]:
            return '{"sha": "/tmp"}'
        if args[:2] == ["glab", "api"]:
            return __import__("json").dumps(notes)
        if args[:3] == ["glab", "mr", "note"]:
            posted.append(args)
        return ""
    return run

def git(top, *args):
    if args[:2] == ("rev-parse", "--abbrev-ref"):
        return "feat"
    if args[0] == "log":
        return "2026-10-18T18:06:00Z"
    return mod._run(["git", "-C", top, *args], top)

PUSH = {"tool_input": {"command": "git push"}, "cwd": "/tmp"}
mod._git = git
posted = []
mod._run = stub([APPROVED], posted)
assert mod.request_review(PUSH) and len(posted) == 1
posted = []
mod._run = stub([], posted)
assert mod.request_review(PUSH) is None and not posted


# request_github_review: greptile's github handle is @greptileai; a review already on the head means no post
def gh_stub(reviews, posted):
    def run(args, cwd, timeout=15):
        if args[0] == "git":
            return "git@github.com:o/r.git" if "github" in args else ""
        if args[:3] == ["gh", "pr", "list"]:
            return '[{"number": 5, "headRefOid": "abc"}]'
        if args[:2] == ["gh", "api"]:
            return __import__("json").dumps(reviews)
        if args[:3] == ["gh", "pr", "comment"]:
            posted.append(args)
        return ""
    return run

posted = []
mod._run = gh_stub([], posted)
msg = mod.request_github_review("/tmp", "feat", "abc")
assert posted and posted[0][-1] == "@greptileai review", posted
assert "o/r#5" in msg and "@greptileai review" in msg, msg
posted = []
mod._run = gh_stub([{"user": {"login": "greptile-apps[bot]"}, "commit_id": "abc"}], posted)
assert mod.request_github_review("/tmp", "feat", "abc") is None
assert not posted
print("ok")
