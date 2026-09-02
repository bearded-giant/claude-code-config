#!/usr/bin/env python3
"""Self-check for the harvester filters. Run: python3 hooks/workspace_session_end_check.py"""

import importlib.util
from pathlib import Path

spec = importlib.util.spec_from_file_location(
    "wse", Path(__file__).parent / "workspace_session_end.py"
)
wse = importlib.util.module_from_spec(spec)
spec.loader.exec_module(wse)


def main():
    # mid-sentence captures: what the unanchored patterns used to produce
    assert not wse.is_sentence("imports, subprocess calls.")
    assert not wse.is_sentence("structure and how a feature dir is shaped here.")
    assert not wse.is_sentence('The "config value is set in settings.json.')
    assert not wse.is_sentence("| important | done | bounded instead of cached |")
    assert not wse.is_sentence("Config is loaded lazily")

    assert wse.is_sentence("Config removal dropped SessionStart from 10 hooks to 7.")

    hit = "Config removal dropped SessionStart from 10 hooks to 7."
    miss = "We rewired the dispatcher and the config came along with it."
    found = wse.extract_discoveries(f"{hit}\n{miss}\n")
    assert found == [("config", hit)], found

    # "next" as an ordinary word used to capture the rest of the line
    assert wse.extract_plans("The next session will confirm the timing.\n") == []
    assert wse.extract_plans("TODO: raise the prime timeout to 8s\n") == [
        "TODO: raise the prime timeout to 8s"
    ]

    print("ok")


if __name__ == "__main__":
    main()
