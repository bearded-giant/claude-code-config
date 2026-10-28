import importlib.util
from pathlib import Path


def load(name):
    spec = importlib.util.spec_from_file_location(
        name, Path(__file__).with_name(f"{name}.py")
    )
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


pf = load("preflight_check")
mr = load("mr_status")

# classify: exit 0 is ok, network noise is unknown, anything else is expired
assert pf.classify(0, "") is True
assert (
    pf.classify(1, "ERROR: (gcloud.auth.print-access-token) Reauthentication failed.")
    is False
)
assert pf.classify(1, "dial tcp: lookup vault.internal: no such host") is None
assert pf.classify(2, "Get https://x: context deadline exceeded") is None
assert (
    pf.classify(1, "x Logged in to gitlab.rechargeapps.net: 401 Unauthorized") is False
)

# run_check: missing binary is dropped, not reported red
assert pf.run_check(["definitely-not-a-binary-xyz"]) == "missing"
assert pf.run_check(["true"]) == {"ok": True}
assert pf.run_check(["false"]) == {"ok": False}

# project_from_remote: scp, https, ssh-with-port
assert mr.project_from_remote(
    "git@gitlab.rechargeapps.net:engineering/customcheckout.git\n"
) == (
    "gitlab.rechargeapps.net",
    "engineering/customcheckout",
)
assert mr.project_from_remote(
    "https://gitlab.rechargeapps.net/ai-tooling/monitor.git"
) == (
    "gitlab.rechargeapps.net",
    "ai-tooling/monitor",
)
assert mr.project_from_remote("ssh://git@gitlab.example.com:2222/a/b/c.git") == (
    "gitlab.example.com",
    "a/b/c",
)
assert (
    mr.project_from_remote("git@github.com:bearded-giant/claude-code-config.git")[0]
    == "github.com"
)
assert mr.project_from_remote("") == (None, None)


def mk(
    status: str | None = "success", merge="mergeable", sha="abc", pipe_sha="abc", **kw
):
    pipe = {"status": status, "sha": pipe_sha} if status else None
    return {"head_pipeline": pipe, "detailed_merge_status": merge, "sha": sha, **kw}


# verdict: hard blockers outrank waits, GREEN only when gitlab says mergeable
assert mr.verdict(mk()) == ("GREEN", "ok")
assert mr.verdict(mk(has_conflicts=True, status="failed")) == ("conflicts", "bad")
assert mr.verdict(mk(merge="conflict")) == ("conflicts", "bad")
assert mr.verdict(mk(status="failed", merge="discussions_not_resolved")) == (
    "pipe:failed",
    "bad",
)
assert mr.verdict(mk(status="canceled")) == ("pipe:failed", "bad")
assert mr.verdict(mk(merge="need_rebase")) == ("rebase", "bad")
assert mr.verdict(mk(status="running", merge="ci_still_running")) == (
    "pipe:running",
    "wait",
)
assert mr.verdict(mk(status=None, merge="ci_must_pass")) == ("no pipe", "wait")
assert mr.verdict(mk(pipe_sha="old")) == ("pipe:stale", "wait")
assert mr.verdict(mk(merge="draft_status", draft=True)) == ("draft", "wait")
assert mr.verdict(mk(merge="discussions_not_resolved")) == ("threads", "wait")
assert mr.verdict(mk(merge="not_approved")) == ("approval", "wait")
assert mr.verdict(mk(merge="requested_changes")) == ("approval", "wait")
assert mr.verdict(mk(merge="checking")) == ("checking", "wait")

def gh(state="CLEAN", checks=(), draft=False, review="APPROVED", mergeable="MERGEABLE"):
    return {
        "mergeStateStatus": state,
        "statusCheckRollup": list(checks),
        "isDraft": draft,
        "reviewDecision": review,
        "mergeable": mergeable,
    }


RUN = {"__typename": "CheckRun", "status": "COMPLETED", "conclusion": "SUCCESS"}
FAIL = {"__typename": "CheckRun", "status": "COMPLETED", "conclusion": "FAILURE"}
BUSY = {"__typename": "CheckRun", "status": "IN_PROGRESS", "conclusion": None}
CTX_OK = {"__typename": "StatusContext", "state": "SUCCESS"}
CTX_PENDING = {"__typename": "StatusContext", "state": "PENDING"}

# github_verdict: same tags as gitlab, read from gh pr list fields
assert mr.github_verdict(gh(checks=[RUN, CTX_OK])) == ("GREEN", "ok")
assert mr.github_verdict(gh(state="HAS_HOOKS", checks=[RUN])) == ("GREEN", "ok")
assert mr.github_verdict(gh(mergeable="CONFLICTING", checks=[FAIL])) == ("conflicts", "bad")
assert mr.github_verdict(gh(state="DIRTY")) == ("conflicts", "bad")
assert mr.github_verdict(gh(state="BLOCKED", checks=[RUN, FAIL])) == ("pipe:failed", "bad")
assert mr.github_verdict(gh(state="BEHIND", checks=[RUN])) == ("rebase", "bad")
assert mr.github_verdict(gh(state="BLOCKED", checks=[RUN, BUSY])) == ("pipe:running", "wait")
assert mr.github_verdict(gh(checks=[CTX_PENDING])) == ("pipe:running", "wait")
assert mr.github_verdict(gh()) == ("no pipe", "wait")
assert mr.github_verdict(gh(checks=[RUN], draft=True)) == ("draft", "wait")
assert mr.github_verdict(gh(state="BLOCKED", checks=[RUN], review="REVIEW_REQUIRED")) == ("approval", "wait")
assert mr.github_verdict(gh(state="BLOCKED", checks=[RUN], review="CHANGES_REQUESTED")) == ("approval", "wait")
assert mr.github_verdict(gh(state="BLOCKED", checks=[RUN])) == ("threads", "wait")
assert mr.github_verdict(gh(state="UNSTABLE", checks=[RUN])) == ("unstable", "wait")

print("ok")
