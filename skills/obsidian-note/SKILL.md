---
name: obsidian-note
description: Write Claude-authored markdown into the Obsidian vault (~/Recharge-Notes/areas/<area>/<domain>/) with the vault frontmatter contract plus a creation timestamp, list vault notes by area/domain/project/tag to pull prior context, and link a note to its claude.ai artifact. Default target of "publish". Auto-fires when the user says "publish", "publish this", "note this", "write this up", "save to obsidian", "runbook for", "write me a doc/reference/summary", or asks for any markdown deliverable that is not feature state (.giantmem/). Never writes to ~/Desktop. Skip for feature artifacts (proposal, plan, tasks, specs, reviews) which stay under .giantmem/, and for handoffs (workspace-rules `## Handoff` owns `handoffs/`).
---
<!-- caveman:compressed -->

Vault = `~/Recharge-Notes`, the only vault Claude writes; "the vault", "write to vault", "publish" always mean it. `~/giantmem-vault` is a read-only Obsidian view of repo `.giantmem` dirs, never a target. Vault = source of truth, default target of "publish". Team sharing = claude.ai artifact via `claude-artifact` skill, distilled from the note, linked both ways. Desktop = never.

## Write

Body to a scratchpad file, then:

```bash
python3 ~/.claude/skills/obsidian-note/scripts/note.py new \
  --title "recharge-auth Redis keys and TTLs" \
  --area auth \
  --domain sessions \
  --tags redis,ttl \
  --body-file "$SCRATCH/body.md"
```

Prints abs path. Report that path to the user, nothing else.

- `--area` required, closed list below. Pick one; tags carry overlap.
- `--domain` required, lowercase-hyphenated subdir under the area: the system, product, or recurring topic a reader would search by (`ai-tooling/recharge-mcp`, `ai-tooling/churn-investigator`, `ai-tooling/mcp-general`). Run `note.py domains --area X` and reuse an existing domain when it fits. New domain only when no existing one does; `<topic>-general` is the catch-all name. Never a worktree, branch, or ticket.
- `--project` defaults to git repo name of cwd (worktree parent minus `-wt`, so `cc-wt/stage` gives `cc`). Pass it when cwd is not the subject repo or the default is too terse.
- `--tags` comma list, lowercase, hyphenated. `claude` prepended always.
- `--created` ISO 8601, only for imports (birthtime). Default now with tz.
- `--key PE-1234` for ticket notes (`sec-ticket` skill): filename becomes `PE-1234-<slug>.md` (key kept uppercase, stripped from the slug when the title starts with it), frontmatter gains `ticket`, `rev: 1`, `modified`, `status: new`.
- Body starting with `# ` keeps its own H1; otherwise `# <title>` is inserted.
- Filename = slug of title. Collision appends `-YYYY-MM-DD`, then `-N`. Never overwrite.

## Areas

| area | covers |
|---|---|
| auth | recharge-auth, sessions, JWT, redis session cache, tokens, api keys |
| ai-tooling | claude config, MCPs, orchestrator, agents, dashboards, doit, prompts |
| migration | skio, monster, translation layer, data model mapping |
| platform | recharge API, bundles, repricing, platform docs |
| infra | ES, sentry, splunk, k8s, zendesk plumbing, vault |
| dev-process | merge train, quality, local dev setup, SDLC |
| dev-tools | nvim, tmux, terminal, shell, alfred |
| personal | bearded giant, non-work |
| security | ticket reviews (HackerOne, internal, client), vuln research, fix proposals; domain = repo alias |

New area = edit `AREAS` in `scripts/note.py` and this table, same commit. Domains are open; the vault tree is the registry.

## Frontmatter emitted

```yaml
---
id: recharge-auth-redis-keys-and-ttls
aliases: []
tags: [claude, redis, ttl]
area: auth
project: recharge-auth
created: 2026-09-28T14:38:12-04:00
---
```

`id, aliases, tags, area, project` = obsidian.nvim contract, do not add or rename keys. Script-owned additions: `created`, `artifact` + `artifact_rev` + `artifact_account` once linked, and `ticket` + `rev` + `modified` + `status` on `--key` notes. Domain is the folder, not a key. Do not hand-write frontmatter; the script owns it.

## Bump or set status on a ticket note

After any content edit to a `--key` note, and on a status change:

```bash
python3 ~/.claude/skills/obsidian-note/scripts/note.py bump <note.md>
python3 ~/.claude/skills/obsidian-note/scripts/note.py status <note.md> ready   # new ready blocked in_progress in_review done wont_fix
```

`bump`: `rev` +1, `modified` = now. `status`: sets `status`, `modified` = now, `rev` unchanged. Ticket notes carry no revision log; the `sec-ticket` skill keeps it on the doit list. A note without `rev:` whose filename starts with a ticket key (legacy `pe-1527-review-...`) gains `ticket`, `rev: 2`, `modified`, `status: new` on its first bump; any other note without `rev:` exits non-zero, and so does `status`.

## Link to an artifact

After a `claude-artifact` publish of this note's content:

```bash
python3 ~/.claude/skills/obsidian-note/scripts/note.py link <note.md> --url <artifact url> --rev N --log "one line on what changed"
```

Upserts `artifact:` / `artifact_rev:` / `artifact_account:` (logged-in claude.ai org label, `--account` overrides) and appends `- rev N · <ts> · <log>` under `## Artifact revisions`. Temporal detail and change history belong in the note, never in the artifact. Note already has `artifact:` → re-share updates that URL. `note.py account [<note.md>]` prints the login's label and exits non-zero when the note's artifact lives in another account. Building the artifact from a note → `claude-artifact` `## From a note`.

## Read before write

```bash
python3 ~/.claude/skills/obsidian-note/scripts/note.py list --area auth --since 90
python3 ~/.claude/skills/obsidian-note/scripts/note.py list --area auth --domain sessions
python3 ~/.claude/skills/obsidian-note/scripts/note.py list --tag redis
python3 ~/.claude/skills/obsidian-note/scripts/note.py list --ticket PE-1526   # ticket: key or a key-prefixed filename, any area
python3 ~/.claude/skills/obsidian-note/scripts/note.py list --status ready      # ticket notes in one status; rows gain a status column
python3 ~/.claude/skills/obsidian-note/scripts/note.py domains
```

One line per note: `created | area | domain | project | path | title`. Read the hits that match the subject before writing a new note. Extend an existing note (Edit) when the subject is the same; new note when the subject is new.

## Rules

- Vault pushes to GitHub every 5 min. No secrets, tokens, connection strings with passwords, query dumps, or customer PII. Redact `<REDACTED:token>`. Raw dumps stay in the scratchpad.
- Notes are for the user: paths, dates, changelogs allowed. Anything for others goes out as a `claude-artifact`, not a note.
- The `daily_note` hook logs every vault note write (Write/Edit or `note.py new`) and every artifact publish under `## CLAUDE LINKS` in `daily/<YYYY-MM-DD>.md`, creating the day's note from `templates/dailytemplate.md` when missing. Never hand-edit those sections or log twice.
- Feature state stays in `.giantmem/`: proposal, plan, tasks, specs, facts, reviews, research tied to an in_progress feature. Handoffs go to `handoffs/<project>/` per workspace-rules `## Handoff`, never through `note.py`. Cross-repo durable knowledge (runbook, incident writeup, design note, reference, decision record, how-to) goes to the vault.
- Do not write `areas/index.md`; it is a Dataview page.
- Wiki links `[[note]]` resolve vault-wide; link existing notes by stem when relevant.
