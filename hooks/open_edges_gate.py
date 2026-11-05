#!/usr/bin/env python3
"""Stop hook: block a final report once when its open-edges list still holds
work the session could do itself (CLAUDE.md `### Proactive execution` triage),
or a question parked in doit or a doc instead of asked (`### Strategy visibility`).

Reads the last assistant turn from the transcript, finds "Open edges" /
"Not done" / "Open questions" sections plus GATE/LIMIT/SEQUENCE items anywhere,
and matches item shapes that mean CLOSE, VERIFY, or ASK rather than GATE or
LIMIT. One block per stop: stop_hook_active skips the check.
"""

import importlib.util
import json
import os
import re
import sys
from pathlib import Path

BYPASS_ENV = "OPEN_EDGES_GATE"
MAX_SECTION_LINES = 60
MAX_QUOTE = 110

HEADER = re.compile(
    (
        r"^\W{0,6}(?:open edges?|not done(?: yet)?|still (?:open|not done)|not finished"
        r"|left undone|what(?:['’]s| is) not done|unfinished)\b[^\n]{0,60}$"
    ),
    re.IGNORECASE | re.MULTILINE,
)
QUESTION_HEADER = re.compile(
    (
        r"^(?![^\n]*\b(?:none|nothing)\b)\W{0,6}"
        r"(?:open (?:questions?|decisions?)|questions? for (?:you|me|the user)"
        r"|decisions? (?:for you|needed|pending|to make)|needs? your (?:call|input|decision))"
        r"\b[^\n]{0,60}$"
    ),
    re.IGNORECASE,
)
SECTION_END = re.compile(
    r"^(?:#{1,6}\s|\*\*[^*\n]{1,80}\*\*:?\s*$|\s{0,3}[A-Z][\w '’/-]{0,50}:\s*$"
    r"|\s{0,3}[A-Z][\w'’/-]*(?: [\w'’/()-]+){0,3}\s*$)"
)
ITEM_START = re.compile(r"^\s*(?:[-*+]|\d+[.)])\s+")
TAGGED_ITEM = re.compile(r"^\s*(?:[-*+]|\d+[.)])\s+\W{0,3}(?:GATE|LIMIT|SEQUENCE)\b")
CODE = re.compile(r"`[^`\n]*`|https?://\S+")
FENCE = re.compile(r"^\s*```.*?^\s*```", re.MULTILINE | re.DOTALL)
CLAUSE = re.compile(r"[.;]\s+|\n")
DEFERRED = re.compile(r"\bdeferred\b|\bdecide later\b", re.IGNORECASE)
SETTLED = re.compile(
    r"\b(?:deferred|decide later|resolved|answered|closed|removed)\b", re.IGNORECASE
)
PARKED_DECISION = (
    r"\bdecisions? (?:items?|mirror\w*)\b|\bmirror\w* (?:\S+ ){0,3}?decisions?\b"
    r"|\bnon-?blocking (?:\w+ )?(?:decisions?|questions?)\b|\[non-?blocking\]"
)
PARKED = re.compile(PARKED_DECISION, re.IGNORECASE)
QUESTION = re.compile(
    PARKED_DECISION
    + r"|\?(?=[\s)\]*_]|$)|\bopen questions?\b|\bnon-?blocking\b|\[blocking\]"
    r"|\b(?:until|unless) you (?:say(?! [\"“']?ship)|decide|pick|choose|answer)"
    r"|\b(?:needs?|awaits?|awaiting|waiting on|pending) (?:a |an |your )?"
    r"(?:decision|answer|call|input)\b|\byour call\b|\bwhether to\b"
    r"|\bsay [\"“'](?!ship)[^\"”'\n]{1,30}[\"”'] and\b",
    re.IGNORECASE,
)
# an owed twin, a stated expectation, or a dependency means the item is already a gate or sequenced
GATE_MARKER = re.compile(
    r"daily #\d+|\bexpect|\bto check:|\bon failure\b"
    r"|\bdep on\b|\bblocked (?:by|on)\b|\bwaits? (?:on|for)\b",
    re.IGNORECASE,
)
# shipping never waits on the user, so this beats GATE_MARKER's "waits for"
UNSHIPPED = re.compile(
    r"\b(?:until|unless|once|when|after) you say [\"“']?ship\b"
    r"|\bwaits? (?:on|for) (?:your |a )?[\"“']?ship it\b",
    re.IGNORECASE,
)

