import json
import subprocess
import sys
from datetime import date, datetime, timezone
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))

import eod  # noqa: E402

TEST_CFG = {
    "name": "Pat Doe",
    "gitlab_user": "pat.doe",
    "email": "pat.doe@example.com",
    "self_user": "USELF",
    "self_dm": "DSELF",
    "manager": "Sam Lead",
    "manager_user": "UMGR",
    "manager_dm": "DMGR",
}

SENT = """About to wind down for the day. EOD Update from me:
*TL;DR* - auth multi-store MR is in review, remi streaming landed on stage. investigator v2 vercel app is next.
----------------
*Immediate Priorities*
• auth multi-store: MR up for review, should merge tomorrow after stage testing.
• remi streaming: merged the response streaming MRs, running on stage now. prod waits on the next release.
*Emerging Concerns*
• snowflake queries: there is a 20s cap on the analytics queries and a few runs hit it. _triaging, might need a bigger warehouse_
*On the horizon*
• investigator v2: second vercel app for the v2 agent, target end of next week.
*Exploration*
• eod status: ported a teammate's EOD drafter into my claude config, testing the daily draft."""

MINIMAL = "\n".join(SENT.splitlines()[:6])


@pytest.fixture(autouse=True)
def cfg(monkeypatch):
    monkeypatch.setattr(eod, "CFG", dict(TEST_CFG))


def utc(*args: int) -> datetime:
    return datetime(*args, tzinfo=timezone.utc)


@pytest.mark.parametrize(
    "now,days,expected",
    [
        (utc(2026, 10, 19, 19), 1, utc(2026, 10, 16, 19)),
        (utc(2026, 10, 20, 19), 1, utc(2026, 10, 19, 19)),
        (utc(2026, 10, 18, 19), 1, utc(2026, 10, 16, 19)),
        (utc(2026, 10, 19, 19), 3, utc(2026, 10, 16, 19)),
        (utc(2026, 10, 21, 19), 7, utc(2026, 10, 14, 19)),
    ],
)
def test_window_start_skips_weekends(now, days, expected):
    assert eod.window_start(now, days) == expected


def test_learn_start_reaches_back_to_last_run():
    since = utc(2026, 10, 20, 19)
    assert eod.learn_start(None, since) == since
    assert eod.learn_start(utc(2026, 10, 16, 19), since) == utc(2026, 10, 16, 19)
    assert eod.learn_start(utc(2026, 10, 21, 1), since) == since


def test_state_round_trip(tmp_path):
    path = tmp_path / "state.json"
    assert eod.load_last_run(path) is None
    at = utc(2026, 10, 5, 19)
    eod.save_last_run(at, path)
    assert eod.load_last_run(path) == at


def test_load_config_requires_every_key(tmp_path):
    path = tmp_path / "config.json"
    with pytest.raises(RuntimeError, match="missing"):
        eod.load_config(path)
    path.write_text(json.dumps({**TEST_CFG, "manager_dm": ""}))
    with pytest.raises(RuntimeError, match="manager_dm"):
        eod.load_config(path)
    path.write_text(json.dumps(TEST_CFG))
    assert eod.load_config(path) == TEST_CFG


def test_opener_and_rollup_rules():
    assert eod.opener(1) == eod.OPENER and eod.window_rules(1) == ""
    assert eod.opener(3) == "Rollup from me for the last 3 days:"
    assert "7-day rollup" in eod.window_rules(7)
    rollup = SENT.replace(eod.OPENER, eod.opener(3))
    assert eod.validate(rollup, eod.opener(3)) == []
    assert any("line 1" in e for e in eod.validate(rollup))


def activity_row(actor, app, at, tag, action="ship", result="shipped"):
    return {
        "action": action,
        "actor": actor,
        "application": app,
        "result": result,
        "createdAt": at,
        "detail": {"plan": {"tagName": tag}},
    }


