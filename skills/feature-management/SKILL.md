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

If step 1's file is missing, skip steps 2-3.
