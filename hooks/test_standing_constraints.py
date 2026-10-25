import sys
from pathlib import Path

CONSTRAINTS = Path(__file__).resolve().parents[1] / "config" / "standing-constraints.md"
# claude code persists hook stdout over 10k chars to a file and shows the model a 2k preview;
# dispatch prints these constraints in the same stdout as giantmem recall (max seen ~2.6k) and the auto mode line
HOOK_STDOUT_LIMIT = 10_000
RECALL_MAX = 2_600
AUTO_MODE_LINE = 300


def main(path=CONSTRAINTS):
    size = len(path.read_text(encoding="utf-8").strip())
    budget = HOOK_STDOUT_LIMIT - RECALL_MAX - AUTO_MODE_LINE
    assert (
        size <= budget
    ), f"{path.name} is {size} chars; keep it under {budget} so the hook output stays inline"
    print("ok")


if __name__ == "__main__":
    main(Path(sys.argv[1]) if len(sys.argv) > 1 else CONSTRAINTS)