def test_my_actions_keeps_only_mine_in_window():
    activity = [
        activity_row(
            "pat.doe@example.com", "customcheckout", "2026-10-21T15:00:00Z", "2.2.280"
        ),
        activity_row(
            "pat.doe@example.com", "customcheckout", "2026-10-19T15:00:00Z", "2.2.270"
        ),
        activity_row(
            "other@example.com", "customcheckout", "2026-10-21T16:00:00Z", "2.2.281"
        ),
        activity_row(
            "pat.doe@example.com",
            "release-central",
            "2026-10-21T17:00:00Z",
            None,
            "rollback",
            "rolled_back",
        ),
    ]
    rows = eod.my_actions(activity, utc(2026, 10, 20, 19))
    assert [(r["action"], r["tag"]) for r in rows] == [
        ("ship", "2.2.280"),
        ("rollback", None),
    ]
    assert rows[0]["at"] == "2026-10-21 11:00 ET"


def release(version, at, commits, rollout="stable"):
    return {
        "release": {
            "application": "customcheckout",
            "version": version,
            "deployedBy": "derek@example.com",
            "deployedAt": at,
            "current": True,
            "rollback": False,
        },
        "reports": {"risk": {"commits": commits}, "rollout": {"status": rollout}},
    }


def commit(author, mr, title="t", level="low"):
    return {"author": author, "mrUrl": mr, "title": title, "level": level}


def test_release_with_my_mrs_matches_author_or_url():
    detail = release(
        "2.2.280",
        "2026-10-21T19:18:06.015Z",
        [
            commit("Pat Doe", "https://gl/mr/1", "mine by name"),
            commit("Someone Else", "https://gl/mr/2", "mine by url"),
            commit("Someone Else", "https://gl/mr/3", "not mine"),
        ],
        rollout="unstable",
    )
    found = eod.release_with_my_mrs(detail, {"https://gl/mr/2"})
    assert found
    assert [m["title"] for m in found["my_mrs"]] == ["mine by name", "mine by url"]
    assert found["rollout_status"] == "unstable" and found["deployed_by"] == "derek"
    assert found["deployed_at"] == "2026-10-21 15:18 ET"
    assert (
        eod.release_with_my_mrs(release("1", "2026-10-21T19:00:00Z", []), set()) is None
    )


def test_release_central_stops_at_window_and_skips_others(monkeypatch):
    calls = []
    releases = {
        "2.2.281": release(
            "2.2.281", "2026-10-21T19:00:00Z", [commit("Pat Doe", "u1")]
        ),
        "2.2.280": release("2.2.280", "2026-10-21T15:00:00Z", [commit("Other", "u2")]),
    }

    def fake(tool, args):
        calls.append((tool, args.get("version")))
        if tool == "list_apps":
            return [{"application": "customcheckout"}]
        if tool == "list_releases":
            return [
                {"version": "2.2.281", "deployedAt": "2026-10-21T19:00:00Z"},
                {"version": "2.2.280", "deployedAt": "2026-10-21T15:00:00Z"},
                {"version": "2.2.270", "deployedAt": "2026-10-18T15:00:00Z"},
            ]
        if tool == "get_release":
            return releases[args["version"]]
        return []

    monkeypatch.setattr(eod, "call_release_central", fake)
    out = eod.release_central(utc(2026, 10, 20, 19), set())
    assert [r["version"] for r in out["releases_with_my_mrs"]] == ["2.2.281"]
    assert ("get_release", "2.2.270") not in calls and out["my_actions"] == []


def mr(ref, author, state="opened"):
    return {
        "references": {"full": ref},
        "state": state,
        "title": ref,
        "web_url": f"https://gl/{ref}",
        "author": {"username": author},
        "project_id": 1,
        "iid": 1,
    }


def test_my_reviews_skips_own_mrs_and_flags_approval(monkeypatch):
    monkeypatch.setattr(
        eod,
        "gitlab_mrs",
        lambda query, since: [
            mr("a!1", "pat.doe"),
            mr("b!2", "sam"),
            mr("c!3", "lee", "merged"),
        ],
    )
    monkeypatch.setattr(
        eod, "approvers", lambda m: ["pat.doe"] if m["title"] == "b!2" else []
    )
    rows = eod.my_reviews(utc(2026, 10, 20))
    assert [(r["ref"], r["approved"]) for r in rows] == [("b!2", True), ("c!3", False)]


def test_approvers_timeout_is_no_approvals(monkeypatch):
    def slow(cmd, **kwargs):
        raise subprocess.TimeoutExpired(cmd, kwargs["timeout"])

    monkeypatch.setattr(eod.subprocess, "run", slow)
    assert eod.approvers(mr("a!1", "sam")) == []