SHAPES = [
    (
        "UNVERIFIED",
        (
            r"\bI\s+(?:haven['’]t|have\s+not|didn['’]t|did\s+not|never)\s+(?:\w+\s+){0,2}?"
            r"(?:check|verif|test|tr(?:y|ied)|run|ran|call|open|look|confirm|measur|seen"
            r"|see\b|hit|exercis|replay|load|click|execut|watch)"
        ),
    ),
    (
        "UNVERIFIED",
        (
            r"\bnot[\s-]?(?:verified|tested|checked|measured|confirmed)\b"
            r"|\bun(?:verified|tested|measured|confirmed)\b"
        ),
    ),
    (
        "OFFER",
        (
            r"\b(?:say|tell\s+me|give\s+me)\s+[\"'“‘]?[^\"'”’\n]{1,30}[\"'”’]?\s+and\s+I"
            r"(?:['’]ll|\s+will)\b"
        ),
    ),
    (
        "OFFER",
        (
            r"\bI(?:['’]ll|\s+will)\s+(?:\w+\s+){0,6}?(?:if|when|once)\s+you\s+"
            r"(?:say|confirm|want|ok|approve|give|tell)"
        ),
    ),
    (
        "PREEXISTING",
        (
            r"\bpre-?existing\b|\bfails?\s+the\s+same\s+way\s+without\b|\bI\s+didn['’]t\s+touch\b"
            r"|\balready\s+fail(?:s|ed|ing)\s+(?:before|on\s+main|without)"
        ),
    ),
    (
        "PARKED",
        (
            r"\bqueued\s+for\s+/burn\b|\bI\s+didn['’]t\s+do\s+it\b|\bnow\s+unblocked\b"
            r"|\bleft\s+(?:it\s+)?for\s+(?:a\s+)?(?:later|another\s+session|a\s+follow-?up)\b"
        ),
    ),
    (
        "SCRATCH",
        (
            r"/private/tmp|\bscratch\s+clone\b|\blost\s+on\s+reboot\b"
            r"|\bdoesn['’]t\s+survive\s+a\s+reboot\b"
        ),
    ),
    (
        "GIT",
        (
            r"\b(?:still\s+)?not\s+(?:committed|pushed)\b|\bnothing\s+(?:told|asked)\s+me\s+to\s+"
            r"(?:commit|push)\b|\bneither\s+\w+\s+authorized\s+a\s+push\b|\bno\s+MR\b"
        ),
    ),
]
COMPILED = [(tag, re.compile(rx, re.IGNORECASE)) for tag, rx in SHAPES]


def last_assistant_text(transcript_path):
    texts = []
    try:
        with open(os.path.expanduser(transcript_path), encoding="utf-8") as fh:
            for line in fh:
                try:
                    entry = json.loads(line)
                except ValueError:
                    continue
                kind = entry.get("type")
                if kind == "user":
                    texts = []
                elif kind == "assistant":
                    content = entry.get("message", {}).get("content")
                    if isinstance(content, str):
                        texts.append(content)
                    elif isinstance(content, list):
                        texts.extend(
                            c.get("text", "")
                            for c in content
                            if isinstance(c, dict) and c.get("type") == "text"
                        )
    except OSError:
        return ""
    return "\n".join(t for t in texts if t)


