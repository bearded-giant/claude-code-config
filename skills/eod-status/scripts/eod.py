import argparse
import importlib.util
import itertools
import json
import logging
import os
import re
import subprocess
import sys
import time
from collections import Counter
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import learn

ET = ZoneInfo("America/New_York")
HOME = Path(os.environ.get("EOD_STATUS_HOME", Path.home() / ".config/eod-status"))
CONFIG_FILE = HOME / "config.json"
STATE_FILE = HOME / "state.json"
DRAFTS_DIR = HOME / "drafts"
ROLLUPS_DIR = HOME / "rollups"
LESSONS_FILE = HOME / "lessons.md"
PROPOSALS_FILE = HOME / "proposals.json"
VAULT = Path(os.environ.get("OBSIDIAN_VAULT", "~/Recharge-Notes")).expanduser()
SCRIPT_DIR = Path(__file__).parent
REPO = Path(__file__).resolve().parents[3]
VOICE_FILE = REPO / "config/voice.md"
PROMPT_FILE = SCRIPT_DIR / "prompt.md"
RUN_SCRIPT = SCRIPT_DIR / "run.sh"
NETWORK_ATTEMPTS = 4
NETWORK_RETRY_SECONDS = 180

RELEASE_CENTRAL_MCP = "https://ai-tooling.infra.rechargeapps.net/release-central/mcp"
CONFIG_KEYS = [
    "name",
    "gitlab_user",
    "email",
    "self_user",
    "self_dm",
    "manager",
    "manager_user",
    "manager_dm",
]
CFG: dict[str, str] = {}

SLACK_READ_TOOLS = [
    "slack_read_channel",
    "slack_read_thread",
    "slack_search_public_and_private",
    "slack_read_user_profile",
    "slack_search_users",
]
SLACK_PREFIXES = ["mcp__claude_ai_Slack__", "mcp__plugin_slack_slack__"]

OPENER = "About to wind down for the day. EOD Update from me:"
TLDR_PREFIX = "*TL;DR* - "
DIVIDER = "----------------"
SECTIONS = [
    "Immediate Priorities",
    "Emerging Concerns",
    "On the horizon",
    "Exploration",
]
BULLET = "\u2022 "
EMPTY = BULLET + "nothing new here"
STATUS_WORDS = re.compile(r"\b(deployed|merged|closed|handled)\b", re.IGNORECASE)
SESSION_LINE = re.compile(r"^- (\d\d:\d\d) (\S+)")
LINK_LINE = re.compile(r"^- (\d\d:\d\d) (.*?)(?: · s:\w+)?$")
VAULT_LINK = re.compile(r"\[\[([^\]|]+)")
FILE_LINK = re.compile(r"\]\((/[^)]+\.md)\)")

COMPOSE_SCHEMA = {
    "type": "object",
    "properties": {
        "message": {"type": "string"},
        "asks_addressed": {"type": "array", "items": {"type": "string"}},
        "evidence": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "bullet": {"type": "string"},
                    "source": {"type": "string"},
                },
                "required": ["bullet", "source"],
            },
        },
    },
    "required": ["message", "asks_addressed", "evidence"],
}
SEND_SCHEMA = {
    "type": "object",
    "properties": {
        "sent": {"type": "boolean"},
        "channel_id": {"type": "string"},
        "message_link": {"type": "string"},
        "error": {"type": "string"},
    },
    "required": ["sent"],
}

logger = logging.getLogger("eod-status")


