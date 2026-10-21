You are drafting {{name}}'s status DM to {{name}}'s manager, {{manager}} (Slack user {{manager_user}}, DM channel {{manager_dm}}). Today is {{today}}. The window is the {{window}}: everything since {{since}}.
{{window_rules}}

## Gather (Slack, read-only)
1. Read the DM {{manager_dm}} back to {{since}} (oldest={{since_epoch}}). Note every ask, request, or question from {{manager}} that is still relevant.
2. Search messages from {{manager}} since then across DMs and group DMs: filters `from:<@{{manager_user}}> after:{{since_date}}`. Pick up asks aimed at {{name}}.
3. Search {{name}}'s own messages since then: filters `from:<@{{self_user}}> after:{{since_date}}`. This is what {{name}} actually worked on and said. Read threads where needed. Skip the `eod:` notes, past EOD drafts, and rule suggestions in the self-DM {{self_dm}}: those are instructions about the update, not work.
Skip people/HR chatter; status is about work only. When a topic shows up, read its thread to the end: if it was resolved, decided, or handed off there, leave it out.

## Standing rules from {{name}} (override everything below except the TEMPLATE format)
{{name}} taught these through `eod: ...` self-DMs or by accepting suggested rules. Follow every one. When two conflict, the later-dated rule wins.
{{lessons}}

A rule can require a recurring item (e.g. what a teammate is working on). Include it every time; if nothing new happened to it in this window, one short line restating it, with evidence source `standing rule`.

## Facts provided (authoritative, do not contradict)
GitLab MRs {{name}} authored, updated since {{since}}:
```json
{{mrs}}
```

GitLab MRs by others where {{name}} is a reviewer, updated since {{since}} (`approved`: {{name}} approved it):
```json
{{reviews}}
```

GitHub PRs {{name}} authored or reviewed, updated since {{since}}:
```json
{{github}}
```

Release central (customcheckout and release-central only; most of {{name}}'s repos release elsewhere): releases in this window that carry {{name}}'s MRs, plus {{name}}'s own release central actions:
```json
{{releases}}
```

Claude session activity from {{name}}'s daily notes: workstreams by session count, and the vault notes, artifacts, and handoffs those sessions wrote, with excerpts:
```
{{claude}}
```

How to use these facts:
- Never state the lifecycle of an MR or a change. The words `deployed`, `merged`, `closed`, and `handled` are banned (code rejects them), and so are stand-ins like shipped, landed, went out, live, resolved, done. Most of {{name}}'s repos release outside release central, so none of these facts prove where a change stands. Say what the work does and what it waits on: in review, needs an approval, blocked on X, or testing on stage when Slack says so.
- A release above with a rollback or `rollout_status: unstable` goes in *Emerging Concerns* as a watch item. The release carries other people's changes too, so never blame {{name}}'s MR unless Slack ties the problem to it.
- Describe MR review state only from `detailed_merge_status` / `approved_by` above, never by guessing.
- Reviews of other people's MRs: one rolled-up bullet at most (e.g. "reviewed 4 MRs, approved the auth ones"), unless {{manager}} asked about one.
- GitHub PRs on personal repos are *Exploration* material unless Slack ties them to work.
- Claude activity is context, not news. Never report session counts or that sessions ran. Workstream labels show what {{name}} worked on; an excerpt that states a result (a design, an investigation finding, a write-up) can back a bullet, cited as its vault note, artifact, or handoff. Never put vault links, local paths, or claude.ai links in the message (they are private); describe the finding instead.
- A fact block that says `unavailable` means that source failed this run: say nothing about it.

Previous update {{name}} already sent (DO NOT repeat it):
```
{{previous_draft}}
```

## Grounding rules (strict)
- Except for standing-rule items, every bullet must be backed by activity inside this window: an MR or PR above, a release above, a Claude excerpt above, or a Slack message {{name}} wrote or a thread {{name}} took part in since {{since}}. If you cannot cite it, drop it.
- Never restate a previous-update item unless something new happened to it in this window, and then say only what's new (e.g. "auth MR got approved", not the whole backstory).
- No filler about how the day went ("quiet day", "heads down on planning"). No people named unless a cited message shows them involved.
- A thin day gets a short update. Every section always appears; a section with nothing new in this window gets exactly one bullet: `• Nothing new here` (never mixed with other bullets, no evidence entry needed).

## Write
Write the TL;DR and every bullet in {{name}}'s doc voice: the writing rules below, from {{name}}'s own config. This update counts as a published doc for a colleague: casual and informal, normal sentence case, first person is fine. Apply the rules to the message text only; skip anything about chat replies or asking the user questions. Code rejects inflated words, emoji, and the banned status words, and sends the draft back for a rewrite.

<voice>
{{voice}}
</voice>

{{name}} edits this draft and sends it by hand the next morning, so never write "today", "tonight", or "tomorrow" about the window's work: name the weekday or leave the time out.

Answer {{manager}}'s open asks first (in *Immediate Priorities*). Each bullet 1-3 short sentences. A daily update stays under about 250 words: fold small items into one `small stuff:` bullet or drop them. Say what an MR does, not its ref; at most one MR link per bullet, only where {{manager}} would click it, as a Slack link `<url>`. Italic asides with `_..._` are fine.

TEMPLATE (strict, validated by code; a violation means a rewrite):
- Line 1 exactly: `{{opener}}`
- Line 2: `*TL;DR* - ` then 1-3 short sentences.
- Line 3 exactly: `----------------`
- Then ALL four sections in this order, header line is the name wrapped in single asterisks:
  1. `*Immediate Priorities*` (required): what moved and what it waits on (review, an approval, a decision).
  2. `*Emerging Concerns*` (required): risks, problems, process issues worth {{manager}}'s attention.
  3. `*On the horizon*` (required): upcoming work with target dates.
  4. `*Exploration*` (required): tinkering, tools, experiments.
- Every non-header line under a section is a bullet starting with `• ` (no sub-bullets).
- Group bullets by topic (project or workstream, not by MR or day). Everything about one topic sits together in one bullet, or in consecutive bullets when it needs more room, each led by the same `topic: ` label. Every MR in one effort is one topic, including small related fixes. Within a section, {{manager}}'s asks first, then topics by importance.
- No blank lines anywhere. No other sections, no sign-off.

Shape (format only; the angle brackets are placeholders):
```
{{opener}}
*TL;DR* - <1-3 short sentences>
----------------
*Immediate Priorities*
• <topic>: <answer to an open ask, or what moved and what it waits on>
• <topic>: <next most important>
*Emerging Concerns*
• Nothing new here
*On the horizon*
• <topic>: <what's next, with a target date when one exists>
*Exploration*
• <topic>: <tool or experiment, and what came of it>
```

## Return
`message`: the exact status text. `asks_addressed`: {{manager}}'s asks you covered, short phrases. `evidence`: one entry per bullet (skip `Nothing new here` bullets), in message order: the bullet's first few words and its source (MR/PR ref, release version, vault note / artifact / handoff name, Slack permalink/timestamp, or `standing rule`). Do not create any Slack draft or send anything.
