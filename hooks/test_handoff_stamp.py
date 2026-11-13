import contextlib
import importlib.util
import io
import json
import re
import sys
import tempfile
from pathlib import Path

spec = importlib.util.spec_from_file_location(
    "handoff_stamp", Path(__file__).with_name("handoff_stamp.py")
)
assert spec and spec.loader
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

ET_STAMP = re.compile(r"\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d-0[45]:00")


def run(data):
    sys.stdin = io.StringIO(json.dumps(data))
    with contextlib.redirect_stdout(io.StringIO()) as out:
        mod.main()
    sys.stdin = sys.__stdin__
    return out.getvalue()


def front(path, key):
    return mod.value_of(path.read_text(), key)


def event(tool, path, resp):
    return {
        "hook_event_name": "PostToolUse",
        "tool_name": tool,
        "tool_input": {"file_path": str(path)},
        "tool_response": resp,
    }


def main():
    now = "2026-11-13T15:04:05-05:00"
    assert mod.as_et("2026-11-13T20:00:00+00:00") == "2026-11-13T15:00:00-05:00"
    assert mod.as_et("2026-07-01T12:00:00Z") == "2026-07-01T08:00:00-04:00"
    assert mod.as_et("2026-11-13") is None
    assert mod.as_et("2026-11-12 17:25 EST") is None

    body = "---\ntype: handoff\nstatus: ready\ncreated: 2026-11-13\nupdated: 2026-11-13\n---\n\n# h\n"
    out = mod.stamp(body, None, now)
    assert f"created: {now}\nupdated: {now}\n---\n\n# h\n" in out, out

    old = body.replace("created: 2026-11-13", "created: 2026-11-12T09:00:00-05:00")
    out = mod.stamp(body, old, now)
    assert "created: 2026-11-12T09:00:00-05:00\n" in out, out
    assert f"updated: {now}" in out

    # bare date with no earlier timestamp stays; no invented time
    assert "created: 2026-11-13\n" in mod.stamp(body, body, now)

    missing = "---\ntype: handoff\nstatus: ready\n---\nx\n"
    out = mod.stamp(missing, None, now)
    assert out.startswith("---\ntype: handoff\nstatus: ready\n") and out.endswith(
        f"created: {now}\nupdated: {now}\n---\nx\n"
    ), out
    assert mod.stamp("# no frontmatter\n", None, now) is None

    with tempfile.TemporaryDirectory() as tmp:
        vars(mod).update(VAULT=Path(tmp))
        handoffs = Path(tmp) / "areas" / "proj" / "handoffs"
        (handoffs / "features").mkdir(parents=True)

        new = handoffs / "features" / "feat.md"
        new.write_text(body)
        ctx = run(event("Write", new, {"type": "create", "originalFile": None}))
        assert ET_STAMP.fullmatch(front(new, "created")), new.read_text()
        assert front(new, "created") == front(new, "updated")
        assert (
            "handoff_stamp"
            in json.loads(ctx)["hookSpecificOutput"]["additionalContext"]
        )

        over = handoffs / "main.md"
        over.write_text(body)
        run(event("Write", over, {"type": "update", "originalFile": old}))
        assert front(over, "created") == "2026-11-12T09:00:00-05:00"
        assert ET_STAMP.fullmatch(front(over, "updated"))

        edited = handoffs / "branch.md"
        edited.write_text(old.replace("status: ready", "status: done"))
        run(event("Edit", edited, {"originalFile": None}))
        assert front(edited, "created") == "2026-11-12T09:00:00-05:00"
        assert ET_STAMP.fullmatch(front(edited, "updated"))

        elsewhere = Path(tmp) / "areas" / "proj" / "notes.md"
        elsewhere.write_text(body)
        assert run(event("Write", elsewhere, {"type": "create"})) == ""
        assert elsewhere.read_text() == body

        assert run({**event("Read", new, {}), "tool_name": "Read"}) == ""
        sys.stdin = io.StringIO("nope")
        mod.main()
        sys.stdin = sys.__stdin__
    print("ok")


if __name__ == "__main__":
    main()
