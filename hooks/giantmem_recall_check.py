#!/usr/bin/env python3
"""Regression checks for giantmem_recall.py classification and merge logic.

Run by hand: python3 hooks/giantmem_recall_check.py
Not a registered hook.
"""

import importlib.util
import os
import sys
from typing import Any

HERE = os.path.dirname(os.path.abspath(__file__))
spec = importlib.util.spec_from_file_location(
    "gr", os.path.join(HERE, "giantmem_recall.py")
)
assert spec is not None and spec.loader is not None
gr: Any = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gr)


def hit(key, cur, sib, tag="fts"):
    return {
        "key": key,
        "cur": cur,
        "sib": sib,
        "loc": "l",
        "name": key,
        "snippet": "",
        "tag": tag,
    }


def names(lines):
    return [line.split()[2] for line in lines]


def main():
    assert gr.canon("frost-wt") == "frost"
    assert gr.canon("python-cc-wt--bare") == "python-cc"
    assert gr.canon("/hyphae/") == "hyphae"

    # live_index.detect_project is the python peer of Go project.Detect; drift here
    # silently mislabels every live_docs row, so pin the three shapes that differ
    li = gr.live_index_mod()
    assert (
        li.detect_project("/Users/bryan/dev/giant-tooling/giantmem", li.ARCHIVE_BASE)[0]
        == "giant-tooling"
    )
    assert (
        li.detect_project("/Users/bryan/dev/python/cc-wt/stage", li.ARCHIVE_BASE)[0]
        == "cc-wt"
    )
    assert li.detect_project("/Users/bryan", li.ARCHIVE_BASE)[0] == "bryan"

    repo = ("hyphae", "/Users/bryan/dev/ai/hyphae/")
    assert gr.is_current(
        repo, "frost", path="/Users/bryan/dev/ai/hyphae/.giantmem/x.md"
    )
    assert gr.is_current(
        repo,
        "ai-hyphae",
        path="/Users/bryan/.claude/projects/-Users-bryan-dev-ai-hyphae/memory/a.md",
    )
    assert not gr.is_current(
        repo, "frost", path="/Users/bryan/dev/skio/frost/.giantmem/filebox/t.md"
    )
    assert gr.is_current(
        ("cc", "/Users/bryan/dev/python/cc-wt/stage/"),
        "cc-wt",
        worktree="/Users/bryan/dev/python/cc-wt/main",
    )

    # worktree siblings of one doc collapse
    assert gr.sibling_key(
        "frost", "/Users/bryan/dev/skio/frost/.giantmem/filebox/t.md"
    ) == gr.sibling_key(
        "frost-wt", "/Users/bryan/dev/skio/frost-wt/b/.giantmem/filebox/t.md"
    )
    # same doc reached via fts (absolute path) and semantic (artifact-relative path) collapses
    assert gr.sibling_key(
        "hyphae", "/Users/bryan/dev/ai/hyphae/.giantmem/research/x.md"
    ) == gr.sibling_key("hyphae", "research/x.md")
    # memory files key on basename
    assert gr.sibling_key(
        "ai-hyphae",
        "/Users/bryan/.claude/projects/-Users-bryan-dev-ai-hyphae/memory/m.md",
    ) == (
        "ai-hyphae",
        "m.md",
    )

    gr.LIMIT, gr.CROSS_MAX, gr.BUDGET = 4, 1, 10_000
    cur5 = [hit(f"c{i}", True, ("r", f"c{i}")) for i in range(5)]
    oth3 = [hit(f"o{i}", False, ("x", f"o{i}")) for i in range(3)]
    assert names(gr.merge([], cur5 + oth3)) == ["c0", "c1", "c2", "o0"]
    assert len(gr.merge([], cur5)) == 4
    assert names(
        gr.merge([], cur5[:1] + [hit(f"o{i}", False, ("x", f"o{i}")) for i in range(5)])
    ) == ["c0", "o0"]
    assert (
        len(
            gr.merge(
                [],
                [
                    hit("/a/frost/t.md", False, ("frost", "filebox/t.md")),
                    hit("/a/frost-wt/t.md", False, ("frost", "filebox/t.md")),
                ],
            )
        )
        == 1
    )
    assert (
        names(
            gr.merge(
                [hit("s0", True, ("r", "s0"), "sem")], [hit("c0", True, ("r", "c0"))]
            )
        )[0]
        == "s0"
    )
    # sem + fts of the same doc -> one line
    assert (
        len(
            gr.merge(
                [
                    hit(
                        "hyphae/repo:research:x",
                        True,
                        ("hyphae", "research/x.md"),
                        "sem",
                    )
                ],
                [hit("/w/.giantmem/research/x.md", True, ("hyphae", "research/x.md"))],
            )
        )
        == 1
    )

    # token budget: each line below is ~116 chars => 29 tokens
    def long_hit(key, cur):
        h = hit(key, cur, ("r" if cur else "x", key))
        h["snippet"] = "s" * 100
        return h

    gr.LIMIT, gr.CROSS_MAX, gr.BUDGET = 8, 1, 70
    cur5 = [long_hit(f"c{i}", True) for i in range(5)]
    oth2 = [long_hit(f"o{i}", False) for i in range(2)]
    # 29 reserved for the cross slot leaves room for exactly one current hit
    assert names(gr.merge([], cur5 + oth2)) == ["c0", "o0"]
    gr.BUDGET = 200
    # 171 for current: all five (5 x 29 = 145) fit, and the reserved cross slot still lands
    assert names(gr.merge([], cur5 + oth2)) == ["c0", "c1", "c2", "c3", "c4", "o0"]
    gr.BUDGET = 70
    # oversized top hit is skipped, next current hit still fits
    huge = long_hit("big", True)
    huge["snippet"] = "s" * 1000
    assert names(gr.merge([], [huge] + cur5 + oth2)) == ["c0", "o0"]
    assert all(gr.tokens(line) > 0 for line in gr.merge([], cur5))

    # document-frequency filter on query terms
    import sqlite3  # pylint: disable=import-outside-toplevel

    c = sqlite3.connect(":memory:")
    c.executescript(
        "create table live_docs(path text primary key, content text);"
        "create virtual table live_docs_fts using fts5(path, project, feature, dir_type, content);"
    )
    for i in range(10):
        text = "session giantmem" + (" posix" if i == 0 else "")
        c.execute(
            "insert into live_docs(path, content) values (?, ?)", (f"/p{i}", text)
        )
        c.execute(
            "insert into live_docs_fts(path, content) values (?, ?)", (f"/p{i}", text)
        )
    gr.MAX_DF = 0.2
    # survivors come back rarest first (hyphae df 0, posix df 1)
    assert gr.rare_terms(["session", "giantmem", "posix", "hyphae"], conn=c) == [
        "hyphae",
        "posix",
    ]
    # fewer than two survivors -> keep the original list
    assert gr.rare_terms(["session", "giantmem", "posix"], conn=c) == [
        "session",
        "giantmem",
        "posix",
    ]
    # short lists pass through untouched
    assert gr.rare_terms(["a", "b"], conn=c) == ["a", "b"]

    print("giantmem_recall checks ok")


if __name__ == "__main__":
    try:
        main()
    except AssertionError:
        print("giantmem_recall checks FAILED", file=sys.stderr)
        raise
