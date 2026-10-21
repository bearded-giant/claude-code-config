import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))

import eod  # noqa: E402
import learn  # noqa: E402
from test_eod import SENT, TEST_CFG  # noqa: E402

JAMES_NOTE = (
    "eod: on the horizon needs to include a note as to what James is working on. "
    "We want to start bringing visibility to it."
)
TS_OCT15 = str(datetime(2026, 10, 15, 14, tzinfo=timezone.utc).timestamp())
TS_OCT15_LATER = str(datetime(2026, 10, 15, 15, tzinfo=timezone.utc).timestamp())


@pytest.fixture(autouse=True)
def cfg(monkeypatch):
    monkeypatch.setattr(eod, "CFG", dict(TEST_CFG))


def empty() -> dict:
    return {"next_id": 1, "pending": [], "seen": []}


@pytest.mark.parametrize(
    "text,body",
    [
        ("eod: drop the deploy count", "drop the deploy count"),
        ("  EOD:   keep it short", "keep it short"),
        ("eod:", None),
        ("Updates notes:\n- something", None),
        (eod.OPENER + "\n*TL;DR* - x", None),
        ("reminder: eod: buy milk", None),
    ],
)
def test_note_body_requires_prefix(text, body):
    assert learn.note_body(text) == body


def test_apply_notes_adds_rule_once():
    note = {"ts": TS_OCT15, "text": JAMES_NOTE, "link": "https://slack/p1"}
    lessons, proposals = learn.apply_notes([note], "", empty())
    assert lessons == (
        "- 2026-10-15 | on the horizon needs to include a note as to what James is working on. "
        "We want to start bringing visibility to it. | https://slack/p1\n"
    )
    again, _ = learn.apply_notes([note], lessons, proposals)
    assert again == lessons
    repeat = {**note, "ts": TS_OCT15_LATER}
    assert learn.apply_notes([repeat], lessons, proposals)[0] == lessons


def test_apply_notes_ignores_non_notes():
    notes = [
        {"ts": TS_OCT15, "text": "lunch at noon"},
        {"ts": TS_OCT15_LATER, "text": SENT},
    ]
    lessons, proposals = learn.apply_notes(notes, "", empty())
    assert lessons == "" and proposals["seen"] == []


def test_accept_and_reject_pending_proposals():
    proposals = {
        "next_id": 3,
        "pending": [
            {
                "id": "P1",
                "rule": "Keep TL;DR to one sentence.",
                "source": "edits to 2026-10-14 draft",
            },
            {
                "id": "P2",
                "rule": "Never mention Kai.",
                "source": "edits to 2026-10-14 draft",
            },
        ],
        "seen": [],
    }
    notes = [
        {"ts": TS_OCT15, "text": "eod: accept p1"},
        {"ts": TS_OCT15_LATER, "text": "eod: reject P2"},
    ]
    lessons, updated = learn.apply_notes(notes, "", proposals)
    assert (
        lessons
        == "- 2026-10-15 | Keep TL;DR to one sentence. | edits to 2026-10-14 draft\n"
    )
    assert updated["pending"] == []


def test_similarity_ignores_slack_formatting():
    markdown = eod.to_markdown(SENT) + "\n\n*Sent using* Claude"
    assert learn.similarity(SENT, markdown) == 1.0
    edited = SENT.replace("investigator v2 vercel app is next.", "")
    edited = "\n".join(line for line in edited.splitlines() if "eod status" not in line)
    assert learn.similarity(SENT, edited) < learn.SAME_ENOUGH


def test_draft_for_matches_send_day(tmp_path):
    (tmp_path / "2026-10-14.md").write_text("a")
    (tmp_path / "2026-10-16.md").write_text("b")
    assert learn.draft_for(TS_OCT15, tmp_path).stem == "2026-10-14"
    assert (
        learn.draft_for(
            str(datetime(2026, 10, 1, tzinfo=timezone.utc).timestamp()), tmp_path
        )
        is None
    )


