---
name: claude-artifact
description: Rules for team-shared artifacts on the artifacts hub (Vercel site behind Vercel Authentication, repo RechargePayments/ai-artifacts-hub) - system overviews, design theory, feature details, decision cases written for other engineers. Every artifact carries a visible `Rev N · timestamp` stamp and never reads like a changelog or exposes the operator's working process. Built from a vault note and linked back (hub URL and rev in its frontmatter). Auto-fires when the user says "share this", "share with the team", "make it an artifact", "claude artifact", "artifact this", "artifact from note", "update the artifact", invokes /claude-artifact <note.md>, or before any hub publish of a document meant for other people. "publish" alone means the vault (`obsidian-note`), not this.
---
<!-- caveman:compressed -->

Vault note = working source, for the user. Artifact = distilled team view on the hub, always built from a note. Hub = `~/dev/ai/artifact-publish` (GitHub `RechargePayments/ai-artifacts-hub`, Vercel project `artifacts-hub` on `rechargeapps`, https://artifacts-hub-ten.vercel.app, Vercel Authentication on every deployment). Any claude.ai account publishes; the account never matters. Each publish is logged to the vault daily note by the `daily_note` hook; don't log it by hand.

## Route

| Ask | Do |
|---|---|
| "publish", "note this", "write this up", any durable doc | `obsidian-note` only. Never publish an artifact unasked; the user runs `/claude-artifact <note.md>` later |
| "share", "for the team", "artifact" in a session | write or update the vault note, then `## From a note` on it |
| `/claude-artifact <note.md>` | `## From a note` |
| re-share a note whose frontmatter has a hub `artifact:` | republish that hub name, never a second one |

## From a note

1. Read the whole note. N = `artifact_rev` + 1, else 1. Name = hub folder and URL path:
   - `artifact:` is a hub URL → its last path segment; republish with `FORCE=1`.
   - `artifact:` is a claude.ai URL (legacy) or absent → note stem, lowercased. No `FORCE`: publish.sh refuses a name another note already holds; then use `<stem>-<domain>` and say so.
2. Build per `## Build`, distilling per `## Content`. The note is the only source; no session context.
3. Publish: `[FORCE=1] ~/dev/ai/artifact-publish/publish.sh <scratchpad>/<name>.html <name>`. Validates (claude.ai-only runtime, credential shapes, kebab name), commits, pushes `main`, prints the URL; Vercel deploys on push. `hooks/artifact_gate.py` blocks the call when the page lacks the stamp or carries a changelog heading.
4. `python3 ~/.claude/skills/obsidian-note/scripts/note.py link <note.md> --url <url> --rev N --log "<what changed, one line>"`. Writes `artifact:` + `artifact_rev:`, drops legacy `artifact_account` / `artifact_mirror_*` keys, appends `- rev N · <ts> · <log>` under `## Artifact revisions`. The change history lives there, only there.
5. Report: URL, rev. Nothing else. No sharing advice: the hub is org-internal; never public or outside-org.

`scripts/from-note.sh [-y] <note.md>` opens this as an interactive session (tmux window, else a wezterm window), after a confirm unless `-y`. nvim `<leader>oA` calls it.

## Build

1. Load `artifact-design` (and `artifact-diagramming` when a picture shows the mechanism). Author one self-contained HTML document (doctype, head, body): the hub serves it as-is, nothing wraps it. Libraries only as pinned builds from cdnjs or jsdelivr. Never `window.claude`, `window.storage`, or `api.anthropic.com` in a script: hub validation rejects them.
   Doc-shaped note (sections, tables, prose): default to the house doc template, sticky TOC sidebar + Spark role colors (blue band and h2, teal h3 and code, lime number chips, tinted table heads). Never a monochrome page.
   ```bash
   python3 ~/.claude/skills/claude-artifact/scripts/build_doc.py <note.md> --out <scratchpad>/<name>.html --rev N \
     [--source-note <vault note.md>] [--doc-title "<Name>"] [--eyebrow "<Area · Kind>"] \
     [--companion-url <url> --companion-name "<bold text in note>"] \
     [--replace "<note-only line>" "<artifact line>"] [--docx <note dir>/gdoc/<stem>.docx]
   ```
   Input is the note or a distilled copy of it; a copy outside the vault needs `--source-note <the vault note>`, else the meta holds the bare filename. Renders into `doc-template/template.html`, stamps Rev N, sets `source-note`, builds the TOC from `## N. Title` / `## A. Title` headings. Diagrams: `![alt](diagrams/x.png)` in the note with a sibling `x.mmd`; the page gets the mermaid source plus a pinned mermaid loader whose theme follows `prefers-color-scheme`. Don't card or restyle it. `--docx` writes the Google Docs import (Drive upload, Open with Google Docs): PNGs embedded, frontmatter and `## Artifact revisions` stripped, Spark-styled (blue Georgia headings, teal h3 and Inconsolata code, Inter body, shaded table heads, blue row labels, direct table borders). Docx only; never touches the artifact. Mackinac face loads from the hub's `/fonts/mackinac-book.woff2` (licensed; the file lives only in the private hub repo, never in claude-code-config, whose github remote is public); opened outside the hub, headings fall back to Georgia.
2. Stamp, directly under the `<h1>`, visible: `Rev N · YYYY-MM-DD HH:MM TZ`. N from `## From a note` step 1. Time = publish time, local tz. `build_doc.py` writes it; hand-built pages add it.
3. Source link, when a vault note exists: `<meta name="source-note" content="areas/<area>/<domain>/<stem>.md">` in `<head>`. Vault-relative, invisible to readers.

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
