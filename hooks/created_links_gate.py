#!/usr/bin/env python3
import json
import os
import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path

BYPASS_ENV = "CREATED_LINKS_GATE"
STATE_DIR = Path("/tmp/claude-created-links")
TAIL_LINES = 12

MR_CREATE_CMD = re.compile(r"\bglab\s+mr\s+create\b|\bgh\s+pr\s+create\b")
MR_CREATE_OUT = re.compile(r"Creating (?:merge|pull) request for")
MR_URL = re.compile(
    r"https://[^\s\"'<>)\]]+?/-/merge_requests/\d+"
    r"|https://github\.com/[^/\s\"'<>]+/[^/\s\"'<>]+/pull/\d+"
)
CHRONOCTL = re.compile(r"\bchronoctl\b[^\n|;&]*")
CHRONO_DASH = re.compile(r"https://[a-z0-9-]+\.chronosphere\.io/dashboards/[\w-]+")
DASHBOARD_TOOL = re.compile(
    r"(splunk|chronosphere|newrelic)_(?:create|put|update)_dashboard$"
)
ANY_URL = re.compile(r"https://[^\s\"'<>)\]}]+")
NOT_A_PROMPT = (
    "<task-notification",
    "<teammate-message",
    "Another Claude session sent a message",
    "<local-command-stdout",
    "<bash-input",
    "<bash-stdout",
)


def interactive():
    # claude -p sets sdk-cli even when its parent session is cli
    return not os.environ.get("CLAUDE_CODE_ENTRYPOINT", "cli").startswith("sdk")


def is_prompt(rec):
    if rec.get("type") != "user" or rec.get("isMeta"):
        return False
    content = (rec.get("message") or {}).get("content")
    if isinstance(content, list):
        if any(isinstance(b, dict) and b.get("type") == "tool_result" for b in content):
            return False
        content = result_text(content)
    return isinstance(content, str) and not content.lstrip().startswith(NOT_A_PROMPT)


def result_text(content):
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "\n".join(
            b.get("text", "")
            for b in content
            if isinstance(b, dict) and b.get("type") == "text"
        )
    return ""


def json_urls(obj):
    if isinstance(obj, dict):
        for key, val in obj.items():
            if key == "url" and isinstance(val, str) and val.startswith("http"):
                yield val
            else:
                yield from json_urls(val)
    elif isinstance(obj, list):
        for val in obj:
            yield from json_urls(val)


def result_urls(text):
    try:
        found = list(dict.fromkeys(json_urls(json.loads(text))))
    except ValueError:
        found = []
    if found:
        return found
    m = ANY_URL.search(text)
    return [m.group(0)] if m else []


def mr_label(url):
    m = re.search(r"/([^/]+)/-/merge_requests/(\d+)$", url) or re.search(
        r"/([^/]+)/pull/(\d+)$", url
    )
    if not m:
        return url
    return f"{m.group(1)}{'#' if '/pull/' in url else '!'}{m.group(2)}"


def chronoctl_writes(cmd):
    return any(
        re.search(r"\b(?:apply|create)\b", seg)
        and not re.search(r"--dry-run|--help|\s-h\b", seg)
        for seg in CHRONOCTL.findall(cmd)
    )


def chrono_links(text):
    return [("chronosphere dashboard", u) for u in CHRONO_DASH.findall(text)]


def classify(name, inp, text):
    if name == "Bash":
        cmd = inp.get("command", "") if isinstance(inp, dict) else ""
        if MR_CREATE_CMD.search(cmd) or MR_CREATE_OUT.search(text):
            urls = list(dict.fromkeys(MR_URL.findall(text)))
            return [(mr_label(u), u) for u in urls], not urls
        return [], False
    m = DASHBOARD_TOOL.search(name)
    if m:
        return [(f"{m.group(1)} dashboard", u) for u in result_urls(text)], False
    return [], False


def records_of(path):
    try:
        with open(path, encoding="utf-8") as fh:
            for line in fh:
                try:
                    rec = json.loads(line)
                except ValueError:
                    continue
                if isinstance(rec, dict):
                    yield rec
    except OSError:
        return


def read_turn(path):
    seen_before, records, start = set(), [], ""
    for rec in records_of(path):
        if is_prompt(rec):
            seen_before.update(
                r.get("prUrl") for r in records if r.get("type") == "pr-link"
            )
            records, start = [], rec.get("timestamp") or ""
        records.append(rec)
    return seen_before, records, start


