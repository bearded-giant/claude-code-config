import importlib.util
from pathlib import Path

spec = importlib.util.spec_from_file_location(
    "session_prime", Path(__file__).with_name("session_prime.py")
)
assert spec and spec.loader
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)


def main() -> None:
    assert mod.render({"project": "p"}) is None

    docs_only = mod.render(
        {"project": "p", "recent_docs": [{"dir_type": "history", "path": "/x.md"}]}
    )
    assert (
        docs_only
        and "recent .giantmem/ writes:" in docs_only
        and "open MRs" not in docs_only
    )

    # open MRs alone are actionable: the prime must not be skipped
    out = mod.render(
        {
            "project": "recharge-auth",
            "open_mrs": [
                {
                    "label": "recharge-auth!63",
                    "url": "https://gitlab.example/identity/recharge-auth/-/merge_requests/63",
                    "state": "conflicts",
                    "opener": "f8943589",
                    "role": "opened",
                    "cached": False,
                },
                {
                    "label": "terraform!4177",
                    "url": "https://gitlab.example/infra/terraform/-/merge_requests/4177",
                    "state": "GREEN",
                    "opener": "974061b2",
                    "role": "touched",
                    "cached": True,
                },
            ],
        }
    )
    assert out is not None
    lines = out.splitlines()
    assert lines[0] == "<system-reminder>" and lines[-1] == "</system-reminder>"
    assert (
        "  - recharge-auth!63  conflicts  f8943589  https://gitlab.example/identity/recharge-auth/-/merge_requests/63"
        in lines
    ), out
    assert (
        "  - terraform!4177  GREEN (cached)  974061b2 (first touched)  "
        "https://gitlab.example/infra/terraform/-/merge_requests/4177" in lines
    ), out
    print("ok")


if __name__ == "__main__":
    main()
