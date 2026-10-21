import difflib
import json
import re
from datetime import datetime
from pathlib import Path
from typing import Callable
from zoneinfo import ZoneInfo

ET = ZoneInfo("America/New_York")
NOTE_PREFIX = re.compile(r"^\s*eod:\s*", re.IGNORECASE)
COMMAND = re.compile(r"^(accept|reject)\s+((?:p\d+[\s,]*)+)$", re.IGNORECASE)
FOOTER = re.compile(r"^\*?sent using\*?\s+claude\s*$", re.IGNORECASE)
SAME_ENOUGH = 0.97

Claude = Callable[..., dict]

GATHER_SCHEMA = {
    "type": "object",
    "properties": {
        "notes": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "ts": {"type": "string"},
                    "text": {"type": "string"},
                    "link": {"type": "string"},
                },
                "required": ["ts", "text"],
            },
        },
        "sent": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {"ts": {"type": "string"}, "text": {"type": "string"}},
                "required": ["ts", "text"],
            },
        },
    },
    "required": ["notes", "sent"],
}
PROPOSE_SCHEMA = {
    "type": "object",
    "properties": {"rules": {"type": "array", "items": {"type": "string"}}},
    "required": ["rules"],
}


def note_body(text: str) -> str | None:
    match = NOTE_PREFIX.match(text)
    if not match:
        return None
    return text[match.end() :].strip() or None


def parse_command(body: str) -> tuple[str, list[str]] | None:
    match = COMMAND.match(body.strip())
    if not match:
        return None
    ids = [i.upper() for i in re.findall(r"p\d+", match.group(2), re.IGNORECASE)]
    return match.group(1).lower(), ids


def load_proposals(path: Path) -> dict:
    try:
        return json.loads(path.read_text())
    except (FileNotFoundError, ValueError):
        return {"next_id": 1, "pending": [], "seen": []}


def save_proposals(path: Path, proposals: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(proposals, indent=1))


def add_lesson(lessons: str, day: str, rule: str, source: str) -> str:
    rule = " ".join(rule.split())
    existing = {
        line.split(" | ")[1].casefold()
        for line in lessons.splitlines()
        if line.count(" | ") >= 2
    }
    if rule.casefold() in existing:
        return lessons
    line = f"- {day} | {rule} | {source}"
    return f"{lessons.rstrip()}\n{line}\n".lstrip("\n")


def ts_day(ts: str) -> str:
    return datetime.fromtimestamp(float(ts), ET).date().isoformat()


def apply_notes(notes: list[dict], lessons: str, proposals: dict) -> tuple[str, dict]:
    seen = set(proposals["seen"])
    pending = {p["id"]: p for p in proposals["pending"]}
    for note in sorted(notes, key=lambda n: float(n["ts"])):
        body = note_body(note["text"])
        if note["ts"] in seen or not body:
            continue
        seen.add(note["ts"])
        command = parse_command(body)
        if command:
            verb, ids = command
            for pid in ids:
                proposal = pending.pop(pid, None)
                if proposal and verb == "accept":
                    lessons = add_lesson(
                        lessons,
                        ts_day(note["ts"]),
                        proposal["rule"],
                        proposal["source"],
                    )
            continue
        lessons = add_lesson(
            lessons, ts_day(note["ts"]), body, note.get("link") or f"ts {note['ts']}"
        )
    return lessons, {
        **proposals,
        "pending": list(pending.values()),
        "seen": sorted(seen),
    }


def comparable(text: str) -> list[str]:
    lines = []
    for raw in text.splitlines():
        line = re.sub(r"^\s*(?:[-*]|•)\s+", "", raw.strip())
        line = re.sub(r"<([^|>]+)(?:\|[^>]*)?>", r"\1", line)
        line = re.sub(r"[*_\\]", "", line).strip()
        if line and not FOOTER.match(raw.strip()) and not re.fullmatch(r"-+", line):
            lines.append(line)
    return lines


def similarity(draft: str, sent: str) -> float:
    return difflib.SequenceMatcher(None, comparable(draft), comparable(sent)).ratio()


def draft_for(ts: str, drafts_dir: Path) -> Path | None:
    # a send matches the draft from its own ET day, else the latest before it
    day = ts_day(ts)
    candidates = sorted(p for p in drafts_dir.glob("*.md") if p.stem <= day)
    return candidates[-1] if candidates else None


def propose_prompt(draft: str, sent: str, lessons: str) -> str:
    return (
        "The author edits an auto-drafted EOD status before sending it to a manager. Compare the draft "
        "with what he actually sent and infer at most 3 standing rules that would make future "
        "drafts need fewer edits (tone, length, what to include or leave out, ordering, wording "
        "habits). Only rules that generalize; ignore one-off fact corrections. Skip anything "
        "already covered by the existing rules. Each rule is one imperative sentence. Return an "
        f"empty list if nothing generalizes.\n\nExisting rules:\n{lessons or '(none)'}\n\n"
        f"DRAFT:\n```\n{draft}\n```\n\nSENT:\n```\n{sent}\n```"
    )


def learn_from_sent(
    sent: list[dict], proposals: dict, lessons: str, drafts_dir: Path, claude: Claude
) -> tuple[dict, list[dict]]:
    seen = set(proposals["seen"])
    pending = list(proposals["pending"])
    next_id = proposals["next_id"]
    new: list[dict] = []
    for item in sorted(sent, key=lambda s: float(s["ts"])):
        if item["ts"] in seen:
            continue
        seen.add(item["ts"])
        draft_path = draft_for(item["ts"], drafts_dir)
        if not draft_path:
            continue
        draft = draft_path.read_text()
        if similarity(draft, item["text"]) >= SAME_ENOUGH:
            continue
        rules = claude(
            propose_prompt(draft, item["text"], lessons), PROPOSE_SCHEMA, []
        )["rules"]
        for rule in rules[:3]:
            proposal = {
                "id": f"P{next_id}",
                "rule": " ".join(rule.split()),
                "source": f"edits to {draft_path.stem} draft",
            }
            next_id += 1
            new.append(proposal)
    updated = {"next_id": next_id, "pending": pending + new, "seen": sorted(seen)}
    return updated, new


def proposal_message(new: list[dict]) -> str:
    lines = [
        f"EOD rule suggestions from your edits. Reply `eod: accept {new[0]['id']}` (or reject) to keep one:"
    ]
    lines += [f"• {p['id']}: {p['rule']}" for p in new]
    return "\n".join(lines)


def gather_prompt(
    self_dm: str, manager_dm: str, self_user: str, opener: str, oldest: int
) -> str:
    return (
        f"Read only, send nothing.\n"
        f"1. Read Slack channel {self_dm} (the author's DM to self) with oldest={oldest}. For every "
        "message that has thread replies, read the thread too. Return `notes`: each message or "
        "reply whose text starts with `eod:` (case-insensitive), with its ts, its text exactly as "
        "written (keep the `eod:` prefix), and its permalink if you have it.\n"
        f"2. Read Slack channel {manager_dm} with oldest={oldest}. Return `sent`: each message by user "
        f"{self_user} whose text starts with `{opener}`, with its ts and full text exactly as written.\n"
        "Return empty lists when nothing matches."
    )