def test_learn_from_sent_proposes_only_for_real_edits(tmp_path):
    (tmp_path / "2026-10-15.md").write_text(SENT + "\n")
    prompts = []

    def claude(prompt, schema, tools):
        prompts.append(prompt)
        return {
            "rules": [
                "Keep TL;DR to one sentence.",
                "Drop exploration filler.",
                "x",
                "y",
            ]
        }

    unchanged = {"ts": TS_OCT15, "text": eod.to_markdown(SENT)}
    proposals, new = learn.learn_from_sent([unchanged], empty(), "", tmp_path, claude)
    assert new == [] and prompts == [] and proposals["seen"] == [TS_OCT15]

    edited = {"ts": TS_OCT15_LATER, "text": "\n".join(SENT.splitlines()[:6])}
    proposals, new = learn.learn_from_sent(
        [edited], proposals, "- old rule", tmp_path, claude
    )
    assert [p["id"] for p in new] == ["P1", "P2", "P3"]
    assert proposals["next_id"] == 4 and len(proposals["pending"]) == 3
    assert (
        "- old rule" in prompts[0] and "DRAFT:" in prompts[0] and "SENT:" in prompts[0]
    )
    assert learn.learn_from_sent([edited], proposals, "", tmp_path, claude)[1] == []


def test_proposal_message_explains_how_to_accept():
    msg = learn.proposal_message(
        [{"id": "P4", "rule": "Keep it short.", "source": "s"}]
    )
    assert "eod: accept P4" in msg and "• P4: Keep it short." in msg
    assert not msg.startswith(eod.OPENER) and learn.note_body(msg) is None


def test_gather_prompt_is_read_only_and_targets_dms():
    prompt = learn.gather_prompt("DSELF", "DMGR", "USELF", eod.OPENER, 123)
    assert "send nothing" in prompt and "oldest=123" in prompt
    assert "DSELF" in prompt and "DMGR" in prompt and "`eod:`" in prompt
    assert "Josh" not in prompt


def paths(monkeypatch, tmp_path):
    monkeypatch.setattr(eod, "LESSONS_FILE", tmp_path / "lessons.md")
    monkeypatch.setattr(eod, "PROPOSALS_FILE", tmp_path / "proposals.json")
    monkeypatch.setattr(eod, "DRAFTS_DIR", tmp_path / "drafts")


def fake_claude(gathered):
    def run(prompt, schema, tools, model=None):
        assert schema is not learn.GATHER_SCHEMA or "DSELF" in prompt
        if schema is learn.GATHER_SCHEMA and "opener" in eod.CFG:
            assert eod.CFG["opener"] in prompt
        assert not any("send" in t for t in tools)
        return gathered if schema is learn.GATHER_SCHEMA else {"rules": []}

    return run


def test_learn_rules_persists(monkeypatch, tmp_path):
    paths(monkeypatch, tmp_path)
    eod.CFG["opener"] = "Morning, update from yesterday:"
    gathered = {"notes": [{"ts": TS_OCT15, "text": JAMES_NOTE}], "sent": []}
    monkeypatch.setattr(eod, "run_claude", fake_claude(gathered))
    lessons, new = eod.learn_rules(
        datetime(2026, 10, 15, tzinfo=timezone.utc), dry_run=False
    )
    assert "James" in lessons and new == []
    assert eod.LESSONS_FILE.read_text() == lessons
    assert learn.load_proposals(eod.PROPOSALS_FILE)["seen"] == [TS_OCT15]


def test_learn_rules_dry_run_writes_nothing(monkeypatch, tmp_path):
    paths(monkeypatch, tmp_path)
    gathered = {"notes": [{"ts": TS_OCT15, "text": JAMES_NOTE}], "sent": []}
    monkeypatch.setattr(eod, "run_claude", fake_claude(gathered))
    lessons, _ = eod.learn_rules(
        datetime(2026, 10, 15, tzinfo=timezone.utc), dry_run=True
    )
    assert "James" in lessons
    assert not eod.LESSONS_FILE.exists() and not eod.PROPOSALS_FILE.exists()