def load_voice_gate():
    spec = importlib.util.spec_from_file_location(
        "voice_gate", REPO / "hooks/voice_gate.py"
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


voice_gate = load_voice_gate()


def load_config(path: Path | None = None) -> dict[str, str]:
    path = path or CONFIG_FILE
    try:
        cfg = json.loads(path.read_text())
    except FileNotFoundError:
        raise RuntimeError(f"missing {path}; keys: {', '.join(CONFIG_KEYS)}") from None
    missing = [k for k in CONFIG_KEYS if not cfg.get(k)]
    if missing:
        raise RuntimeError(f"{path} is missing {', '.join(missing)}")
    if {cfg["self_dm"], cfg["self_user"]} & {cfg["manager_dm"], cfg["manager_user"]}:
        raise RuntimeError(f"{path}: self ids must differ from the manager's")
    return cfg


def load_last_run(path: Path | None = None) -> datetime | None:
    try:
        return datetime.fromisoformat(
            json.loads((path or STATE_FILE).read_text())["last_run"]
        )
    except (FileNotFoundError, KeyError, ValueError):
        return None


def save_last_run(at: datetime, path: Path | None = None) -> None:
    path = path or STATE_FILE
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"last_run": at.isoformat()}))


def window_start(now: datetime, days: int) -> datetime:
    start = now - timedelta(days=days)
    while start.astimezone(ET).weekday() >= 5:
        start -= timedelta(days=1)
    return start


def learn_start(last_run: datetime | None, since: datetime) -> datetime:
    # a skipped day must not drop `eod:` notes or sent updates from learning
    return min(last_run, since) if last_run else since


def opener(days: int) -> str:
    if days == 1:
        return CFG.get("opener") or OPENER
    return f"Rollup from me for the last {days} days:"


def window_rules(days: int) -> str:
    if days == 1:
        return ""
    return (
        f"This is a {days}-day rollup, not a daily update. Roll each topic up to its outcome "
        "over the whole window (what shipped, what is in review, what is blocked) instead of "
        "day-by-day activity. At most 4 bullets per section; drop small one-off items. "
        "Restating items from earlier daily updates is expected when they matter to the outcome."
    )


def parse_ts(value: str) -> datetime:
    return datetime.fromisoformat(value)


def parse_mcp_response(body: str) -> Any:
    payload = next(
        (
            line[len("data: ") :]
            for line in body.splitlines()
            if line.startswith("data: ")
        ),
        body,
    )
    reply = json.loads(payload)
    if "error" in reply:
        raise RuntimeError(f"release-central MCP error: {reply['error']}")
    result = reply["result"]
    if result.get("isError"):
        raise RuntimeError(
            f"release-central tool error: {result['content'][0]['text']}"
        )
    return json.loads(result["content"][0]["text"])


def call_release_central(tool: str, arguments: dict) -> Any:
    # python's TLS handshake to the VPN host fails where curl succeeds
    body = json.dumps(
        {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/call",
            "params": {"name": tool, "arguments": arguments},
        }
    )
    out = subprocess.run(
        [
            "curl",
            "-sS",
            "--fail",
            "-m",
            "30",
            "-X",
            "POST",
            RELEASE_CENTRAL_MCP,
            "-H",
            "content-type: application/json",
            "-H",
            "accept: application/json, text/event-stream",
            "-d",
            body,
        ],
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )
    if out.returncode != 0:
        raise RuntimeError(f"release-central unreachable (VPN?): {out.stderr.strip()}")
    return parse_mcp_response(out.stdout)


def my_actions(activity: list[dict], since: datetime) -> list[dict]:
    return [
        {
            "at": f"{parse_ts(row['createdAt']).astimezone(ET):%Y-%m-%d %H:%M} ET",
            "action": row.get("action"),
            "app": row.get("application"),
            "result": row.get("result"),
            "tag": ((row.get("detail") or {}).get("plan") or {}).get("tagName"),
        }
        for row in activity
        if row.get("actor") == CFG["email"] and parse_ts(row["createdAt"]) >= since
    ]


