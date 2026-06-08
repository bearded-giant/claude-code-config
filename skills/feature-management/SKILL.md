---
name: feature-management
description: Feature folder lifecycle, scoping, and feature-scoped output routing for .giantmem/features/. Auto-fires when user says "create a plan", "draft a plan", "plan this out", "new feature", or invokes /new-feature, /plan-feature, /start-feature, /pause-feature, /complete-feature, /reopen-feature, /list-features, /feature-facts, /feature-report. Also fires before writing to .giantmem/features/** or when checking which feature is active.
---

Feature system for `.giantmem/features/`. Persistent capabilities that span sessions.

## Folder structure

```
features/
├── features.json          # cache, every command reads/writes
├── _index.md              # human-readable registry
├── {feature-name}/
│   ├── proposal.md        # intent + scope + approach (renamed from spec.md)
│   ├── design.md          # optional — technical approach + architecture decisions
│   ├── specs/{domain}/    # delta-specs — ADDED/MODIFIED/REMOVED Requirements
│   │   └── spec.md        # behavior contract relative to source-of-truth
│   ├── tasks.md           # checkbox list, status auto-derives from %
│   ├── facts.md           # beta flags, config, test commands
│   ├── meta.json          # machine-readable (swarm)
│   ├── plan.md            # /plan-feature output
│   ├── plan_context.json  # domain linkage
│   ├── plans/current.md   # transient session scratchpad (deleted on complete)
│   ├── research/          # scoped research
│   ├── reviews/           # scoped reviews
│   └── filebox/           # scoped data
```

## Three-spec split (post-OpenSpec-hybrid)

| Artifact | Role | When written |
|---|---|---|
| `features/{name}/proposal.md` | Intent — why this exists, scope, approach. NOT behavior. | `/new-feature` scaffolds. User refines. |
| `features/{name}/specs/{domain}/spec.md` | Delta-spec — `## ADDED` / `## MODIFIED` / `## REMOVED Requirements`. Behavior contract. Each Requirement has Given/When/Then scenarios (RFC 2119). | User/Claude writes when designing behavior. Empty allowed. |
| `.giantmem/specs/{domain}/spec.md` | Source-of-truth. Accumulated behavior across all completed features. | `/complete-feature` merges delta-specs in. Never hand-edited mid-feature. |

Legacy `features/{name}/spec.md` symlinks → `proposal.md` for 30-day muscle-memory back-compat (set by `migrate_spec_to_proposal.py`).

## Lifecycle (per-artifact)

Every artifact written under `features/{name}/` carries a `lifecycle:` field in addition to `status:`. Defaults stamped by `/new-feature` templates:

| Lifecycle | Used for | Behavior |
|---|---|---|
| `durable` | All `/new-feature` scaffolds (proposal, delta-spec, tasks, design, facts). Source-specs after `/complete-feature` merge. | Never auto-pruned. Shows up in default preload packs. |
| `candidate` | AI-captured research, discoveries, mid-session notes. | Listed by `/review-memory`. User promotes → durable or demotes → deprecated. |
| `deprecated` | Previously useful, now rejected. | Kept on disk. Excluded from default packs and stale reports. |

`/complete-feature` flips merged delta-specs to `lifecycle: durable` if not already (they should be — they came from a durable template).

## Cache discipline — CRITICAL

Every feature command (new/start/pause/complete/reopen) MUST update both:
- `.giantmem/features/features.json`
- `.giantmem/features/_index.md`

When adding beta flags or key config, add to Quick Reference section.

## Domain knowledge base

```
domains/
├── _index.json
├── {domain-name}.json
```

Repo-level, not feature-scoped. Created by `/plan-feature`, refreshed by `/update-domains` and `/complete-feature`. Load relevant domain JSONs at session start instead of re-reading code.

## When to create a feature folder

- Distinct capability, not a bug fix
- Spans multiple sessions
- Has identifiable artifacts (beta flag, endpoints)

## Commands

| Command | Purpose |
|---|---|
| `/list-features` | display registry |
| `/new-feature <name>` | scaffold folder (auto-detects pending vs in_progress) |
| `/plan-feature [name] [--refresh]` | explore domains, draft plan |
| `/list-domains [--verbose]` | show indexed domains |
| `/search-domains <query> [--load]` | search domain JSONs |
| `/update-domains [domains] [--all-stale]` | refresh domain JSONs |
| `/feature-facts <name>` | quick lookup |
| `/feature-report [feature]` | validation report (parses delta-spec Requirements) |
| `/feature-validate <name> [--fix]` | lint structure; `--fix` auto-repairs |
| `/feature-next [name]` | informational: next ready artifact per DAG |
| `/start-feature <name>` | promote pending → in_progress |
| `/pause-feature` | mark current paused |
| `/complete-feature` | mark complete, merge delta-specs to source-of-truth |
| `/reopen-feature <name>` | complete → in_progress |

Adjacent CLI surface (not Claude commands — terminal):

| Command | Purpose |
|---|---|
| `giantmem artifact list` | typed artifact query in current repo |
| `giantmem artifact list -f {feature}` | per-feature view |
| `giantmem artifact list --type delta-spec --status ready` | filter |
| `giantmem artifact reindex` | rebuild `.giantmem/artifacts.json` |
| `giantmem artifact show {id}` | print frontmatter + body |
| `giantmem artifact orphans` | files lacking frontmatter |

## "Create a plan" disambiguation — CRITICAL

When user says "create a plan", "plan this out", "draft a plan", or similar, MUST emit AskUserQuestion BEFORE any file write:

```
Question: feature (persistent, spans sessions) or session work (transient)?
Options:
  1. feature → /new-feature → features/{name}/proposal.md (+ delta-specs in specs/)
  2. session work → plans/current.md
```

Ask first. Write second. User often forgets which context they're in.

## Feature-scoped output routing

When a feature has status `in_progress` in `features.json`, it is the **active feature**. All session output that would normally go to top-level `.giantmem/` subdirectories MUST instead go inside the active feature's directory:

| Without active feature | With active feature `{name}` |
|---|---|
| `.giantmem/plans/current.md` | `.giantmem/features/{name}/plans/current.md` |
| `.giantmem/research/{topic}.md` | `.giantmem/features/{name}/research/{topic}.md` |
| `.giantmem/reviews/{subject}.md` | `.giantmem/features/{name}/reviews/{subject}.md` |
| `.giantmem/filebox/*` | `.giantmem/features/{name}/filebox/*` |

## Living feature notes (`{name}-notes.md`) — append during work

`/new-feature` seeds `features/{name}/{name}-notes.md` with minimal frontmatter and a single hint comment. Treat it as a **living cheat sheet**. Append silently as work happens — no permission ask, no chat announcement.

### Silent-background contract (CRITICAL — overrides default no-write bias)

When the active feature has status `in_progress` and an append trigger fires below, the model MUST:

1. **Append without asking.** Skip "should I save this?" — the trigger list IS the permission. Notes file exists (seeded), so it's an `Edit`, not a new-file `Write` — the global no-write-without-permission rule does not apply.
2. **Append silently.** Do NOT mention the append in chat. No "saved to notes", no "added to cheat sheet". Pure background. User reads the file when they want.
3. **Append in the same tool batch as the action being captured.** Don't defer to end-of-turn — model forgets. The Bash that runs a `kubectl` command and the Edit that appends it ship in one batch.
4. **Tiebreaker: append.** When unsure if a command is "reusable enough," append. Cost of noise in notes < cost of forgetting the command. Only skip if confidently single-use boilerplate.

### When to append (moderate — reusable signal)

- Bash / shell one-liner authored together OR pasted by the user (will likely re-run)
- `redis-cli`, `kubectl`, `gcloud`, `gh`, `glab`, `psql`, `mysql`, `curl`, `bq`, `vault`, `aws` commands that returned useful state or are worth re-running
- DB query that surfaced a non-obvious row / state worth re-querying
- env var, config knob, beta flag, or feature flag discovered mid-session (also mirror flag/endpoints into `facts.md`)
- Specific identifier worth keeping (e.g. `shop_id 47281 reproduces the bug`, `job_id abc123 = stuck task`, customer email, MR URL, Jira ticket)
- Script / function written for the feature, even tiny
- Path to a useful log file, dashboard URL, monitoring query, repro endpoint
- User explicitly says "save this" / "good for later" / "note that" / "we'll need this again" — append immediately, override every skip rule

### When NOT to append

- Single-use debug command obviously throwaway (e.g. one-shot `ls`, `cat <file>` to peek)
- Generic Linux commands every dev already knows (`git status`, `ls -la`)
- Content that belongs in another feature artifact — put it there instead:
  - intent / scope / approach → `proposal.md`
  - beta flag / endpoints / test commands / key files → `facts.md`
  - checkbox work items → `tasks.md`
  - behavior contracts (Requirements / Scenarios) → `specs/{domain}/spec.md`
- Spec quote, RFC 2119 wording — those are normative, live in delta-specs
- Anything inside `/complete-feature` execution — see Lifecycle below

### Sensitive data — REDACT before append

NEVER append raw:
- `Authorization: Bearer ...` tokens, API keys, vault tokens, OAuth secrets
- DB connection strings with embedded passwords
- Customer PII (email, phone, address) unless the user explicitly said save it
- `.env` file contents, GPG keys, SSH private keys

Redact with `<REDACTED:token>`, `<REDACTED:password>`, `<REDACTED:pii>` placeholders. Keep the surrounding command shape so it's still re-runnable after the user re-injects the secret.

### Format — VERY loose, no prescribed structure

- Append-only. Never reorder past entries. Never reformat past entries. Never delete past entries unless user explicitly asks.
- Group loosely by topic if helpful, otherwise chronological is fine.
- Code blocks for commands — preserve EXACTLY, no caveman compression inside fenced blocks.
- Prose around the block: caveman style, one short line, *why* not *what*.
- No section banners (`# === foo ===`), no decorative headers.
- Do NOT touch the seed frontmatter — append below it.

### Read on session resume — `non-empty` semantics

Read `{name}-notes.md` on resume when file has **content past the seed line** — i.e. >1 line of body beyond the frontmatter + seed `<!-- ... -->` comment. A file containing only frontmatter + seed comment counts as empty for resume purposes; skip it, do not surface the seed comment in chat.

When body content exists and resumed work touches a captured command/snippet, surface the relevant entry once ("last session we used: `<cmd>`") so it gets reused. Don't dump the whole file.

### When no feature is `in_progress`

Skip notes capture entirely. Do NOT buffer to a scratch file, do NOT prompt user to create a feature. Useful commands from session work go in `.giantmem/plans/current.md` if relevant to the current task, otherwise let them go. Notes file is feature-scoped by design.

### Lifecycle

- **During in_progress:** append per rules above.
- **During `/pause-feature`:** stop appending. Resume on `/start-feature` or `/reopen-feature`.
- **During `/complete-feature` execution itself:** do NOT append further. File freezes as durable reference at the moment `/complete-feature` starts.
- **After complete:** file stays in `features/{name}/`. Not merged into source-specs. Not pruned by `giantmem artifact stale`. Treated as `lifecycle: durable` per its frontmatter.

## Always global — NEVER feature-scoped

- `domains/` — repo-level code knowledge
- `history/` — session log spans all features
- `prompts/` — reusable templates
- `context/patterns.md` — curated architectural patterns (repo-level)
- `WORKSPACE.md`, `features/_index.md`, `features.json`

Create subdirectories inside feature folder on first write. Don't require upfront.

When no feature is `in_progress`, use top-level `.giantmem/` subdirectories.

## Session start check

Read in order if files exist:
1. `.giantmem/WORKSPACE.md`
2. `.giantmem/features/features.json` — find active feature
3. Active feature's `plans/current.md`, else `.giantmem/plans/current.md`
4. Active feature's `{name}-notes.md` if non-empty — living cheat sheet, surface relevant commands when resuming related work

If step 1's file is missing, skip steps 2-4.
