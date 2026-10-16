import ast
from pathlib import Path

# hooks also run under macOS /usr/bin/python3 (3.9), where `X | None` in a signature raises at import
HERE = Path(__file__).parent


def has_future_annotations(tree):
    return any(
        isinstance(n, ast.ImportFrom)
        and n.module == "__future__"
        and any(a.name == "annotations" for a in n.names)
        for n in tree.body
    )


def pep604_annotations(tree):
    for n in ast.walk(tree):
        anns = []
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)):
            anns = [n.returns] + [
                a.annotation
                for a in n.args.args + n.args.kwonlyargs + n.args.posonlyargs
            ]
        elif isinstance(n, ast.AnnAssign):
            anns = [n.annotation]
        for a in anns:
            if a is not None and any(
                isinstance(x, ast.BinOp) and isinstance(x.op, ast.BitOr)
                for x in ast.walk(a)
            ):
                yield n.lineno


bad = []
for p in sorted(HERE.glob("*.py")):
    if p.name.startswith("test_"):
        continue
    tree = ast.parse(p.read_text())
    if not has_future_annotations(tree):
        bad += [f"{p.name}:{line}" for line in pep604_annotations(tree)]
assert (
    not bad
), "X | Y annotations without `from __future__ import annotations`: " + ", ".join(bad)

print("ok")