def test_my_mrs_reads_approvals_only_for_open(monkeypatch):
    monkeypatch.setattr(
        eod,
        "gitlab_mrs",
        lambda query, since: [mr("a!1", "pat.doe"), mr("a!2", "pat.doe", "merged")],
    )
    asked = []
    monkeypatch.setattr(eod, "approvers", lambda m: asked.append(m["title"]) or ["sam"])
    rows = eod.my_mrs(utc(2026, 10, 20))
    assert asked == ["a!1"] and [r["approved_by"] for r in rows] == [["sam"], []]


def test_github_prs_labels_role(monkeypatch):
    seen = []

    def fake_run(cmd, **kwargs):
        seen.append(cmd)
        prs = (
            []
            if "--reviewed-by=@me" in cmd
            else [
                {
                    "number": 4,
                    "title": "feat: x",
                    "url": "https://github.com/o/r/pull/4",
                    "state": "open",
                    "repository": {"nameWithOwner": "o/r"},
                    "isDraft": False,
                }
            ]
        )
        return subprocess.CompletedProcess(cmd, 0, json.dumps(prs), "")

    monkeypatch.setattr(eod.subprocess, "run", fake_run)
    rows = eod.github_prs(utc(2026, 10, 20, 19))
    assert rows == [
        {
            "role": "author",
            "ref": "o/r#4",
            "state": "open",
            "draft": False,
            "title": "feat: x",
            "url": "https://github.com/o/r/pull/4",
        }
    ]
    assert all("--updated=>=2026-10-20T19:00:00Z" in cmd for cmd in seen)


DAILY = """---
id: 2026-10-21
---

## CLAUDE SESSIONS

- 07:05 remi-gap · tmux remi:gap wt · `cd /x && claude --resume a` · [bundle](file:///b)
- 16:10 remi-gap · tmux remi:gap wt · `cd /x && claude --resume b`
- 16:20 auth-multi · tmux auth:1 · `cd /y && claude --resume c`

---

## CLAUDE LINKS

- 07:28 vault [[early-note]] · Recharge-Notes · s:1f632bc7
- 16:28 vault [[call-flow]] · Recharge-Notes · s:1f632bc7
- 16:29 artifact [Call Flow](https://claude.ai/artifact/abc) · Recharge-Notes · s:1f632bc7
- 16:30 handoff [handoff]({handoff}) · remi · s:1f632bc7
"""


def test_claude_activity_windows_and_excerpts(monkeypatch, tmp_path):
    vault = tmp_path / "vault"
    (vault / "daily").mkdir(parents=True)
    (vault / "areas/x").mkdir(parents=True)
    (vault / "areas/x/call-flow.md").write_text(
        "---\ntitle: t\n---\n# Call flow\n\nzendesk chat hits the orchestrator first.\n"
    )
    handoff = tmp_path / "handoff.md"
    handoff.write_text(
        "---\ntype: handoff\n---\n<!-- caveman:compressed -->\n## Start here\nstreaming fix is on stage.\n"
    )
    (vault / "daily/2026-10-21.md").write_text(DAILY.format(handoff=handoff))
    monkeypatch.setattr(eod, "VAULT", vault)
    since = datetime(2026, 10, 21, 15, tzinfo=eod.ET)
    text = eod.claude_activity(since, date(2026, 10, 21))
    assert text.startswith(
        "2026-10-21:\n- workstreams (session count): remi-gap x1, auth-multi x1"
    )
    assert "early-note" not in text
    assert (
        "16:28 vault [[call-flow]] · Recharge-Notes\n  excerpt: # Call flow zendesk chat hits the orchestrator first."
        in text
    )
    assert (
        "16:29 artifact [Call Flow](https://claude.ai/artifact/abc) · Recharge-Notes\n"
        in text
    )
    assert "excerpt: ## Start here streaming fix is on stage." in text
    assert "s:1f632bc7" not in text


def test_claude_activity_empty(monkeypatch, tmp_path):
    monkeypatch.setattr(eod, "VAULT", tmp_path)
    assert "no Claude activity" in eod.claude_activity(
        utc(2026, 10, 20), date(2026, 10, 21)
    )


