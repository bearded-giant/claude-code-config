#!/usr/bin/env python3
"""Run several hook modules in one process, so an event pays one process spawn
instead of N. Spawn cost is ~300ms here; the hooks themselves are ~50ms.

Only for events whose hooks emit plain text (stdout is concatenated). A hook
that emits hookSpecificOutput / decision JSON must stay its own entry: two
control objects cannot be merged into one stdout.
"""

import importlib.util
import io
import json
import sys
from contextlib import redirect_stdout
from pathlib import Path

HOOKS = Path(__file__).resolve().parent


def run(name, raw):
    buf = io.StringIO()
    saved = sys.stdin
    try:
        spec = importlib.util.spec_from_file_location(
            f"_hook_{name}", HOOKS / f"{name}.py"
        )
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        sys.stdin = io.StringIO(raw)
        with redirect_stdout(buf):
            mod.main()
    except BaseException:  # pylint: disable=broad-exception-caught
        # SystemExit too: one hook must not end the run
        pass
    finally:
        sys.stdin = saved
    return buf.getvalue().strip()


def main():
    raw = sys.stdin.read()
    out = []
    for name in sys.argv[1:]:
        chunk = run(name, raw)
        if not chunk:
            continue
        try:
            json.loads(chunk)
        except (json.JSONDecodeError, ValueError):
            out.append(chunk)
            continue
        print(chunk)
        return
    if out:
        print("\n\n".join(out))


if __name__ == "__main__":
    main()
