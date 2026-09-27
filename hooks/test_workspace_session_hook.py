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

    start = mod.claude_process_start()
    assert start is None or start <= time.time()
    print("ok")


if __name__ == "__main__":
    main()
