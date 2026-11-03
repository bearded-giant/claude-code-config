---
name: claude-artifact
description: Rules for team-shared claude.ai Artifacts (the `Artifact` tool) - system overviews, design theory, feature details, decision cases written for other engineers. Every artifact carries a visible `Rev N · timestamp` stamp and never reads like a changelog or exposes the operator's working process. Built from a vault note and linked back (artifact URL, rev, and claude.ai account in its frontmatter). Auto-fires when the user says "share this", "share with the team", "make it an artifact", "claude artifact", "artifact this", "artifact from note", "update the artifact", invokes /claude-artifact <note.md>, or before any Artifact publish of a document meant for other people. "publish" alone means the vault (`obsidian-note`), not this.
---
<!-- caveman:compressed -->

Vault note = working source, for the user. Artifact = distilled team view, always built from a note. Each publish is logged to the vault daily note by the `daily_note` hook; don't log it by hand.

## Route

| Ask | Do |
|---|---|
| "publish", "note this", "write this up", any durable doc | `obsidian-note` only. Never publish an artifact unasked; the user runs `/claude-artifact <note.md>` later |
| "share", "for the team", "artifact" in a session | write or update the vault note, then `## From a note` on it |
| `/claude-artifact <note.md>` | `## From a note` |
| re-share a note whose frontmatter has `artifact:` | update that URL (read it first), never a new artifact |
| "hub", "to the hub", `/claude-artifact <note.md> --hub` | `## Hub` only; never also claude.ai unless asked |

## From a note

The note's `artifact_account` owns the artifact: only a session on that account can update it.

1. `python3 ~/.claude/skills/obsidian-note/scripts/note.py account <note.md>`. Prints this session's claude.ai label (`rc-inc`, `rc-team`) from its keychain slot; tell the user it before anything else. Non-zero = the artifact lives in the other account; stop, relay the message.
2. Read the whole note. `artifact:` present: read that URL, N = old stamp + 1, publish with `url`. The read is not `writer`: the artifact lives in the other account (linked before accounts were recorded); stop and say so, never publish a second artifact. Absent: N = 1, new artifact.
3. Build + publish per `## Build`, distilling per `## Content`. The note is the only source; no session context.
4. `note.py link` per Build step 4. It records `artifact_account` from the session.
5. Report: URL, account, rev. Nothing else. No sharing advice: artifacts stay org-internal, never public or outside-org.

`scripts/from-note.sh [-y] [--account rc-inc|rc-team] <note.md>` opens this as an interactive session (tmux window, else a wezterm window) on that account's keychain slot (`CLAUDE_SECURESTORAGE_CONFIG_DIR`, the `claude-team` / `claude-ent` dirs), after a confirm unless `-y`. Account defaults to `artifact_account`, else the caller's login. nvim `<leader>oA` calls it. `claude -p` has no Artifact tool, so headless runs cannot publish.

## Hub

Opt-in side path, only when the user says hub; the claude.ai flow above stays the default. Hub = `~/dev/ai/artifact-publish` (GitHub `RechargePayments/ai-artifacts-hub`; Next.js app in `hub/`, Vercel project `artifacts-hub-next`, https://artifacts.beardedgiant.tools). Readers sign in with a rechargeapps.com Google account, and every artifact starts closed to everyone but the hub admins (the user) until shared in the hub UI (Share dialog). Any claude.ai account publishes.

1. Read the whole note. N = `artifact_hub_rev` + 1, else 1. Name = last path segment of `artifact_hub:`, else the note stem lowercased. A republish of the same slug creates a new version; another note holding the slug means use `<stem>-<domain>` and say so.
2. Distill per `## Content`, then `build_doc.py <note.md> --out <scratchpad>/<name>.html --rev N --hub [...]` per `## Build`: full document, Mackinac inlined, pinned mermaid loader. A hand-built page: full document, nothing from claude.ai's runtime (`window.claude`, `window.storage`); hub validation rejects those.
3. From `~/dev/ai/artifact-publish`: `pnpm --filter art art publish <file.html> --title "<note title>" --slug <name> --label "Rev N" --json` prints `{id, slug, version, url}`. The CLI holds the user's hub login in the keychain (`pnpm --filter art art whoami --json` shows it; `art login --hub https://artifacts.beardedgiant.tools` when it is missing, the user's step). `--slug` appends a version to the artifact holding it, else creates it; same content is unchanged, new content is a new version. `hooks/artifact_gate.py` does not see this call, so check the `Rev N` stamp yourself first. Fallback with no login: `cd hub && pnpm exec tsx scripts/import.ts <file.html> [slug]` with the production env (`DATABASE_URL`, `DATABASE_URL_UNPOOLED`, `BLOB_READ_WRITE_TOKEN`, `ADMIN_EMAILS`, `HEADING_FONT_URL=fonts/heading.woff2`, `HUB_ORIGIN`, `AUTH_PROVIDER=none`, `DB_DRIVER=neon`, `BLOB_DRIVER=vercel`, `ORG_NAME=Recharge`), which writes as the owner directly.
4. `note.py link <note.md> --hub --url <url> --rev N --log "<one line>"`: writes `artifact_hub:` + `artifact_hub_rev:`, logs `- rev N · <ts> · hub <url> · <log>`, claude.ai keys untouched.
5. Share only when the user names people or says everyone: the hub UI Share dialog (rechargeapps.com addresses only), which is the user's step. Never everyone unasked.
6. Report: URL, rev, and who it is shared with (from the hub UI).

