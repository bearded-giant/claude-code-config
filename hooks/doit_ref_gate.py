#!/usr/bin/env python3
import importlib.util
import json
import os
import re
import sys
from pathlib import Path

BYPASS_ENV = "DOIT_REF_GATE"
MAX_QUOTE = 110
FENCE = re.compile(r"^\s*```.*?^\s*```", re.MULTILINE | re.DOTALL)
REF = re.compile(
    r"(?:\b([a-z0-9][\w.-]*)\s+)?(?<![\w#/&!])#(\d+[a-z]*)\b`?", re.IGNORECASE
)
LABELED = re.compile(r"\s*\(")
DEP_CONTEXT = re.compile(
    r"\bdeps?:?(?: on)?\s*(?:#\d+[a-z]*,?\s*(?:and\s+)?)*$", re.IGNORECASE
)
NOT_DOIT = re.compile(
    r"\b(?:PRs?|MRs?|issues?|pull requests?|tickets?|text|image)\b[^.\n]{0,12}$",
    re.IGNORECASE,
)
WORD = re.compile(r"[a-z0-9][\w-]{3,}")


def load(name):
    spec = importlib.util.spec_from_file_location(
        name, Path(__file__).with_name(f"{name}.py")
    )
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def labels(p, auto, name, cache):
    if name not in cache:
        cache[name] = {}
        for t in p.load_todos(os.path.join(p.LISTS_DIR, f"{name}.json")) or []:
            text = t.get("text", "") if isinstance(t, dict) else ""
            rank = auto.RANK.match(text)
            if rank:
                cache[name][rank.group(1)] = auto.DEPS.sub(
                    "", text[rank.end() :]
                ).strip()
    return cache[name]


def list_for(word, names):
    if not word:
        return ""
    w = word.lower()
    if w in names:
        return w
    alias = [n for n in names if n.endswith("-" + w)]
    if len(alias) == 1:
        return alias[0]
    # a hyphenated name that is no list is a repo or other namespace, so its numbers are not doit items
    return None if "-" in w else ""


def mentions(line, label):
    words = WORD.findall(label.lower())[:4]
    low = line.lower()
    return bool(words) and sum(w in low for w in words) >= min(2, len(words))


def findings(text, p, auto, session_list):
    try:
        names = {f[:-5] for f in os.listdir(p.LISTS_DIR) if f.endswith(".json")}
    except OSError:
        return []
    cache, found, seen = {}, [], set()
    for line in FENCE.sub("", text).splitlines():
        current = session_list
        for m in REF.finditer(line):
            named = list_for(m.group(1), names)
            if named != "":
                current = named
            before = line[max(0, m.start(2) - 41) : m.start(2) - 1]
            if current is None or DEP_CONTEXT.search(before) or NOT_DOIT.search(before):
                continue
            n = m.group(2)
            label = labels(p, auto, current, cache).get(n)
            if label is None or LABELED.match(line, m.end()) or mentions(line, label):
                continue
            if (current, n) not in seen:
                seen.add((current, n))
                quote = line.strip()[:MAX_QUOTE] + (
                    "…" if len(line.strip()) > MAX_QUOTE else ""
                )
                found.append((f"{current} #{n} ({label})", quote))
    return found


def reason(found):
    lines = [
        (
            f"doit_ref_gate: {len(found)} doit ref(s) give a number with no label; the "
            "user does not know items by number (CLAUDE.md ### Format). Rewrite each as "
            "`<list> #N (<label>)` and say what acting on it means, then send the report "
            "again. A ref that is not a doit item: reword it so it does not read as one."
        )
    ]
    lines.extend(f'  - {ref} in: "{quote}"' for ref, quote in found)
    return "\n".join(lines)


def main():
    try:
        data = json.load(sys.stdin) or {}
    except ValueError:
        return
    if data.get("stop_hook_active") or os.environ.get(BYPASS_ENV, "").lower() == "off":
        return
    path = data.get("transcript_path")
    if not path:
        return
    p, auto = load("doit_session_prime"), load("auto_mode")
    cwd = os.environ.get("CLAUDE_PROJECT_DIR") or data.get("cwd") or os.getcwd()
    root = p.git_root(cwd)
    text = load("open_edges_gate").last_assistant_text(path)
    found = findings(text, p, auto, p.list_name(root, p.active_feature(root)))
    if found:
        print(json.dumps({"decision": "block", "reason": reason(found)}))


if __name__ == "__main__":
    main()
