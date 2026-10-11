import importlib.util
import io
import json
import sys
import tempfile
from contextlib import redirect_stdout
from pathlib import Path

spec = importlib.util.spec_from_file_location(
    "artifact_gate", Path(__file__).with_name("artifact_gate.py")
)
assert spec and spec.loader
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)


def run(**tool_input):
    sys.stdin = io.StringIO(
        json.dumps({"tool_name": "Artifact", "tool_input": tool_input})
    )
    buf = io.StringIO()
    with redirect_stdout(buf):
        mod.main()
    out = buf.getvalue().strip()
    return json.loads(out)["reason"] if out else ""


def main():
    with tempfile.TemporaryDirectory() as d:

        def page(name, body):
            p = Path(d, name)
            p.write_text(body, encoding="utf-8")
            return str(p)

        good = page(
            "good.html",
            '<html><head><meta name="source-note" content="areas/a/b/c.md"></head><body>'
            "<h1>Session store</h1><p class=rev><span>Rev 3</span> &middot; "
            "<time>2026-10-11 14:05 EDT</time></p><h2>How it works</h2></body></html>",
        )
        assert run(file_path=good) == ""

        nostamp = page("nostamp.html", "<h1>Session store</h1><p>2026-10-11</p>")
        assert "stamp" in run(file_path=nostamp)

        log = page(
            "log.html",
            "<h1>X</h1><p>Rev 2 · 2026-10-11 14:05</p><h2 id=c>Changelog</h2>"
            "<h3>What's new in rev 2</h3>",
        )
        reason = run(file_path=log)
        assert "`Changelog`" in reason and "What's new in rev 2" in reason, reason

        md = page("doc.md", "# X\n\nRev 1 · 2026-10-11T09:00\n\n## Revision history\n")
        assert "Revision history" in run(file_path=md)

        hidden = page(
            "hidden.html", "<h1>X</h1><script>// Rev 1 · 2026-10-11 10:00</script>"
        )
        assert "stamp" in run(file_path=hidden)

        assert run(file_path=nostamp, action="read") == ""
        assert run(file_path=nostamp, asset=True, url="u") == ""
        assert run(file_path=page("img.png", "x")) == ""
        assert run(action="list") == ""
    print("ok")


if __name__ == "__main__":
    main()