def edge_items(text):
    items, cur = [], []
    kind = cur_kind = None
    taken = 0

    def flush():
        if cur:
            items.append((cur_kind, " ".join(cur)))
            cur.clear()

    for line in text.splitlines():
        header = None
        if QUESTION_HEADER.match(line):
            header = "deferred" if DEFERRED.search(line) else "questions"
        elif HEADER.match(line):
            header = "edges"
        if header or (kind and (SECTION_END.match(line) or taken >= MAX_SECTION_LINES)):
            flush()
            kind, cur_kind, taken = header, None, 0
            if header:
                continue
        taken += 1 if kind else 0
        stripped = line.strip()
        if ITEM_START.match(line):
            flush()
            cur_kind = kind or ("edges" if TAGGED_ITEM.match(line) else None)
        elif not stripped:
            if not kind:
                flush()
                cur_kind = None
            continue
        elif not cur and kind:
            cur_kind = kind
        if cur_kind:
            cur.append(stripped)
    flush()
    return items


def _quote(item):
    return item[:MAX_QUOTE] + ("…" if len(item) > MAX_QUOTE else "")


def _unasked(kind, item):
    if kind == "deferred" or DEFERRED.search(item):
        return False
    return kind == "questions" or bool(QUESTION.search(CODE.sub("", item)))


def parked_clauses(text):
    clauses = CLAUSE.split(FENCE.sub("", text))
    return [
        c.strip()
        for c in clauses
        if PARKED.search(CODE.sub("", c)) and not SETTLED.search(c)
    ]


def findings(text, ask=True):
    found = []
    for kind, item in edge_items(text):
        if ask and _unasked(kind, item):
            found.append(("UNASKED", _quote(item)))
            continue
        if UNSHIPPED.search(item):
            found.append(("SHIP", _quote(item)))
            continue
        if GATE_MARKER.search(item):
            continue
        for tag, rx in COMPILED:
            if rx.search(item):
                found.append((tag, _quote(item)))
                break
    if ask and not any(tag == "UNASKED" for tag, _ in found):
        found.extend(("UNASKED", _quote(c)) for c in parked_clauses(text))
    return found


def reason(found):
    tags = {tag for tag, _ in found}
    lines = [
        f"open_edges_gate: {len(found)} report item(s) need work before this report."
    ]
    if tags - {"UNASKED"}:
        lines.append(
            "CLOSE/VERIFY shapes are not gates (CLAUDE.md ### Proactive execution). For each: "
            "do it now (fix / run the check / commit+push / run ship-it / remove the hazard), or rewrite it as a "
            "GATE (only the user can: do / expect / on failure) or a LIMIT (a choice, named as one)."
        )
    if "UNASKED" in tags:
        lines.append(
            "UNASKED items park a question for the user in doit, a doc, or the report "
            "(CLAUDE.md ### Strategy visibility: ask, never park). Ask each now with "
            "AskUserQuestion: one question per call, recommended option first, `Decide later` "
            "last. Answered: record the answer in the doc body or code, close any `decision` "
            "item and Open Questions entry written for it, drop the line. `Decide later`: keep "
            "or write the Open Questions entry + `decision` item, list it as "
            "`deferred by you: <list> #N (<label>)`."
        )
    lines.append("Then send the report again.")
    lines.extend(f"  - [{tag}] {quote}" for tag, quote in found)
    return "\n".join(lines)


def auto_on(session_id):
    try:
        spec = importlib.util.spec_from_file_location(
            "auto_mode", Path(__file__).with_name("auto_mode.py")
        )
        assert spec and spec.loader
        auto = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(auto)
        return bool(auto.read_state(auto.state_path(session_id)))
    except (OSError, ImportError, SyntaxError, AttributeError, AssertionError):
        return False


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
    ask = not auto_on(data.get("session_id"))
    found = findings(last_assistant_text(path), ask=ask)
    if found:
        print(json.dumps({"decision": "block", "reason": reason(found)}))


if __name__ == "__main__":
    main()