## Build

1. Load `artifact-design` (and `artifact-diagramming` when a picture shows the mechanism). Author HTML.
   Doc-shaped note (sections, tables, prose): default to the house doc template, sticky TOC sidebar + Spark role colors (blue band and h2, teal h3 and code, lime number chips, tinted table heads). Never a monochrome page.
   ```bash
   python3 ~/.claude/skills/claude-artifact/scripts/build_doc.py <note.md> --out <scratchpad>/<stem>.html --rev N \
     [--source-note <vault note.md>] [--doc-title "<Name>"] [--eyebrow "<Area · Kind>"] \
     [--companion-url <url> --companion-name "<bold text in note>"] \
     [--replace "<note-only line>" "<artifact line>"] [--docx <note dir>/gdoc/<stem>.docx]
   ```
   HTML note (`.html`): the note is already the page and `build_doc.py` reads md only. Copy it to the scratchpad, drop the leading `<!-- --- ... --- -->` metadata comment, distill per `## Content`, add the stamp (step 2) and `source-note` meta (step 3), publish that copy; hub takes the same file. No TOC is added: the note's layout stands.
   Input is the note or a distilled copy of it; a copy outside the vault needs `--source-note <the vault note>`, else the meta holds the bare filename. Renders into `doc-template/template.html`, stamps Rev N, sets `source-note`, builds the TOC from `## N. Title` / `## A. Title` headings. Diagrams: `![alt](diagrams/x.png)` in the note with a sibling `x.mmd`; the page gets the raw mermaid source and the host renders it natively. Don't theme or card it: forced themes fight the host's dark mode and look worse. `--docx` writes the Google Docs import (Drive upload, Open with Google Docs): PNGs embedded, frontmatter and `## Artifact revisions` stripped, Spark-styled (blue Georgia headings, teal h3 and Inconsolata code, Inter body, shaded table heads, blue row labels, direct table borders). Docx only; never touches the artifact. Republish = same `--out` path. Mackinac face reads from the recharge-auth checkout (`$ARTIFACT_DISPLAY_FONT` overrides); never commit the font, the github remote is public.
2. Stamp, directly under the `<h1>`, visible: `Rev N · YYYY-MM-DD HH:MM TZ`. First publish N=1. Republish: read the artifact, parse the old stamp, N+1. Time = publish time, local tz. `hooks/artifact_gate.py` blocks any publish without it.
3. Source link, when a vault note exists: `<meta name="source-note" content="areas/<project>/<stem>.md">` (`.html` for an html note) in `<head>`. Vault-relative, invisible to readers.
4. Publish. Then, when a note exists:
   ```bash
   python3 ~/.claude/skills/obsidian-note/scripts/note.py link <note.md> --url <artifact url> --rev N --log "<what changed, one line>"
   ```
   Writes `artifact:` + `artifact_rev:` + `artifact_account:` frontmatter and appends `- rev N · <ts> · <log>` under the note's `## Artifact revisions`. The change history lives there, only there.

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

Reader comments on a published artifact: `artifact-comments` skill (body rewritten to the current code, each thread answered in a closing `## N. Questions readers asked` section, threads sent to Claude resolved, the rest listed for the user).
