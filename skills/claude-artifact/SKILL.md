---
name: claude-artifact
description: Rules for team-shared claude.ai Artifacts (the `Artifact` tool) - system overviews, design theory, feature details, decision cases written for other engineers. Every artifact carries a visible `Rev N · timestamp` stamp and never reads like a changelog or exposes the operator's working process. Links to the source Obsidian note when one exists. Auto-fires when the user says "share this", "share with the team", "make it an artifact", "claude artifact", "artifact this", "update the artifact", or before any Artifact publish of a document meant for other people. "publish" alone means the vault (`obsidian-note`), not this.
---
<!-- caveman:compressed -->

Vault note = working source, for the user. Artifact = distilled team view.

## Route

| Ask | Do |
|---|---|
| "publish", "note this", "write this up" | `obsidian-note` only |
| "share", "for the team", "artifact" | artifact; also write or update the vault note first when the subject is durable |
| re-share a note whose frontmatter has `artifact:` | update that URL (read it first), never a new artifact |

## Build

1. Load `artifact-design` (and `artifact-diagramming` when a picture shows the mechanism). Author HTML.
2. Stamp, directly under the `<h1>`, visible: `Rev N · YYYY-MM-DD HH:MM TZ`. First publish N=1. Republish: read the artifact, parse the old stamp, N+1. Time = publish time, local tz. `hooks/artifact_gate.py` blocks any publish without it.
3. Source link, when a vault note exists: `<meta name="source-note" content="areas/<area>/<domain>/<stem>.md">` in `<head>`. Vault-relative, invisible to readers.
4. Publish. Then, when a note exists:
   ```bash
   python3 ~/.claude/skills/obsidian-note/scripts/note.py link <note.md> --url <artifact url> --rev N --log "<what changed, one line>"
   ```
   Writes `artifact:` + `artifact_rev:` frontmatter and appends `- rev N · <ts> · <log>` under the note's `## Artifact revisions`. The change history lives there, only there.

## Content

Audience: engineers and leads reading a principal engineer's account of a system. State the current design as fact.

Never in an artifact (hook blocks the headings, the rest is on you):
- changelog shapes: revision history, what's new, changes in/since rev N, release notes, update log
- delta prose: "updated to", "now does", "previously", "no longer", "fixed", "was changed", "as of", "currently", "recently"
- dates other than the stamp; deploy, merge, MR, ticket, or rollout status
- process: grill runs, swarm, doit, giantmem, sessions, worktrees, branches, "I tried", "we found while", review back-and-forth
- local paths, store/user IDs, secrets, tokens, customer PII

Republish = rewrite to the current truth, not append. A section that only existed to explain a change gets folded into the design or dropped.

Note → artifact is a distill, not a transcribe: the note may hold dates, logs, and open threads; the artifact keeps the durable design.
