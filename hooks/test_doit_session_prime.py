import importlib.util
from pathlib import Path

spec = importlib.util.spec_from_file_location(
    "doit_session_prime", Path(__file__).with_name("doit_session_prime.py")
)
assert spec and spec.loader
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

CASES = [
    # worktree == feature collapses to one segment
    ("/dev/cc-wt/sec-auth0-fix", "sec-auth0-fix", "cc-sec-auth0-fix"),
    # org prefix and -wt container suffix dropped
    ("/dev/recharge-auth-wt/better-redis-search", "session-index", "auth-session-index"),
    ("/dev/recharge-auth-wt/better-redis-search", "better-redis-search", "auth-better-redis-search"),
    # over the cap: trailing words shed, never cut mid-word
    ("/dev/recharge-auth-wt/better-redis-search", "service-auth-decouple", "auth-service-auth"),
    ("/dev/recharge-merchant-mcp-wt/legacy-oauth-connectors", "legacy-oauth-connectors", "merchant-mcp-legacy"),
    # long repo names keep their first word
    ("/dev/investigator-agent-wt/admin-qol", "admin-qol", "investigator-admin-qol"),
    ("/dev/claude-code-config", "assigned-reviews", "claude-assigned-reviews"),
    # feat- prefix dropped
    ("/dev/frontend-wt/feat-redact-api-tokens", "feat-redact-api-tokens", "frontend-redact-api"),
    # no feature: non-default worktree names the list, default worktree does not
    ("/dev/cc-wt/stage", None, "cc-stage"),
    ("/dev/remi-wt/main", None, "remi"),
    ("/dev/remi-wt/main", "monorepo", "remi-monorepo"),
    # plain repo, short enough to keep whole
    ("/dev/giant-tooling", None, "giant-tooling"),
    ("/dev/do-it.nvim", None, "do-it.nvim"),
]


def main() -> None:
    for root, feat, expected in CASES:
        got = mod.list_name(root, feat)
        assert got == expected, f"{root} {feat}: {got!r} != {expected!r}"
        assert len(got) <= mod.MAX_LIST_NAME

    # one word longer than the cap is hard cut
    long = mod.list_name("/dev/cc-wt/x", "a" * 40)
    assert len(long) == mod.MAX_LIST_NAME and long.startswith("cc-a")
    print("ok")


if __name__ == "__main__":
    main()
