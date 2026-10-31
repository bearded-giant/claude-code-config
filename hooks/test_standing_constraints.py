import importlib.util
import sys
import tempfile
from pathlib import Path

CONSTRAINTS = Path(__file__).resolve().parents[1] / "config" / "standing-constraints.md"
spec = importlib.util.spec_from_file_location(
    "standing_constraints", Path(__file__).with_name("standing_constraints.py")
)
assert spec and spec.loader
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)
# claude code persists hook stdout over 10k chars to a file and shows the model a 2k preview;
# dispatch prints these constraints in the same stdout as giantmem recall (max seen ~2.6k) and the auto mode line
HOOK_STDOUT_LIMIT = 10_000
RECALL_MAX = 2_600
AUTO_MODE_LINE = 300


def cadence_cases():
    stamp = {"v": ""}
    with tempfile.TemporaryDirectory() as d:
        vars(mod).update(STATE_DIR=Path(d), _compact_stamp=lambda _: stamp["v"])
        # CLAUDE.md is in context on prompt 1, so the constraints wait for drift
        got = [mod._should_inject("s1") for _ in range(mod.REINJECT_EVERY + 1)]
        want = [n == mod.REINJECT_EVERY for n in range(1, mod.REINJECT_EVERY + 2)]
        assert got == want, got
        stamp["v"] = "123"
        assert mod._should_inject("s1") is True
        assert mod._should_inject("s1") is False
        assert mod._should_inject("") is True


def main(path=CONSTRAINTS):
    cadence_cases()
    size = len(path.read_text(encoding="utf-8").strip())
    budget = HOOK_STDOUT_LIMIT - RECALL_MAX - AUTO_MODE_LINE
    assert (
        size <= budget
    ), f"{path.name} is {size} chars; keep it under {budget} so the hook output stays inline"
    print("ok")


if __name__ == "__main__":
    main(Path(sys.argv[1]) if len(sys.argv) > 1 else CONSTRAINTS)