def scan_records(records, seen_before):
    uses, created, final = {}, [], []
    needs_link = armed = False
    for rec in records:
        kind = rec.get("type")
        content = (rec.get("message") or {}).get("content")
        if kind == "assistant":
            if isinstance(content, str):
                content = [{"type": "text", "text": content}]
            for b in content if isinstance(content, list) else []:
                if not isinstance(b, dict):
                    continue
                if b.get("type") == "tool_use":
                    uses[b.get("id")] = (b.get("name") or "", b.get("input") or {})
                    if armed:
                        created.extend(chrono_links(json.dumps(b.get("input"))))
                elif b.get("type") == "text":
                    final.append(b.get("text", ""))
                    if armed:
                        created.extend(chrono_links(b.get("text", "")))
        elif kind == "user":
            final = []
            for b in content if isinstance(content, list) else []:
                if (
                    not isinstance(b, dict)
                    or b.get("type") != "tool_result"
                    or b.get("is_error")
                ):
                    continue
                name, inp = uses.get(b.get("tool_use_id"), ("", {}))
                text = result_text(b.get("content"))
                # chronoctl prints no URL, so the dashboard link shows up later in the agent's own text
                if name == "Bash" and isinstance(inp, dict):
                    armed = armed or chronoctl_writes(inp.get("command", ""))
                if armed:
                    created.extend(chrono_links(text))
                found, wants_link = classify(name, inp, text)
                created.extend(found)
                needs_link = needs_link or wants_link
    # pr-link alone fires on MRs merely viewed, so it only fills in a create whose output hid the URL
    if needs_link:
        created.extend(
            (mr_label(r["prUrl"]), r["prUrl"])
            for r in records
            if r.get("type") == "pr-link"
            and r.get("prUrl")
            and r["prUrl"] not in seen_before
        )
    return created, "\n".join(t for t in final if t)


def epoch(ts):
    try:
        return datetime.fromisoformat(ts.replace("Z", "+00:00")).timestamp()
    except ValueError:
        return 0.0


def subagent_records(path, start):
    since = epoch(start) if start else 0.0
    for sub in sorted((Path(path).with_suffix("") / "subagents").glob("agent-*.jsonl")):
        try:
            if sub.stat().st_mtime < since:
                continue
        except OSError:
            continue
        yield [r for r in records_of(sub) if (r.get("timestamp") or "") >= start]


def scan(path):
    path = os.path.expanduser(path)
    seen_before, records, start = read_turn(path)
    created, final = scan_records(records, seen_before)
    for sub in subagent_records(path, start):
        created.extend(scan_records(sub, set())[0])
    uniq = {}
    for label, url in created:
        uniq.setdefault(url, label)
    return [(label, url) for url, label in uniq.items()], final


def open_url(url):
    if sys.platform == "darwin":
        subprocess.Popen(  # pylint: disable=consider-using-with
            ["open", url],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )


def state_path(session_id):
    return STATE_DIR / f"{re.sub(r'[^A-Za-z0-9_-]', '', session_id) or 'global'}.json"


def load_state(path):
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        data = {}
    return {k: set(data.get(k) or []) for k in ("opened", "delivered")}


def save_state(path, state):
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps({k: sorted(v) for k, v in state.items()}), encoding="utf-8"
    )


def in_tail(url, final):
    tail = "\n".join([ln for ln in final.splitlines() if ln.strip()][-TAIL_LINES:])
    return re.search(re.escape(url) + r"(?![\w-])", tail) is not None


def reason(missing):
    where = " (opened in the browser)" if sys.platform == "darwin" else ""
    lines = "\n".join(f"  {label} {url}" for label, url in missing)
    return (
        f"created_links_gate: this turn created these links{where}:\n{lines}\n"
        "End with them as the last lines of a short final message, one per line exactly "
        "as listed, after all other output. Do not repeat the report."
    )


def main():
    try:
        data = json.load(sys.stdin) or {}
    except ValueError:
        return
    if os.environ.get(BYPASS_ENV, "").lower() == "off" or not interactive():
        return
    path = data.get("transcript_path")
    if not path:
        return
    created, final = scan(path)
    if not created:
        return
    spath = state_path(data.get("session_id") or "global")
    state = load_state(spath)
    for _, url in created:
        if url not in state["opened"]:
            open_url(url)
            state["opened"].add(url)
    state["delivered"].update(url for _, url in created if in_tail(url, final))
    save_state(spath, state)
    missing = [(label, url) for label, url in created if url not in state["delivered"]]
    # one block per stop, so a model that cannot comply never loops
    if missing and not data.get("stop_hook_active"):
        print(json.dumps({"decision": "block", "reason": reason(missing)}))


if __name__ == "__main__":
    main()
