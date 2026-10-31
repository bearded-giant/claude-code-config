---
name: artifact-comments
description: >-
  Work the reader comment threads on a published claude.ai artifact - fix what they caught in the vault note and the body, answer each thread in a closing "Questions readers asked" section, republish the next rev, resolve the threads sent to Claude, and tell the user which stay open. Auto-fires when the user says "address the artifact comments", "go through the comments on the artifact", "answer the comments", "clear the comments", "work the threads", "move the comments to a Q&A", or invokes /artifact-comments <note.md|artifact url>. Skip for MR/PR review threads (babysit, accept-kai-feedback).
---
<!-- caveman:compressed -->

Comments are feedback on the design account. Two outputs per pass: a body rewritten to the current truth, and a closing section where each thread is answered by name. Never a reply that says "updated", never a changelog.

## Preconditions

1. Note: the argument, or the note whose frontmatter `artifact:` matches the URL (`grep -l 'artifact: <url>' ~/Recharge-Notes/areas -r`). No note → stop: artifacts are built from notes (`claude-artifact`).
2. `python3 ~/.claude/skills/obsidian-note/scripts/note.py account <note.md>`: non-zero = this session is not the source account (a mirror's threads are not worked; readers comment on the source); stop, relay the message.
3. `ArtifactComments` `read` on the URL. Zero threads → say so, stop.

## Pass

1. Read the whole note. Read the artifact (`Artifact` `read`): the old stamp gives N; the saved HTML gives the build flags (`<title>` → `--doc-title`, `class="eyebrow"` → `--eyebrow`, `Companion: <name>` + its href → `--companion-name`/`--companion-url`).
2. Triage each open thread against the code, not the note (code is truth):
   - **body**: the text is wrong, stale, or missing what was asked (an example, a comparison, a mechanism) → rewrite that part of the note to the current code. No delta prose.
   - **ask for a behavior change**: the code does not do it → not yours to promise. Answer what the code does; the ask goes to the user as a `decision` item on the feature list (`feature-management`). The artifact claims it only once it ships.
   - **question only**: answered in the closing section.
3. Closing section, last `## N. Questions readers asked` before `## Artifact revisions` (create it once, extend it after): one bold question per thread in the commenter's words, tightened, then one or two bullets, current fact, pointing at the section that holds the detail (`section 4`). Two bullets max. No names, no dates, no "done" / "now" / "fixed".
4. Build + publish rev N+1 per `claude-artifact` `## Build` (same `--out` path, `url` on the publish), then `note.py link --rev N+1 --log "<threads answered, one line>"`, then mirror it per `claude-artifact` `## From a note` step 6.
5. Threads: `ArtifactComments` `reply` with the thread's bullets as one or two plain sentences, then `resolve`, on threads marked activated only. Never resolve a thread not sent to Claude and never one you did not address.
6. Report: rev + URL, then the open threads as a table (thread, section that answers it) so the user can resolve them in the artifact view, then any `decision` items raised. Nothing else.

## Never

- answer a thread by reasoning about the note; verify in the code first
- reply "updated to" / "now does"; the answer is the current behavior
- more than two bullets per question; detail lives in the body section the bullet names
- resolve to tidy up: a thread asking for a change the code lacks stays open and gets a `decision` item
