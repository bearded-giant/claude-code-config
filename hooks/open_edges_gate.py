#!/usr/bin/env python3
"""Stop hook: block a final report once when its open-edges list still holds
work the session could do itself (CLAUDE.md `### Proactive execution` triage).

Reads the last assistant turn from the transcript, finds an "Open edges" /
"Not done" section, and matches item shapes that mean CLOSE or VERIFY rather
than GATE or LIMIT. One block per stop: stop_hook_active skips the check.
"""

import json
import os
import re
import sys

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
SECTION_END = re.compile(r"^(?:#{1,6}\s|\*\*[^*\n]{1,80}\*\*:?\s*$)")
ITEM_START = re.compile(r"^\s*(?:[-*+]|\d+[.)])\s+")
# an owed twin, a stated expectation, or a dependency means the item is already a gate or sequenced
GATE_MARKER = re.compile(
    r"daily #\d+|\bexpect|\bto check:|\bon failure\b"
    r"|\bdep on\b|\bblocked (?:by|on)\b|\bwaits? (?:on|for)\b",
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


def edge_sections(text):
    lines = text.splitlines()
    sections = []
    i = 0
    while i < len(lines):
        if HEADER.match(lines[i]):
            body = []
            j = i + 1
            while j < len(lines) and len(body) < MAX_SECTION_LINES:
                if SECTION_END.match(lines[j]) or HEADER.match(lines[j]):
                    break
                body.append(lines[j])
                j += 1
            sections.append("\n".join([lines[i]] + body))
            i = j
        else:
            i += 1
    return sections


def _items(section):
    items, cur = [], []
    for line in section.splitlines()[1:]:
        if ITEM_START.match(line) and cur:
            items.append(" ".join(cur))
            cur = []
        if line.strip():
            cur.append(line.strip())
    if cur:
        items.append(" ".join(cur))
    return items


def findings(text):
    found = []
    for section in edge_sections(text):
        for item in _items(section):
            if GATE_MARKER.search(item):
                continue
            for tag, rx in COMPILED:
                if rx.search(item):
                    quote = item[:MAX_QUOTE] + ("…" if len(item) > MAX_QUOTE else "")
                    found.append((tag, quote))
                    break
    return found


def reason(found):
    lines = [
        (
            f"open_edges_gate: {len(found)} open-edge item(s) are CLOSE or VERIFY shapes, "
            "not gates (CLAUDE.md ### Proactive execution). For each: do it now "
            "(fix / run the check / commit+push / remove the hazard), or rewrite it as a GATE "
            "(only the user can: do / expect / on failure) or a LIMIT (a choice, named as one). "
            "Then send the report again."
        )
    ]
    lines.extend(f"  - [{tag}] {quote}" for tag, quote in found)
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
    found = findings(last_assistant_text(path))
    if found:
        print(json.dumps({"decision": "block", "reason": reason(found)}))


if __name__ == "__main__":
    main()
