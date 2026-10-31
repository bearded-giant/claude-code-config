import importlib.util
import os
import tempfile
import time
from pathlib import Path

spec = importlib.util.spec_from_file_location(
    "workspace_session_hook", Path(__file__).with_name("workspace_session_hook.py")
)
assert spec and spec.loader
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)


def main():
    now = time.time()
    with tempfile.TemporaryDirectory() as d:
        old, new, missing = Path(d) / "old", Path(d) / "new", Path(d) / "missing"
        old.write_text("x")
        new.write_text("x")
        os.utime(old, (now - 100, now - 100))
        os.utime(new, (now + 100, now + 100))
        assert mod.stale_plugins(now, [old, new, missing]) == [str(new)]

        vars(mod).update(PLUGIN_PATHS=[new])
        # not a /clear: never warn, even with stale paths
        assert mod.restart_notice("startup") == ""
        vars(mod).update(claude_process_start=lambda: now)
        notice = mod.restart_notice("clear")
        assert notice.startswith("FULL RESTART REQUIRED") and str(new) in notice
        vars(mod).update(claude_process_start=lambda: None)
        assert mod.restart_notice("clear") == ""

    template = "---\ntype: plan\nstatus: active\n---\n\n# Current Plan\n\n## Steps\n\n<!-- add -->\n"
    out = mod.format_context_output({"current_plan": template}, "/x/proj", False)
    assert "ACTIVE PLAN" not in out, out
    filled = template + "1. ship the cache fix\n"
    out = mod.format_context_output({"current_plan": filled}, "/x/proj", False)
    assert "=== ACTIVE PLAN ===" in out and "ship the cache fix" in out, out

    out = mod.format_context_output(
        {"workspace_md": "# ws\n", "current_plan": None}, "/x/proj", False
    )
    assert "=== WORKSPACE CONTEXT ===" in out and "ACTIVE PLAN" not in out, out

    ws = "# Workspace: p\n\n## Purpose\n<!-- describe -->\n\n## Features\n\n| a | b |\n\n## Notes\n<!-- notes -->\n"
    with tempfile.TemporaryDirectory() as d:
        (Path(d) / ".giantmem").mkdir()
        (Path(d) / ".giantmem" / "WORKSPACE.md").write_text(ws)
        out = mod.format_context_output(mod.read_workspace_context(d), d, False)
    assert "<!--" not in out and "## Purpose" not in out and "## Notes" not in out, out
    assert "## Features\n\n| a | b |" in out and "# Workspace: p" in out, out

    start = mod.claude_process_start()
    assert start is None or start <= time.time()
    print("ok")


if __name__ == "__main__":
    main()