def test_soft_turns_failures_into_a_marker():
    def boom():
        raise RuntimeError("gh not authed")

    assert eod.soft("github", boom) == "(github unavailable: gh not authed)"
    assert eod.soft("x", lambda: [1]) == [1]


def test_parse_mcp_response_sse():
    body = 'event: message\ndata: {"result":{"content":[{"type":"text","text":"[1,2]"}]}}\n\n'
    assert eod.parse_mcp_response(body) == [1, 2]


def test_parse_mcp_response_tool_error():
    body = json.dumps({"result": {"isError": True, "content": [{"text": "bad args"}]}})
    with pytest.raises(RuntimeError, match="bad args"):
        eod.parse_mcp_response(body)


def test_previous_draft_picks_latest_before_today(tmp_path):
    (tmp_path / "2026-10-01.md").write_text("old")
    (tmp_path / "2026-10-02.md").write_text("friday")
    (tmp_path / "2026-10-05.md").write_text("today")
    assert eod.previous_draft(date(2026, 10, 5), tmp_path) == "friday"
    assert eod.previous_draft(date(2026, 9, 1), tmp_path) == "(none)"


def test_prompt_template_fully_filled():
    template = eod.PROMPT_FILE.read_text()
    keys = set(__import__("re").findall(r"\{\{(\w+)\}\}", template))
    filled = eod.build_prompt(template, {k: "x" for k in keys})
    assert "{{" not in filled


def test_prompt_grounds_deploys_and_hides_private_links():
    template = eod.PROMPT_FILE.read_text()
    assert "Merged != deployed" in template and "releases_with_my_mrs" in template
    assert "Never report session counts" in template and "claude.ai links" in template
    assert "Josh" not in template and "Mike" not in template


def test_plain_dashes():
    assert eod.plain_dashes("review — cc !1, a–b") == "review - cc !1, a - b"


def test_sent_message_matches_template():
    assert eod.validate(SENT) == []
    assert eod.normalize(SENT) == SENT


def test_normalize_fixes_cosmetic_drift():
    drifted = SENT.replace("• ", "* ", 1).replace(
        "*Emerging Concerns*", "\n*Emerging Concerns*"
    )
    assert eod.normalize(drifted + " — x") == SENT + " - x"


@pytest.mark.parametrize(
    "mutate,error",
    [
        (lambda s: s.replace("About to wind down", "Hey, winding down"), "line 1"),
        (lambda s: s.replace("*TL;DR* - ", "TL;DR: "), "line 2"),
        (lambda s: s.replace("----------------", "---"), "line 3"),
        (lambda s: s.replace("*Exploration*", "*Little Stuff*"), "unknown sections"),
        (lambda s: s.replace("*Immediate Priorities*", "*Ignored*"), "required"),
        (
            lambda s: s.replace("*On the horizon*", "*Tmp*")
            .replace("*Emerging Concerns*", "*On the horizon*")
            .replace("*Tmp*", "*Emerging Concerns*"),
            "out of order",
        ),
        (lambda s: s.replace("• auth multi-store", "auth multi-store"), "line 5"),
        (lambda s: s + "\n*Emerging Concerns*", "out of order or repeated"),
        (lambda s: s.rsplit("\n", 1)[0], "has no bullets"),
    ],
)
def test_validate_rejects(mutate, error):
    errors = eod.validate(mutate(SENT))
    assert any(error in e for e in errors), errors


def test_every_section_required():
    errors = eod.validate(MINIMAL)
    assert errors == [f"*{name}* is required" for name in eod.SECTIONS[1:]]


def test_normalize_fills_missing_sections():
    filled = eod.normalize(MINIMAL)
    assert filled.endswith("\n".join(f"*{n}*\n{eod.EMPTY}" for n in eod.SECTIONS[1:]))
    assert eod.validate(filled) == []


def test_normalize_fills_middle_section_in_order():
    lines = SENT.splitlines()
    start, end = lines.index("*On the horizon*"), lines.index("*Exploration*")
    filled = eod.normalize("\n".join(lines[:start] + lines[end:]))
    assert f"*On the horizon*\n{eod.EMPTY}\n*Exploration*" in filled
    assert eod.validate(filled) == []


