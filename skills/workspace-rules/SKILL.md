---
name: workspace-rules
description: Output rules for .giantmem/ — directory selection, format, verbosity, anti-patterns, naming. Auto-fires before writing any file under .giantmem/**, before writing to repo docs/, when user asks to "save findings", "write a plan", "document this", or invokes /ws-init. Also fires when generating long-form analysis or reference docs.
---

Output rules for `.giantmem/` workspace. Loads on-demand.

## Critical rules

1. **Feature-scoped routing applies.** When a feature is `in_progress`, plans/research/reviews/filebox go inside the active feature dir. See [[feature-management]] for routing table.
2. **Never write to repo `docs/` unprompted.** Repo `docs/` is shipped doc, human-owned. Route Claude-generated output to `.giantmem/context/<topic>.md` or the active feature's `research/`.
3. **Never output long-form content only in chat.** If `.giantmem/` exists and output is >40 lines or has tables/diagrams, write to the correct subdir per the routing tables below.

## Open Questions block

When a doc has unresolved questions, put them at the TOP under `## Open Questions for User`. Before any TOC, summary, or content. Buried questions get missed.

Format: numbered list, mark blocking vs non-blocking.

```markdown
## Open Questions for User
1. [BLOCKING] Should auth tokens expire at 1h or 24h?
2. [non-blocking] Redis or Postgres for session store?
```

Remove the section once answered.

## Global directories — always at `.giantmem/` level

| Directory | Format | Verbosity | Example |
|---|---|---|---|
| `artifacts.json` | Live artifact index | Machine-built, never hand-edit | Built by `giantmem artifact reindex` |
| `features/_index.md` | Registry table | Terse, table rows | Feature name, status, beta flag |
| `features/{name}/proposal.md` | Feature intent (renamed from spec.md) | Medium, structured | Intent + scope + approach |
| `features/{name}/design.md` | Technical design (optional) | Medium | Architecture, decisions, file changes |
| `features/{name}/tasks.md` | Checkbox list | Hierarchical | Auto-status from checkbox % |
| `features/{name}/specs/{domain}/spec.md` | Delta-spec | Structured | ADDED / MODIFIED / REMOVED Requirements |
| `features/{name}/facts.md` | Quick lookup | Terse, key-value | Beta flags, config keys, test cmds |
| `features/{name}/plan.md` | Implementation plan | Concise, actionable | Steps, file paths, function names |
| `specs/_index.md` | Source-spec registry | Terse, table rows | Domains, last merged, requirement counts |
| `specs/_history.md` | Spec merge log | Append-only | Chronological per `/complete-feature` merge |
| `specs/{domain}/spec.md` | Source-of-truth spec | Requirements + Scenarios | RFC 2119, Given/When/Then. Merged from delta-specs. |
| `context/patterns.md` | Curated patterns | Medium, organized | Architectural decisions, gotchas |
| `context/*.md` | Reference docs | Minimal prose, lists ok | API lists, dep maps |
| `history/sessions.md` | Session log | One line per session | `- 2026-05-18: worked on auth` |
| `prompts/*.md` | Prompt templates | N/A | Reusable templates |

## Feature-scoped directories — inside active feature when present, else `.giantmem/` level

| Directory | Format | Verbosity | Example |
|---|---|---|---|
| `plans/current.md` | Transient session work | Concise, mutates throughout session | Active task steps. Deleted on `/complete-feature`. |
| `research/*.md` | Findings + sources | Medium, cite sources | Key findings, code examples |
| `reviews/*.md` | Issues + locations | Terse, file:line refs | Bullets with code refs |
| `filebox/*` | Raw data | N/A | JSON, logs, samples |
| `handoff.md` | Session-to-session handoff | Terse, exact commands and paths | One per scope, overwritten by `/wrap`. See `## Handoff`. |

`tasks.md` vs `plans/current.md`: tasks.md is durable, archived with feature, OpenSpec-style checkbox list with auto-status from checkbox %. `plans/current.md` is transient scratchpad — what you're currently handling, mutates throughout the session, deleted on `/complete-feature`.

`context/discoveries.md` is hook-appended, never hand-authored — `workspace_session_end.py` appends extracted findings, the SessionStart hook replays the last 20 lines. It lands as `candidate` and gets triaged in `/review-memory`. Write `context/patterns.md` for curated architectural patterns.

## Handoff

The contract between a session that is ending and the next one. One file per scope, overwritten in place, never dated or numbered:

| Scope | Path |
|---|---|
| feature `in_progress` | `features/{name}/handoff.md` |
| no feature | `.giantmem/handoff.md` |

Written by `/wrap`, or when the user asks for a handoff. It is a doc for the user alone, so absolute paths, branch names, and IDs belong in it; the shared-docs rule does not apply. It holds what a cold session needs that the feature docs don't already say. Link to feature docs instead of copying them.

Frontmatter: `type: handoff`, `status: ready`, `feature:` or `repo:`, `lifecycle: durable`, `created`, `updated`.

Sections in fixed order; omit empty ones:

```markdown
## Open Questions for User   only when there are any
## Open edges                blockers, gaps, and items the user waived during /wrap
## Start here                numbered, exact commands; step 1 runs as-is
## State
- repos: absolute path, branch, HEAD sha, pushed or not, MR !N and its state
- running: process, how it was started, port/pid, left up or torn down, restart command
- doit: list name, pending count, next 3 by do-order
## Decisions                 non-obvious choices, one line of why each
## External docs             absolute paths / URLs of docs outside this dir (Desktop, other repos, Notion)
## Paste prompt              fenced block: the complete prompt for the new session
```

Resume: a session that finds a `status: ready` handoff reads it first, and treats it as a snapshot. It verifies repo and MR state against git before acting, then sets `status: done` once it has acted on `Start here`. A `ready` handoff whose `updated` is older than the branch's last commit is stale; say so instead of following it.

## Frontmatter requirement

Every `.md` and `.yaml` artifact MUST start with YAML frontmatter:

```yaml
---
type: {one of: source-spec | delta-spec | proposal | design | tasks | plan | research | review | notes | pattern | facts | handoff}
feature: {name}              # for feature-scoped artifacts
repo: {repo-name}            # for repo-level artifacts (one of feature or repo)
status: {draft | ready | done | blocked | stale}
lifecycle: {durable | candidate | deprecated}    # SHOULD; default durable
scope: {scope_id}            # optional; overrides repo→scope membership
domain: {name}               # optional
created: YYYY-MM-DD
updated: YYYY-MM-DD
publish: true | false        # optional; true = deliverable, publishes on write; false = never
kind: {quickstart | cheatsheet | overview | arch | runbook | guide | explainer | report}  # optional; any `auto` kind publishes on write
notion: {page url}           # written by notion-publish after first push; presence = upsert
notion_synced: {iso ts}      # written by notion-publish; do not hand-edit
---
```

Notion publish: policy, not questions. Local file is canonical for every class; Notion is a mirror in the page tree `Claude Artifacts / repo / worktree? / feature? / doc`. Never ask whether to publish.

| Class | Types or kinds | Notion |
|---|---|---|
| state | tasks, plan, facts, notes, handoff, delta-spec, source-spec, history, precompact, workspace, filebox, prompt, domain, machine indexes | never |
| model memory | pattern, discoveries | opt-in `publish: true` |
| working prose | proposal, design, research, review, grill-run, grill-final | on explicit user ask (`on_request` in `config/notion-publish.yaml`) |
| deliverable | quickstart, cheatsheet, overview, arch, runbook, guide, explainer, report | on write (`auto` list); hook `notion_publish_nudge.py` emits `publish now`, model runs `notion-publish` same turn |

User asks for a deliverable kind → write it at the normal routed path with `publish: true` (or `kind:`), let the hook fire. Notion-side edits do not flow back; republish overwrites the page; the user backports by hand.

Preview: mdlive only when the user asks (preview / render / open). After writing a `.md`, return its path.

JSON artifacts (`meta.json`) get the same keys at top level (no `---` fences).

Lifecycle stage rules:
- `durable` (default): human-authored, scaffolded by `/new-feature`, accumulated source-specs. Never auto-pruned.
- `candidate`: AI-captured discoveries / research / mid-session notes. Surface in `/review-memory` for promote → durable / demote → deprecated.
- `deprecated`: kept on disk but excluded from stale reports.

Backfill legacy files:
- Frontmatter keys: `python3 ~/dev/giant-tooling/workspace/scripts/backfill_frontmatter.py`
- Lifecycle only: `python3 ~/dev/giant-tooling/workspace/scripts/backfill_lifecycle.py`

## Anti-patterns — DO NOT

- "Phase 1:", "Step 1 of 5:", progress tracking headers
- "Work in Progress", "Status:", progress banners
- Verbose summaries of what you're about to do
- Dump everything into `plans/` — use correct directory
- Filler text ("Great!", "Let's begin by...")
- Multiple files when one suffices

## File naming

- snake_case: `auth_flow_plan.md`, `replica_lag_analysis.md`
- Suffix indicates type: `*_plan.md`, `*_analysis.md`, `*_api.md`

## Format examples

**features/_index.md — CORRECT:**

```markdown
| Feature | Status | Beta Flag | Builds On | FE |
|---|---|---|---|---|
| [jwt-session-cookie](jwt-session-cookie/) | complete | `enable_jwt_session_cookie` | - | - |
| [jwt-session-enforcement](jwt-session-enforcement/) | in_progress | `enable_jwt_session_enforcement` | jwt-session-cookie | FE: jwt-session-enforcement |
```

**features/{name}/facts.md — CORRECT:**

```markdown
## Identifiers
beta_flag: enable_jwt_session_enforcement
config_keys:
  - JWT_SESSION_SECRET

## Test Commands
docker compose run --rm test pytest -s --disable-warnings tests/services/auth_session/
```

**context/patterns.md — CORRECT:**

```markdown
## Session Layer
- Redis key format: `rc_session_{user_id}_{store_id}_{session_id}`
- Lookup by session_id: use SCAN with pattern `rc_session_*_*_{session_id}`

## Gotchas
- SQLAlchemy session isolation causes stale cache in tests
```

**plans/current.md — CORRECT:**

```markdown
# Active: Add session lookup endpoint

## Steps
1. Add get_session_by_session_id to session_store.py
2. Create API resource
3. Register route
```

**WRONG — verbose phase tracking:**

```markdown
## Phase 1: Research and Planning
- [ ] Review current authentication flow
## Progress Tracking
- Started: 2026-01-15
- Status: In Progress
```

## On /ws-init

Organize loose files in `.giantmem/` root:

1. Move `.md` files (except `WORKSPACE.md`):
   - `*_analysis.md`, `*_research.md` → `research/`
   - `*_plan.md`, `*_design.md` → `plans/`
   - `*_endpoints.md`, `*_api.md` → `context/`
   - `*_review.md` → `reviews/`
   - Other `.md` → `context/` (default)

2. Move non-markdown (`.json`, `.yaml`, `.sh`) → `filebox/`

## Concise output

When user asks for "concise":

| Ask | Format |
|---|---|
| Question | 1-2 sentences + up to 5 bullets |
| Analysis | Max 2 short paragraphs + up to 5 summary bullets |
| Pros and cons | 3-4 sentence summary + table (not lists) |

For workspace docs: same constraints. Bullets/tables over prose. Code snippets over prose explanations. No filler paragraphs.

## Scope + Lifecycle (cross-repo memory unit)

Two new pieces let memory cross worktrees + age gracefully:

| Concept | Lives at | Holds |
|---|---|---|
| **scope registry** | `~/.giantmem-global/scopes.yaml` | Named scopes (`personal`, `recharge-customcheckout`, ...) → list of repo names. Artifact membership = repo match OR explicit `scope:` frontmatter. Edit via `giantmem scope init|list|show|add-repo|sync`. |
| **lifecycle** | per-artifact frontmatter `lifecycle:` | `durable` (default, never auto-prunes), `candidate` (review pending), `deprecated` (kept but excluded from default packs). Walk candidates via `/review-memory`. |
| **retention tier** | derived from `type:` | Tier A (proposal/design/source-spec) never expires; Tier B (pattern/research/notes) 180d; Tier C (tasks/plan/review/facts/delta-spec) 90d. Surfaced by `giantmem artifact stale --days 0`. |

Filter by scope or lifecycle anywhere artifacts are listed:

```bash
giantmem artifact list --scope personal -t delta-spec
giantmem artifact list --lifecycle candidate
giantmem artifact stale --days 0           # tier policy, no fixed day cutoff
giantmem artifact stale --days 0 --all-repos --apply   # auto-deprecate stale candidates untouched for 180d (SessionEnd hook runs this daily)
giantmem access top --limit 10             # most-touched artifacts in last 30d
giantmem access prune --older-than 180d    # trim access_log table
```

MCP `find_artifact` accepts `scope` + `lifecycle` args (same semantics). MCP `get_stats` returns counts by type/lifecycle/status/repo plus recent access metrics.

## Finding artifacts (cross-repo)

Before grepping or scanning, use the typed index:

| Need | Command |
|---|---|
| Current-repo, filter by type/status/feature/domain | `giantmem artifact list -t delta-spec -s ready` |
| Cross-repo / cross-worktree | `giantmem artifact list --repo all -t proposal` |
| Include archived snapshots | append `--include-archived` |
| Interactive picker (fzf) | `gma` (default `--repo all`) |
| One artifact full content | `giantmem artifact show <id>` |
| Forgotten / stale | `giantmem artifact stale [--all-repos]` |
| From inside Claude (no shell) | MCP tools `find_artifact`, `get_artifact`, `list_features_with_artifacts` |

Rebuild the index after any feature command writes new files: `giantmem artifact reindex` (already wired into `/new-feature` and `/complete-feature`).

Full search cheat sheet (typed + content + interactive + MCP): [`docs/gma-search.md`](docs/gma-search.md).

## Caveman compression on first write (HUMAN DOCS)

Any human-readable doc I generate MUST be written in caveman style on the FIRST pass. Do NOT write verbose-first then compress. Do NOT wait for a PostToolUse hook to nudge. Add `<!-- caveman:compressed -->` directly after frontmatter so downstream hooks do not re-nudge.

**Applies to (caveman from the start):**
- Every `.md` under `.giantmem/**` — proposals, facts, notes, research, filebox, plans, reviews, mr-description, kaizens
- Repo `docs/` runbooks, design docs, ADRs, post-mortems intended for the team (not the wider world)
- Ad-hoc explainers I write at the user's request when they aren't being shipped externally

**Style:**
- Drop articles (a/an/the), filler (just/really/basically/actually/simply), pleasantries (sure/certainly/of course), hedging
- Fragments OK. Short synonyms (big not extensive, fix not "implement a solution for")
- Tables, boxes-and-arrows, diagrams preferred over prose for flow/architecture explanations
- Code blocks, paths, commands, error text: preserve EXACTLY — never caveman these

**Mermaid sidecar (`.mmd`):**
- Whenever a `.md` doc contains a mermaid diagram, ALSO write a sibling `.mmd` file with just the mermaid source (no fences, no frontmatter). Same basename, same directory.
- Example: `multi-tool-synthesis-explainer.md` (with ```` ```mermaid ```` block) ships alongside `multi-tool-synthesis-explainer.mmd` (raw flowchart source).
- Why: Google Docs / Confluence don't render mermaid inline. User runs `mmdc -i file.mmd -o file.png` to produce an image for paste. Sidecar removes the manual extraction step. Notion renders mermaid fences natively; `notion-publish` passes them through untouched.
- If a doc has multiple diagrams, write `<basename>-1.mmd`, `<basename>-2.mmd`, etc., in source order.
- Keep `.md` mermaid block AND `.mmd` file in sync — edits to one must update the other in the same write batch.

**Does NOT apply (write normally — caveman would degrade these):**
- Published `README.md` files and externally-shipped guides — keep casual senior-dev-to-colleague voice per `### Tone` above
- Delta-specs (`features/{name}/specs/{domain}/spec.md`) and source-specs (`.giantmem/specs/{domain}/spec.md`) — RFC 2119 normative keywords (MUST / MUST NOT / SHOULD / MAY) and GIVEN/WHEN/THEN scenarios MUST stay exact. Caveman the surrounding prose only.
- Code comments — already governed by `## Code Comment Rules`
- Commit messages — governed by `caveman-commit` skill
- LLM-system prompts (e.g. `MULTI_SYNTHESIS_PROMPT`, `ANALYTICS_SYNTHESIS_PROMPT`) — wording is tuned for model behavior, do not paraphrase

Explicit caveman invocation (`/caveman <file>`, "caveman this MR/PR/doc") ALWAYS applies to the named target, overriding any exemption above except code syntax / specs / system-prompt wording.
