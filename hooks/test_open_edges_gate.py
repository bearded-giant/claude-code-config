import importlib.util
import io
import json
import os
import sys
import tempfile
from contextlib import redirect_stdout
from pathlib import Path

spec = importlib.util.spec_from_file_location(
    "open_edges_gate", Path(__file__).with_name("open_edges_gate.py")
)
assert spec and spec.loader
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

# user-reported examples, trimmed
DOIT_REPORT = """Work done, see table above.

**Open edges:**
- **Renamed windows lose their link.** Links follow the window name, so renaming a window drops it to `daily` until you link it again.
- **No fallback to the session link**, because you said "not session".
- **MCP contract change:** `switch_list` now takes `scope: "window"` instead of `"session"`. Nothing in your configs passed `"session"`.
- `tests/modules/obsidian-sync/json_sync_spec.lua` has 1 failing test. It fails the same way without my changes, and I didn't touch obsidian-sync.

**What changed:**
- Links are now saved under a `#S:#W` key.
"""

AUTH_REPORT = """Settings now hides the field. It's committed on the same branch, `a5c1cb7`.

**Not done yet:**
- **Still not pushed, no MR.** The branch now has 2 commits and is still only in the scratch clone, at the same `/private/tmp/...` path as before, which is lost on reboot.
- **Tested in headless Chrome only**, with the same fake `/auth/me`. I haven't seen it on Vercel.
- **doit #11** is now unblocked because !61 is live. It touches the same files. I didn't do it; it's queued for `/burn`.

**What changed** (`ui/app.js`):
- The base URL field sits inside a native `<details>`.
"""

OFFER_REPORT = """Done.

## Open edges
1. **Push and MR:** say "ship it" and I'll push and open the MR.
2. **Not committed:** 6 files are modified. Nothing told me to commit in that repo.

## Burn summary
| # | item |
"""

CLEAN_REPORT = """Open edges
- Gate: after the deploy, open Settings signed in. Expect no Bearer field; a visible field means the `/auth/me` probe failed.
- `daily #83`: whether to show the client secret on the card. The vendor docs do not settle it.
- Limit: links follow the window name, by your choice of key; a renamed window needs relinking.

What changed
- `ui/app.js` hides the bearer field when `sessionCoversApi()` is true.
"""

NO_SECTION = """The failing test is in obsidian-sync. I didn't touch it and I haven't run it; it's outside this change. Say "fix it" and I'll look."""

GATE_SHAPES = """**Open edges**
- **Merge.** !36686 has 0 approvals and isn't merged. I added a new unchecked box for merging to `stage`.
- **Not verified: does `rc_session` reach the Remix server (daily #83).** I inferred it from the apex cookie domain.
- Not tested on Vercel. After the deploy, sign in and open Settings. Expect no Bearer field; a visible field means the probe failed.
- `db_connections.vim.old.bak` holds credentials, so it is untracked on purpose.
- `investigator-cli-mcp #7` (dep on #5): 401 redirect to `/auth/login`, queued for /burn once !61 merges. I didn't do it here.

**Done**
- the rest.
"""

WIDE_HEADER = """**Open edges (read these first):**
- **The numbers below are estimates from reading the code, not measurements.** Neither bucket exists yet.

**Why it's accurate:**
- versioning on.
"""


def tags(text):
    return [t for t, _ in mod.findings(text)]


def run_hook(text, stop_hook_active=False):
    with tempfile.TemporaryDirectory() as d:
        path = Path(d, "t.jsonl")
        entries = [
            {"type": "user", "message": {"content": "do the thing"}},
            {
                "type": "assistant",
                "message": {"content": [{"type": "text", "text": "Starting."}]},
            },
            {"type": "user", "message": {"content": [{"type": "tool_result"}]}},
            {"type": "attachment", "attachment": {}},
            {
                "type": "assistant",
                "message": {"content": [{"type": "text", "text": text}]},
            },
        ]
        path.write_text("\n".join(json.dumps(e) for e in entries), encoding="utf-8")
        sys.stdin = io.StringIO(
            json.dumps(
                {"transcript_path": str(path), "stop_hook_active": stop_hook_active}
            )
        )
        buf = io.StringIO()
        with redirect_stdout(buf):
            mod.main()
        out = buf.getvalue().strip()
        return json.loads(out) if out else None


def main():
    assert tags(DOIT_REPORT) == ["PREEXISTING"], tags(DOIT_REPORT)
    assert tags(AUTH_REPORT) == ["SCRATCH", "UNVERIFIED", "PARKED"], tags(AUTH_REPORT)
    assert tags(OFFER_REPORT) == ["OFFER", "GIT"], tags(OFFER_REPORT)
    assert tags(CLEAN_REPORT) == [], tags(CLEAN_REPORT)
    assert tags(NO_SECTION) == [], tags(NO_SECTION)
    assert tags(WIDE_HEADER) == [], tags(WIDE_HEADER)
    assert tags(GATE_SHAPES) == [], tags(GATE_SHAPES)

    # section ends at the next heading: "What changed" items are not scanned
    assert "Links are now saved" not in " ".join(
        q for _, q in mod.findings(DOIT_REPORT)
    )

    out = run_hook(AUTH_REPORT)
    assert out and out["decision"] == "block", out
    assert "[SCRATCH]" in out["reason"] and "[PARKED]" in out["reason"], out["reason"]
    assert run_hook(AUTH_REPORT, stop_hook_active=True) is None
    assert run_hook(CLEAN_REPORT) is None

    os.environ[mod.BYPASS_ENV] = "off"
    try:
        assert run_hook(AUTH_REPORT) is None
    finally:
        del os.environ[mod.BYPASS_ENV]

    # only the final turn counts: an earlier flagged report followed by a user
    # message and a clean report passes
    with tempfile.TemporaryDirectory() as d:
        path = Path(d, "t.jsonl")
        entries = [
            {
                "type": "assistant",
                "message": {"content": [{"type": "text", "text": AUTH_REPORT}]},
            },
            {"type": "user", "message": {"content": "ok"}},
            {
                "type": "assistant",
                "message": {"content": [{"type": "text", "text": CLEAN_REPORT}]},
            },
        ]
        path.write_text("\n".join(json.dumps(e) for e in entries), encoding="utf-8")
        assert mod.findings(mod.last_assistant_text(str(path))) == []

    print("ok")


if __name__ == "__main__":
    main()