def test_normalize_canonicalizes_empty_bullet():
    assert (
        eod.normalize(MINIMAL + "\n*Emerging Concerns*\n- nothing new here.").count(
            eod.EMPTY
        )
        == 3
    )


def test_empty_mixed_with_bullets_rejected():
    mixed = SENT.replace("*Exploration*\n", f"*Exploration*\n{eod.EMPTY}\n")
    assert any("mixes" in e for e in eod.validate(mixed))


def test_evidence_ignores_empty_bullets():
    message = eod.normalize(MINIMAL)
    evidence = [{"bullet": "x", "source": "!1"}] * 2
    assert eod.evidence_errors({"message": message, "evidence": evidence}) == []


def test_evidence_must_cover_every_bullet():
    bullets = sum(line.startswith(eod.BULLET) for line in SENT.splitlines())
    full = [{"bullet": "x", "source": "cc!1"}] * bullets
    assert eod.evidence_errors({"message": SENT, "evidence": full}) == []
    assert eod.evidence_errors({"message": SENT, "evidence": full[:-1]})
    blank = full[:-1] + [{"bullet": "x", "source": " "}]
    assert eod.evidence_errors({"message": SENT, "evidence": blank})


def test_to_markdown():
    md = eod.to_markdown(SENT)
    assert md.startswith(
        "About to wind down for the day. EOD Update from me:\n\n**TL;DR** - "
    )
    assert (
        "\n\n" + "\\-" * 16 + "\n\n**Immediate Priorities**\n- auth multi-store" in md
    )
    assert "next release.\n\n**Emerging Concerns**\n- snowflake queries" in md
    assert "_triaging, might need a bigger warehouse_" in md


def test_tools_never_send():
    assert not any("send" in t or "schedule" in t for t in eod.compose_tools())
    assert all(t.endswith("slack_send_message") for t in eod.send_tools())


def test_result_entry_handles_object_and_stream():
    result = {"type": "result", "structured_output": {"ok": True}}
    assert eod.result_entry(result) is result
    assert (
        eod.result_entry([{"type": "system"}, {"type": "assistant"}, result]) is result
    )
    assert eod.result_entry([{"type": "system"}]) == {}


def test_claude_env_strips_session_markers(monkeypatch):
    monkeypatch.setenv("CLAUDECODE", "1")
    monkeypatch.setenv("CLAUDE_CODE_PLUGIN_DIRS", "/x")
    env = eod.claude_env()
    assert "CLAUDECODE" not in env and "CLAUDE_CODE_PLUGIN_DIRS" not in env
    assert env["ENABLE_CLAUDEAI_MCP_SERVERS"] == "false"


def test_prompt_forbids_repeating_previous_update():
    template = eod.PROMPT_FILE.read_text()
    assert "carry forward" not in template
    assert "DO NOT repeat" in template


def stub_sources(monkeypatch, tmp_path, prompts=None):
    def fake_compose(prompt, first_line=eod.OPENER):
        if prompts is not None:
            prompts.append(prompt)
        return {
            "message": SENT.replace(eod.OPENER, first_line),
            "asks_addressed": [],
            "evidence": [],
        }

    monkeypatch.setattr(eod, "compose", fake_compose)
    monkeypatch.setattr(eod, "load_config", lambda: dict(TEST_CFG))
    monkeypatch.setattr(eod, "call_release_central", lambda *a: [])
    monkeypatch.setattr(eod, "wait_for_network", lambda: True)
    monkeypatch.setattr(eod, "my_mrs", lambda since: [])
    monkeypatch.setattr(eod, "my_reviews", lambda since: [])
    monkeypatch.setattr(eod, "github_prs", lambda since: [])
    monkeypatch.setattr(eod, "claude_activity", lambda since, today: "(none)")
    monkeypatch.setattr(eod, "learn_rules", lambda since, dry: ("", []))
    monkeypatch.setattr(eod, "HOME", tmp_path)
    monkeypatch.setattr(eod, "DRAFTS_DIR", tmp_path / "drafts")
    monkeypatch.setattr(eod, "ROLLUPS_DIR", tmp_path / "rollups")
    monkeypatch.setattr(eod, "STATE_FILE", tmp_path / "state.json")