def release_with_my_mrs(detail: dict, my_mr_urls: set[str]) -> dict | None:
    reports = detail.get("reports") or {}
    commits = (reports.get("risk") or {}).get("commits") or []
    mine = [
        {"title": c.get("title"), "mr": c.get("mrUrl"), "risk": c.get("level")}
        for c in commits
        if c.get("author") == CFG["name"] or c.get("mrUrl") in my_mr_urls
    ]
    if not mine:
        return None
    release = detail["release"]
    return {
        "app": release["application"],
        "version": release["version"],
        "deployed_at": f"{parse_ts(release['deployedAt']).astimezone(ET):%Y-%m-%d %H:%M} ET",
        "deployed_by": (release.get("deployedBy") or "?").split("@")[0],
        "current": release.get("current"),
        "rollback": release.get("rollback"),
        "rollout_status": (reports.get("rollout") or {}).get("status"),
        "my_mrs": mine,
    }


def release_central(since: datetime, my_mr_urls: set[str]) -> dict:
    releases = []
    for app in call_release_central("list_apps", {}):
        name = app["application"]
        for row in call_release_central("list_releases", {"app": name, "limit": 100}):
            if parse_ts(row["deployedAt"]) < since:
                break
            detail = call_release_central(
                "get_release", {"app": name, "version": row["version"]}
            )
            found = release_with_my_mrs(detail, my_mr_urls)
            if found:
                releases.append(found)
    activity = call_release_central("recent_activity", {"limit": 100})
    return {"releases_with_my_mrs": releases, "my_actions": my_actions(activity, since)}


