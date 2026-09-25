import importlib.util
import io
import sys
import tempfile
from contextlib import redirect_stdout
from pathlib import Path

spec = importlib.util.spec_from_file_location(
    "subagent_context", Path(__file__).with_name("subagent_context.py")
)
assert spec and spec.loader
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)


def run(flag, constraints):
    setattr(mod, "CAVEMAN_FLAG", flag)
    setattr(mod, "CONSTRAINTS", constraints)
    sys.stdin = io.StringIO("{}")
    buf = io.StringIO()
    with redirect_stdout(buf):
        mod.main()
    return buf.getvalue()


def main():
    with tempfile.TemporaryDirectory() as d:
        tmp = Path(d)
        flag, constraints, missing = tmp / "flag", tmp / "c.md", tmp / "missing.md"

        flag.write_text("full\n")
        constraints.write_text("SCOPE: stay in lane")
        out = run(flag, constraints)
        assert out.startswith("CAVEMAN MODE ACTIVE (full)."), out
        assert "SCOPE: stay in lane" in out

        # symlinked flag must never be read, same as caveman-config.js readFlag
        flag.unlink()
        (tmp / "secret").write_text("full")
        flag.symlink_to(tmp / "secret")
        assert run(flag, missing) == ""
        flag.unlink()

        for bad in ("commit", "rm -rf /", "x" * 100):
            flag.write_text(bad)
            assert "CAVEMAN" not in run(flag, missing), bad

        flag.unlink()
        assert run(flag, missing) == ""
    print("ok")


if __name__ == "__main__":
    main()