def test_sends_only_to_self(monkeypatch, tmp_path):
    stub_sources(monkeypatch, tmp_path)
    calls = []
    monkeypatch.setattr(
        eod,
        "run_claude",
        lambda prompt, *a, **k: calls.append(prompt)
        or {
            "sent": True,
            "channel_id": "DSELF",
            "message_link": "https://x/archives/DSELF/p1",
        },
    )
    monkeypatch.setattr(eod, "notify", lambda *a: calls.append(a))
    monkeypatch.setattr(sys, "argv", ["eod.py"])
    assert eod.main() == 0
    assert "USELF" in calls[0] and "DMGR" not in calls[0] and "UMGR" not in calls[0]
    assert "archives/DSELF/" in calls[1][2] and "Sam Lead" in calls[1][1]


def test_send_to_wrong_channel_raises(monkeypatch):
    monkeypatch.setattr(
        eod, "run_claude", lambda *a, **k: {"sent": True, "channel_id": "DMGR"}
    )
    with pytest.raises(RuntimeError, match="unexpected channel"):
        eod.send_to_self(SENT)


def test_rollup_writes_its_own_file_and_skips_previous_draft(monkeypatch, tmp_path):
    stub_sources(monkeypatch, tmp_path, prompts := [])
    (tmp_path / "drafts").mkdir()
    (tmp_path / "drafts/2026-01-01.md").write_text("older daily draft")
    monkeypatch.setattr(
        eod, "run_claude", lambda *a, **k: {"sent": True, "channel_id": "DSELF"}
    )
    monkeypatch.setattr(sys, "argv", ["eod.py", "--days", "3", "--no-notify"])
    assert eod.main() == 0
    (prompt,) = prompts
    assert (
        "{{" not in prompt
        and "3-day rollup" in prompt
        and "older daily draft" not in prompt
    )
    assert "Rollup from me for the last 3 days:" in prompt
    (rollup,) = (tmp_path / "rollups").iterdir()
    assert rollup.name.endswith("-3d.md") and rollup.read_text().startswith(
        "Rollup from me"
    )
    assert [p.name for p in (tmp_path / "drafts").iterdir()] == ["2026-01-01.md"]


def test_days_must_be_positive(monkeypatch):
    monkeypatch.setattr(sys, "argv", ["eod.py", "--days", "0"])
    with pytest.raises(SystemExit):
        eod.main()


def test_wait_for_network_retries_then_succeeds(monkeypatch):
    results = iter([False, False, True])
    monkeypatch.setattr(eod, "network_ok", lambda: next(results))
    monkeypatch.setattr(eod.time, "sleep", lambda s: None)
    assert eod.wait_for_network(attempts=4, delay=0) is True


def test_wait_for_network_gives_up(monkeypatch):
    calls = []
    monkeypatch.setattr(eod, "network_ok", lambda: calls.append(1) or False)
    monkeypatch.setattr(eod.time, "sleep", lambda s: None)
    assert eod.wait_for_network(attempts=3, delay=0) is False
    assert len(calls) == 3


def test_vpn_down_notifies_retry_and_skips_claude(monkeypatch):
    notes = []
    monkeypatch.setattr(eod, "wait_for_network", lambda: False)
    monkeypatch.setattr(eod, "notify", lambda *a, **k: notes.append((a, k)))
    monkeypatch.setattr(
        eod, "run_claude", lambda *a, **k: pytest.fail("claude should not run")
    )
    monkeypatch.setattr(sys, "argv", ["eod.py"])
    assert eod.main() == 1
    ((args, kwargs),) = notes
    assert "VPN" in args[0] and str(eod.RUN_SCRIPT) in kwargs["execute"]


def test_dry_run_keeps_real_draft(monkeypatch, tmp_path):
    stub_sources(monkeypatch, tmp_path)
    (tmp_path / "drafts").mkdir()
    monkeypatch.setattr(
        eod, "run_claude", lambda *a, **k: pytest.fail("dry run must not send")
    )
    monkeypatch.setattr(sys, "argv", ["eod.py", "--dry-run", "--no-notify"])
    assert eod.main() == 0
    assert (tmp_path / "dry-run.md").read_text().strip() == SENT
    assert (
        list((tmp_path / "drafts").iterdir()) == []
        and not (tmp_path / "state.json").exists()
    )