def approvers(mr: dict) -> list[str]:
    try:
        out = subprocess.run(
            [
                "glab",
                "api",
                f"projects/{mr['project_id']}/merge_requests/{mr['iid']}/approvals",
            ],
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
    except subprocess.TimeoutExpired:
        return []
    if out.returncode != 0:
        return []
    return [
        a["user"]["username"] for a in json.loads(out.stdout).get("approved_by", [])
    ]


def gitlab_mrs(query: str, since: datetime) -> list[dict]:
    out = subprocess.run(
        [
            "glab",
            "api",
            f"merge_requests?{query}&scope=all&per_page=100"
            f"&updated_after={since.astimezone(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')}",
        ],
        capture_output=True,
        text=True,
        timeout=60,
        check=True,
    )
    return json.loads(out.stdout)


def my_mrs(since: datetime) -> list[dict]:
    return [
        {
            "ref": mr["references"]["full"],
            "state": mr["state"],
            "draft": mr.get("draft", False),
            "title": mr["title"],
            "url": mr["web_url"],
            "merged_at": mr.get("merged_at"),
            "detailed_merge_status": mr.get("detailed_merge_status"),
            "approved_by": approvers(mr) if mr["state"] == "opened" else [],
        }
        for mr in gitlab_mrs(f"author_username={CFG['gitlab_user']}", since)
    ]


def my_reviews(since: datetime) -> list[dict]:
    return [
        {
            "ref": mr["references"]["full"],
            "state": mr["state"],
            "title": mr["title"],
            "author": mr["author"]["username"],
            "approved": CFG["gitlab_user"] in approvers(mr),
        }
        for mr in gitlab_mrs(f"reviewer_username={CFG['gitlab_user']}", since)
        if mr["author"]["username"] != CFG["gitlab_user"]
    ]


def github_prs(since: datetime) -> list[dict]:
    after = since.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    rows = []
    for role, flag in (("author", "--author=@me"), ("reviewer", "--reviewed-by=@me")):
        out = subprocess.run(
            [
                "gh",
                "search",
                "prs",
                flag,
                f"--updated=>={after}",
                "--json",
                "number,title,url,state,repository,isDraft",
                "--limit",
                "50",
            ],
            capture_output=True,
            text=True,
            timeout=60,
            check=True,
        )
        rows += [
            {
                "role": role,
                "ref": f"{pr['repository']['nameWithOwner']}#{pr['number']}",
                "state": pr["state"],
                "draft": pr["isDraft"],
                "title": pr["title"],
                "url": pr["url"],
            }
            for pr in json.loads(out.stdout)
        ]
    return rows


def section(text: str, heading: str) -> list[str]:
    lines = text.split("\n")
    if heading not in lines:
        return []
    out = []
    for line in lines[lines.index(heading) + 1 :]:
        if line.strip() == "---" or line.startswith("## "):
            break
        if line.strip():
            out.append(line)
    return out


def excerpt(path: Path | None, limit: int = 400) -> str:
    if not path or not path.is_file():
        return ""
    body = re.sub(
        r"\A---\n.*?\n---\n", "", path.read_text(errors="replace"), flags=re.S
    )
    body = re.sub(r"<!--.*?-->", "", body, flags=re.S)
    return " ".join(body.split())[:limit]


def linked_doc(link: str) -> Path | None:
    if match := FILE_LINK.search(link):
        return Path(match.group(1))
    if match := VAULT_LINK.search(link):
        return next(VAULT.rglob(f"{match.group(1)}.md"), None)
    return None


def claude_day(text: str, day: date, since: datetime) -> list[str]:
    def in_window(hhmm: str) -> bool:
        at = datetime.combine(day, datetime.strptime(hhmm, "%H:%M").time(), tzinfo=ET)
        return at >= since

    sessions = Counter(
        m.group(2)
        for line in section(text, "## CLAUDE SESSIONS")
        if (m := SESSION_LINE.match(line)) and in_window(m.group(1))
    )
    out = []
    if sessions:
        out.append(
            "- workstreams (session count): "
            + ", ".join(f"{label} x{n}" for label, n in sessions.most_common())
        )
    for line in section(text, "## CLAUDE LINKS"):
        m = LINK_LINE.match(line)
        if not m or not in_window(m.group(1)):
            continue
        entry = f"- {m.group(1)} {m.group(2)}"
        if not m.group(2).startswith("artifact") and (
            snippet := excerpt(linked_doc(m.group(2)))
        ):
            entry += f"\n  excerpt: {snippet}"
        out.append(entry)
    return out


def claude_activity(since: datetime, today: date) -> str:
    blocks = []
    day = since.astimezone(ET).date()
    while day <= today:
        path = VAULT / "daily" / f"{day.isoformat()}.md"
        if path.exists() and (lines := claude_day(path.read_text(), day, since)):
            blocks.append(f"{day.isoformat()}:\n" + "\n".join(lines))
        day += timedelta(days=1)
    return "\n".join(blocks) or "(no Claude activity in the daily notes)"


def soft(label: str, fetch, *args) -> Any:
    try:
        return fetch(*args)
    except Exception as exc:
        logger.warning("%s unavailable: %s", label, exc)
        return f"({label} unavailable: {str(exc)[:200]})"


def as_json(value: object) -> str:
    return value if isinstance(value, str) else json.dumps(value, indent=1)


def previous_draft(today: date, drafts_dir: Path = DRAFTS_DIR) -> str:
    earlier = sorted(p for p in drafts_dir.glob("*.md") if p.stem < today.isoformat())
    return earlier[-1].read_text() if earlier else "(none)"


def plain_dashes(text: str) -> str:
    return re.sub(r"\s*[\u2014\u2013]\s*", " - ", text)


def normalize(text: str) -> str:
    lines = [line.rstrip() for line in plain_dashes(text).strip().splitlines()]
    bulleted = [
        re.sub(r"^\s*[-*\u2022]\s+", BULLET, line) for line in lines if line.strip()
    ]
    return "\n".join(fill_sections([empty_bullet(line) for line in bulleted]))


def empty_bullet(line: str) -> str:
    return (
        EMPTY
        if re.fullmatch(r"\u2022 nothing new here\.?", line, re.IGNORECASE)
        else line
    )


def fill_sections(lines: list[str]) -> list[str]:
    out = list(lines)
    for i, name in enumerate(SECTIONS):
        if f"*{name}*" in out:
            continue
        later = [out.index(f"*{s}*") for s in SECTIONS[i + 1 :] if f"*{s}*" in out]
        pos = min(later) if later else len(out)
        out[pos:pos] = [f"*{name}*", EMPTY]
    return out


def validate(text: str, first_line: str = OPENER) -> list[str]:
    lines = text.splitlines()
    errors = []
    if lines[:1] != [first_line]:
        errors.append(f"line 1 must be exactly: {first_line}")
    if len(lines) < 2 or not lines[1].startswith(TLDR_PREFIX):
        errors.append(f"line 2 must start with: {TLDR_PREFIX}")
    if lines[2:3] != [DIVIDER]:
        errors.append(f"line 3 must be exactly: {DIVIDER}")
    headers = [line[1:-1] for line in lines[3:] if re.fullmatch(r"\*[^*]+\*", line)]
    unknown = [h for h in headers if h not in SECTIONS]
    if unknown:
        errors.append(f"unknown sections {unknown}; allowed: {SECTIONS}")
    known = [h for h in headers if h in SECTIONS]
    if known != sorted(known, key=SECTIONS.index) or len(set(known)) != len(known):
        errors.append(f"sections out of order or repeated; order: {SECTIONS}")
    errors += [f"*{name}* is required" for name in SECTIONS if name not in headers]
    if len(lines) > 3 and not re.fullmatch(r"\*[^*]+\*", lines[3]):
        errors.append("line 4 must be a section header")
    for i, line in enumerate(lines[3:], start=4):
        is_header = re.fullmatch(r"\*[^*]+\*", line)
        if not is_header and not line.startswith(BULLET):
            errors.append(f"line {i} must be a *Header* or a bullet: {line[:60]}")
        if is_header and (i >= len(lines) or not lines[i].startswith(BULLET)):
            errors.append(f"section {line} has no bullets")
        if is_header:
            body = list(itertools.takewhile(lambda b: b.startswith(BULLET), lines[i:]))
            if EMPTY in body and len(body) > 1:
                errors.append(f"section {line} mixes '{EMPTY[2:]}' with real bullets")
    return errors


def to_markdown(text: str) -> str:
    # blank lines keep slack blocks from merging
    blocks: list[str] = []
    for line in text.splitlines():
        if re.fullmatch(r"\*[^*]+\*", line):
            blocks.append(f"*{line}*")
        elif line.startswith(TLDR_PREFIX):
            blocks.append("**TL;DR** - " + line[len(TLDR_PREFIX) :])
        elif line == DIVIDER:
            blocks.append("\\-" * len(DIVIDER))
        elif line.startswith(BULLET) and blocks and blocks[-1].startswith(("**", "- ")):
            blocks[-1] += "\n- " + line[len(BULLET) :]
        elif line.startswith(BULLET):
            blocks.append("- " + line[len(BULLET) :])
        else:
            blocks.append(line)
    return "\n\n".join(blocks)


def build_prompt(template: str, values: dict[str, str]) -> str:
    return re.sub(r"\{\{(\w+)\}\}", lambda m: values[m.group(1)], template)


def compose_tools() -> list[str]:
    return [prefix + name for prefix in SLACK_PREFIXES for name in SLACK_READ_TOOLS]


def send_tools() -> list[str]:
    return [prefix + "slack_send_message" for prefix in SLACK_PREFIXES]


def claude_env() -> dict[str, str]:
    # nested runs from inside a Claude session must not inherit its plugin dirs or session markers
    drop = {"CLAUDE_CODE_PLUGIN_DIRS", "CLAUDECODE", "CLAUDE_CODE_ENTRYPOINT"}
    env = {k: v for k, v in os.environ.items() if k not in drop}
    env["ENABLE_CLAUDEAI_MCP_SERVERS"] = "false"
    return env


def result_entry(out: dict | list) -> dict:
    # with verbose on, --output-format json emits the whole message stream
    if isinstance(out, dict):
        return out
    return next((m for m in reversed(out) if m.get("type") == "result"), {})


def run_claude(
    prompt: str, schema: dict, tools: list[str], model: str | None = None
) -> dict:
    cmd = [
        "claude",
        "-p",
        "--setting-sources",
        "project",
        "--no-session-persistence",
        "--output-format",
        "json",
        "--json-schema",
        json.dumps(schema),
        *(["--model", model] if model else []),
        "--allowedTools",
        *tools,
        "--disallowedTools",
        "Bash",
        "Edit",
        "Write",
        "WebFetch",
        "WebSearch",
        *(
            prefix + name
            for prefix in SLACK_PREFIXES
            for name in (
                "slack_send_message",
                "slack_schedule_message",
                "slack_send_message_draft",
            )
            if prefix + name not in tools
        ),
    ]
    # cwd holds the .claude/settings.json that enables the slack plugin
    proc = subprocess.run(
        cmd,
        input=prompt,
        capture_output=True,
        text=True,
        timeout=1200,
        env=claude_env(),
        cwd=SCRIPT_DIR,
        check=False,
    )
    if proc.returncode != 0:
        raise RuntimeError(
            f"claude exited {proc.returncode}: {proc.stderr[-500:] or proc.stdout[-500:]}"
        )
    out = result_entry(json.loads(proc.stdout))
    if out.get("is_error") or not out.get("structured_output"):
        raise RuntimeError(
            f"claude returned no output: {out.get('subtype')} {str(out.get('result'))[:300]}"
        )
    logger.info("claude cost $%.2f", out.get("total_cost_usd") or 0)
    return out["structured_output"]


def evidence_errors(result: dict) -> list[str]:
    bullets = sum(
        line.startswith(BULLET) and line != EMPTY
        for line in result["message"].splitlines()
    )
    sources = [e for e in result.get("evidence", []) if e.get("source", "").strip()]
    if bullets != len(sources):
        return [
            f"{bullets} bullets but {len(sources)} evidence entries; cite one source per bullet or drop it"
        ]
    return []


def voice_text(path: Path = VOICE_FILE) -> str:
    return path.read_text().split("\n## Bypass")[0].strip()


def voice_errors(message: str) -> list[str]:
    errors = []
    for line in message.splitlines():
        if line.startswith(TLDR_PREFIX):
            text = line[len(TLDR_PREFIX) :]
        elif line.startswith(BULLET) and line != EMPTY:
            text = line[len(BULLET) :]
        else:
            continue
        found = voice_gate.violations(text, "slack")
        if words := sorted({w.lower() for w in STATUS_WORDS.findall(text)}):
            found.append(
                f"status words ({', '.join(words)}): say what the work does and what it "
                "waits on, never its lifecycle"
            )
        errors += [f"'{text[:40]}': {v}" for v in found]
    return errors


def draft(prompt: str) -> dict:
    result = run_claude(prompt, COMPOSE_SCHEMA, compose_tools())
    result["message"] = normalize(result["message"])
    return result


def draft_errors(result: dict, first_line: str) -> tuple[list[str], list[str]]:
    hard = validate(result["message"], first_line) + evidence_errors(result)
    return hard, voice_errors(result["message"])


def compose(prompt: str, first_line: str = OPENER) -> dict:
    result = draft(prompt)
    hard, voice = draft_errors(result, first_line)
    if hard or voice:
        logger.warning("draft violations, retrying: %s", hard + voice)
        fix = (
            f"{prompt}\n\n## Your previous attempt broke the template or the voice rules\n"
            + "\n".join(f"- {e}" for e in hard + voice)
            + f"\n\nPrevious attempt:\n```\n{result['message']}\n```\n"
            + "Redo the full gather (read Slack again) and rewrite, fixing these issues "
            + "without dropping any supported content."
        )
        result = draft(fix)
        hard, voice = draft_errors(result, first_line)
        if hard:
            raise RuntimeError(f"draft breaks template: {'; '.join(hard)}")
    # the draft is edited by hand before it goes anywhere, so voice drift warns instead of failing
    result["voice_warnings"] = voice
    return result


def send_to_self(message: str) -> dict:
    # slack drafts strip formatting, so a real self-DM is the draft
    prompt = (
        f"Call slack_send_message exactly once with channel_id {CFG['self_user']} (my own DM, "
        "nobody else) and this exact message, byte for byte, no edits:\n<message>\n"
        f"{to_markdown(message)}\n</message>\n"
        "Return sent, the returned channel_id and message_link; on error sent=false with error."
    )
    result = run_claude(prompt, SEND_SCHEMA, send_tools(), model="haiku")
    if result.get("sent") and result.get("channel_id") != CFG["self_dm"]:
        raise RuntimeError(
            f"status sent to unexpected channel {result.get('channel_id')}"
        )
    return result


def notify(
    title: str, message: str, open_target: str | None = None, execute: str | None = None
) -> None:
    proc = subprocess.run(
        [
            "terminal-notifier",
            "-title",
            title,
            "-message",
            message,
            *(["-open", open_target] if open_target else []),
            *(["-execute", execute] if execute else []),
            "-group",
            "eod-status",
            "-sound",
            "Glass",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    if proc.returncode != 0:
        logger.warning("terminal-notifier failed: %s", proc.stderr.strip())
        subprocess.run(
            [
                "osascript",
                "-e",
                f"display notification {json.dumps(message)} with title {json.dumps(title)}",
            ],
            check=False,
        )


def network_ok() -> bool:
    # twingate can report connected while passing nothing
    out = subprocess.run(
        [
            "curl",
            "-s",
            "-o",
            "/dev/null",
            "-m",
            "10",
            "https://gitlab.rechargeapps.net/api/v4/version",
        ],
        capture_output=True,
        check=False,
    )
    return out.returncode == 0


def wait_for_network(
    attempts: int = NETWORK_ATTEMPTS, delay: int = NETWORK_RETRY_SECONDS
) -> bool:
    for attempt in range(1, attempts + 1):
        if network_ok():
            return True
        logger.warning("VPN hosts unreachable (attempt %d/%d)", attempt, attempts)
        if attempt < attempts:
            time.sleep(delay)
    return False


def learn_rules(since: datetime, dry_run: bool) -> tuple[str, list[dict]]:
    lessons = LESSONS_FILE.read_text() if LESSONS_FILE.exists() else ""
    proposals = learn.load_proposals(PROPOSALS_FILE)
    gathered = run_claude(
        learn.gather_prompt(
            CFG["self_dm"],
            CFG["manager_dm"],
            CFG["self_user"],
            opener(1),
            int(since.timestamp()),
        ),
        learn.GATHER_SCHEMA,
        compose_tools(),
        model="haiku",
    )
    lessons, proposals = learn.apply_notes(gathered["notes"], lessons, proposals)
    proposals, new = learn.learn_from_sent(
        gathered["sent"], proposals, lessons, DRAFTS_DIR, run_claude
    )
    if not dry_run:
        LESSONS_FILE.parent.mkdir(parents=True, exist_ok=True)
        LESSONS_FILE.write_text(lessons)
        learn.save_proposals(PROPOSALS_FILE, proposals)
    return lessons, new


def main() -> int:
    parser = argparse.ArgumentParser(description="Draft the status DM to my manager.")
    parser.add_argument(
        "--dry-run", action="store_true", help="no Slack draft, no state update"
    )
    parser.add_argument("--no-notify", action="store_true")
    parser.add_argument(
        "--days",
        type=int,
        default=1,
        help="window in days; >1 writes a rollup (default 1)",
    )
    args = parser.parse_args()
    if args.days < 1:
        parser.error("--days must be at least 1")

    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s"
    )
    now = datetime.now(timezone.utc)
    today = now.astimezone(ET).date()
    since = window_start(now, args.days)
    if args.days == 1:
        draft_path = DRAFTS_DIR / f"{today.isoformat()}.md"
    else:
        draft_path = ROLLUPS_DIR / f"{today.isoformat()}-{args.days}d.md"

    if not wait_for_network():
        logger.error("VPN hosts unreachable after retries; giving up")
        if not args.no_notify:
            notify(
                "EOD status FAILED: VPN down",
                "GitLab/release-central unreachable. Reconnect Twingate, then click to retry.",
                execute=f"{RUN_SCRIPT} >/dev/null 2>&1 &",
            )
        return 1

    try:
        CFG.update(load_config())
        first_line = opener(args.days)
        mrs = my_mrs(since)
        releases = soft(
            "release central", release_central, since, {mr["url"] for mr in mrs}
        )
        try:
            lessons, new_rules = learn_rules(
                learn_start(load_last_run(), since), args.dry_run
            )
        except Exception:
            logger.exception("learning step failed; using saved rules")
            lessons = LESSONS_FILE.read_text() if LESSONS_FILE.exists() else ""
            new_rules = []
        prompt = build_prompt(
            PROMPT_FILE.read_text(),
            {
                "name": CFG["name"],
                "manager": CFG["manager"],
                "manager_user": CFG["manager_user"],
                "manager_dm": CFG["manager_dm"],
                "self_user": CFG["self_user"],
                "self_dm": CFG["self_dm"],
                "today": f"{today:%A %Y-%m-%d}",
                "window": "last day" if args.days == 1 else f"last {args.days} days",
                "window_rules": window_rules(args.days),
                "opener": first_line,
                "since": since.astimezone(ET).strftime("%Y-%m-%d %H:%M ET"),
                "since_epoch": str(int(since.timestamp())),
                "since_date": (
                    since.astimezone(ET).date() - timedelta(days=1)
                ).isoformat(),
                "lessons": lessons.strip() or "(none yet)",
                "mrs": json.dumps(mrs, indent=1),
                "reviews": as_json(soft("gitlab reviews", my_reviews, since)),
                "github": as_json(soft("github", github_prs, since)),
                "releases": as_json(releases),
                "claude": soft("claude activity", claude_activity, since, today),
                "voice": voice_text(),
                "previous_draft": (
                    previous_draft(today)
                    if args.days == 1
                    else "(not provided: a rollup restates daily items by design)"
                ),
            },
        )
        result = compose(prompt, first_line)
    except Exception as exc:
        logger.exception("run failed")
        if not args.no_notify:
            notify(
                "EOD status FAILED",
                f"{str(exc)[:150]} (click to retry)",
                execute=f"{RUN_SCRIPT} >/dev/null 2>&1 &",
            )
        return 1

    if args.dry_run:
        draft_path = HOME / "dry-run.md"
    draft_path.parent.mkdir(parents=True, exist_ok=True)
    draft_path.write_text(result["message"] + "\n")
    print(result["message"])
    logger.info("asks addressed: %s", result["asks_addressed"])
    for warning in result.get("voice_warnings", []):
        logger.warning("voice: %s", warning)
    for item in result["evidence"]:
        logger.info("evidence: %s <- %s", item["bullet"], item["source"])
    if args.dry_run:
        return 0

    try:
        sent = send_to_self(result["message"])
    except Exception as exc:
        logger.exception("slack send failed")
        sent = {"sent": False, "error": str(exc)[:200]}
    logger.info("slack send: %s %s", sent.get("sent"), sent.get("error", ""))
    if new_rules:
        try:
            send_to_self(learn.proposal_message(new_rules))
        except Exception:
            logger.exception("rule suggestions send failed")
    save_last_run(now)
    if not args.no_notify:
        if sent.get("sent"):
            notify(
                "EOD status ready",
                f"Sent to your self-DM. Click to review, copy to {CFG['manager']}."
                + (f" +{len(new_rules)} rule suggestions." if new_rules else ""),
                sent.get("message_link")
                or f"https://grid-recharge.enterprise.slack.com/archives/{CFG['self_dm']}",
            )
        else:
            notify(
                "EOD status: Slack send failed",
                "Click to open local draft.",
                draft_path.as_uri(),
            )
    return 0


if __name__ == "__main__":
    sys.exit(main())
