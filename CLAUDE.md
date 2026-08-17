# CLAUDE.md

Global behavior for `~/.claude` (stowed from `~/dev/claude-code-config`). Repo internals, hook pipeline, key commands → see `README.md`.

## Precedence

Rules in this file are personal invariants. When a project CLAUDE.md / AGENTS.md / INSTRUCTIONS.md conflicts with a rule here, THIS file wins — follow it and flag the conflict in chat in one line. Exception: project build/test/lint commands and code-style conventions — project wins there. Critical subset re-injected every prompt by `hooks/standing_constraints.py` from `config/standing-constraints.md` — keep both in sync when editing scope/execution rules here.

## General Guidelines

Decision rule for action-vs-exploration:

| Ask shape | Default |
|---|---|
| "Generate X" / "write Y" / "give me a curl for Z" | Action first. Produce output, skip scaffolding reads. |
| "Why does X" / "How does Y work" / "What's wrong with Z" | Investigate first. Read referenced files. No speculation. |
| User names a specific file or symbol | MUST Read it before proposing edits. |

Across all rows: never propose edits to a file you have not read in this session.

### Strategy visibility

User reviews strategy, not tool-call streams. Make the path inspectable early and cheap to intercept:

- Multi-step or investigative work: announce approach in 1-3 lines BEFORE executing — path chosen, access paths/tools, expected blast radius.
- Mid-task pivot (new tool, new hypothesis, widening scope, switching access path): state the pivot in ONE line before acting on it. A silent pivot reads as drift.
- Two failed attempts at the same approach → STOP. Present evidence + ranked options. Never silently try a third variation of the same idea.

### Gitignored files are editable

`.gitignore` controls what git *tracks*, not what you may *edit*. A gitignored file — or any file inside an ignored directory — is editable exactly like a tracked file. There is no instruction anywhere that bars editing ignored files; do not invent one. Read, edit, create, and delete them under the same gates as everything else (read-before-edit, confirm before destructive/outward-facing). Never stop, skip, or ask permission *solely because* a path is gitignored — that is not a reason to halt.

## Scope of Changes (blast radius)

The task defines the blast radius. Nothing outside it gets touched.

- No drive-by edits: refactors, comment cleanup, config tweaks, doc fixes outside the named task — mention them, don't do them.
- Team-shared agent config — git-tracked `CLAUDE.md` / `AGENTS.md` / `INSTRUCTIONS.md` / checked-in `.claude/**` in any repo other than `claude-code-config` / `dotfiles` — NEVER edit as a side effect of another task. Propose the diff in chat; edit only when the user explicitly directed that exact change. `guard_protected_paths.py` PreToolUse hook gates this mechanically (ask-prompt).
- Never create a git worktree unless asked. Work in the current worktree; run artifacts go under the current repo's `.giantmem/`.
- Deletions: list targets, wait for confirm, then delete.

## Artifact vs Execution

"Give me / write / generate X" = output the text, fenced. Do NOT run it, wrap it in a shell command, or execute it against any system unless the user says "run it".

- Queries: raw SQL/GraphQL text in a fenced block. No psql/run_sql wrappers, no MCP execution, unless asked.
- A named access path is a contract: user says GraphQL endpoint / `hq.py` / scripted export → use exactly that. Never substitute an equivalent (psql, run_sql, Snowflake MCP, direct REST). Named path fails → stop and report; no silent fallback.

## Code is truth — docs and comments are not

Markdown docs, code comments, docstrings, and `.giantmem/` notes are snapshots from the moment they were written. They drift. Treat them as hints about *intent*, never as authority on *current behavior*.

Authoritative sources, in order:

1. The code itself — function bodies, route handlers, schemas, control flow
2. Live data — actual HTTP responses, DB rows, log lines, observed ticket IDs / job states the user shared
3. Tests — assert what the code currently does (still verify the test isn't itself stale)
4. Docs / comments / `.md` files / docstrings — LAST. Only quote when you've already verified the claim against 1–3.

Forbidden moves:

- Citing a doc/comment as evidence for *current* behavior without verifying the code matches
- Quoting a docstring's "today returns stub" / "not yet implemented" / "once X ships" / "TODO" framing as a present-tense fact
- Building a plan or recommendation on top of doc claims you have not cross-checked against the code
- Repeating a doc's prediction ("once edge N ships") as if the predicate is still unresolved — check whether it already shipped

When a doc and the code disagree:

- The code wins. Say so explicitly to the user.
- Offer to refresh the stale doc/comment in the same turn, or flag it as a follow-up.
- Never silently "average" the two or hedge ("the doc says X but maybe…"). State the divergence directly.

This applies to MR descriptions, proposals, kaizens, runbooks, ADRs, frontmatter — every text artifact. The artifact is a snapshot; the running system is the truth.

Corollary — do not author the staleness you would later have to ignore. When editing or generating code, NEVER write comments / docstrings / module banners that describe *current* functional behavior, response shapes, return values, request/response flow, "today returns X" / "ships dark" / "once Y lands" framing, fallback chains, or any other claim that the code itself already states. The reader will read the code; your comment will rot the moment the code changes. See `## Code Comment Rules` for the only permitted comment shape (the *why* of a non-obvious choice, one line). If you find yourself describing *what* a function does in a docstring, delete the docstring.

<context_management>
Context auto-compacts as it approaches limits. Continue indefinitely. Do not stop early for token concerns. Be persistent, complete tasks fully.
</context_management>

<session_recovery>
On session start or context refresh, IF files exist, read in order:

1. `.giantmem/WORKSPACE.md`
2. `.giantmem/features/features.json` — find active feature (status `in_progress`)
3. Active feature's `plans/current.md` if exists, else `.giantmem/plans/current.md`
4. Active feature's `{name}-notes.md` if it has body content past the seed (frontmatter + `<!-- living cheat sheet ... -->` comment alone counts as empty — skip). Surface relevant captured commands/identifiers in chat only when resumed work touches them; do not dump the whole file or surface the seed comment.
5. `.giantmem/artifacts.json` (typed artifact index, built by `giantmem artifact reindex`) — gives proposal/delta-spec/tasks/design state per feature. Session-start hook already injects an `ACTIVE ARTIFACTS` block summarizing this; the file itself is the authority when the hook output is stale or absent.
6. Active feature's `specs/{domain}/spec.md` (delta-specs) and `.giantmem/specs/{domain}/spec.md` (source-specs) for the domains the feature touches.

Skip steps where the file is missing. If step 1's file is missing, do not check steps 2-6.
</session_recovery>

## Feature & Workspace Output

Two skills carry the full rules and auto-fire on triggers:
- **`feature-management`** — feature folder lifecycle, "create a plan" disambiguation, feature-scoped output routing
- **`workspace-rules`** — `.giantmem/` directory selection, format, verbosity, anti-patterns, file naming

Root invariants (apply before skill fires, and as fallback if skill misses):
- When a feature has status `in_progress`, plans/research/reviews/filebox go inside that feature dir
- Never write to repo `docs/` unprompted — route to `.giantmem/context/` or the active feature's `research/`
- "Create a plan" → MUST AskUserQuestion (feature vs session work) before any file write
- Every `.md` / `.yaml` artifact under `.giantmem/` MUST have YAML frontmatter (`type:`, `status:`, `feature:` or `repo:`). JSON artifacts use the same keys at top level. Backfill legacy files via `python3 ~/dev/giant-tooling/workspace/scripts/backfill_frontmatter.py`.
- Every `.md` / `.json` / `.yaml` artifact under `.giantmem/` SHOULD carry `lifecycle: durable | candidate | deprecated`. Defaults to `durable`. AI-generated discoveries / research land as `candidate` and get reviewed via `/review-memory`. Backfill via `python3 ~/dev/giant-tooling/workspace/scripts/backfill_lifecycle.py`.

### Todos → doit (repo / feature list)

When multi-step work surfaces items the USER must act on outside the current turn (review an MR/doc, run a script later, follow up, decide), MUST `AskUserQuestion` ONCE: offer to create/update the session's doit list. Fires in OR out of a feature — bare-repo work counts (you work outside features often). Never auto-write todos. Never ask per-item — batch the cluster into one ask showing proposed items + buckets so user can edit first.

- List = repo-qualified name: `{repo}-{feature}` (e.g. `claude-code-config-oauth-ttl`); worktree parent dir ending `-wt` prepends → `cc-wt-local-dev-runner-{feature}`; no feature → bare `{repo}`. Reuse if exists, else `create_list`. `daily` only on explicit request. Derivation → `feature-management` skill.
- Bucket → doit `priority`: critical→`critical`, urgent→`urgent`, important→`important`, default→omit. Classify by urgency + critical-path.
- Number each item in text (`1. …`, `2. …`) = do-order / critical-path sequence — the visible priority signal (doit has no ordinal field user sees).
- Item gets a `description` only when it carries a doc link, exact script/command, or identifier (MR URL, ticket, shop_id) — preserve those EXACTLY, redact secrets. Plain post-it items get none.
- Update existing list: `list_todos` first, dedupe vs current items, append new, continue numbering from max. No daily mirror.
- Session start: `doit_session_prime` hook surfaces this session's list name + whether it exists. If it exists, `list_todos` it and surface pending `claude:` items. Re-derive when cwd / worktree / feature changes mid-session.

Full convention + procedure → `feature-management` skill.

### Burn-down queue (`claude:` marker)

Any doit todo whose text starts `claude:` is assigned to the model. `/burn` drains them from one list, priority-first (critical→urgent→important→default), claiming each via `in_progress`, working it end-to-end under normal git/confirm gates, then auto-`complete_todo` + appending a DONE record (local `date` timestamp + ≤6 bullets of what was done; original note preserved). Target list = repo-qualified, worktree-aware (`{repo}-{feature}`, worktree parent `-wt` prepended → `cc-wt-local-dev-runner-{feature}`, no feature → bare `{repo}`); `--list` overrides. In_progress = the claim lock, so 4-6 parallel sessions don't double-grab.

- Assign: type `claude: {task}` in doit. Put doc link / script / id in the todo's note for context.
- Run: `/burn` (one drain) or `/loop 10m /burn` (periodic). Flags: `--list`, `--priority`, `--max`, `--dry-run`.
- Never auto-burns — `/burn` is the gate. Destructive / sev-5 items pause for human.
- When the model proposes a feature-todo batch, items it can execute get the `claude:` prefix; user-only items don't.

Full procedure → `burn` skill.

## Scope + Lifecycle (cross-repo memory unit)

Two new pieces let memory cross worktrees + age gracefully:

| Concept | Lives at | Holds |
|---|---|---|
| **scope registry** | `~/.giantmem-global/scopes.yaml` | Named scopes (`personal`, `recharge-customcheckout`, ...) → list of repo names. Artifact membership = repo match OR explicit `scope:` frontmatter. Edit via `giantmem scope init|list|show|add-repo|sync`. |
| **lifecycle** | per-artifact frontmatter `lifecycle:` | `durable` (default, never auto-prunes), `candidate` (review pending), `deprecated` (kept but excluded from default packs). Walk candidates via `/review-memory`. |
| **retention tier** | derived from `type:` | Tier A (proposal/design/source-spec) never expires; Tier B (pattern/research/notes) 180d; Tier C (tasks/plan/review/facts/delta-spec) 90d. Surfaced by `giantmem artifact stale --days 0`. |
| **preload packs** | `~/.claude/config/preload_packs.yaml` | Ordered layers driving session-start hook output. Layers can inline `static_files`, run `giantmem artifact list` with filters, and resolve `{active_scope}` / `{active_feature}` / `{repo}` / `{branch}` placeholders. |

Filter by scope or lifecycle anywhere artifacts are listed:

```bash
giantmem artifact list --scope personal -t delta-spec
giantmem artifact list --lifecycle candidate
giantmem artifact stale --days 0           # tier policy, no fixed day cutoff
giantmem access top --limit 10             # most-touched artifacts in last 30d
giantmem access prune --older-than 180d    # trim access_log table
```

MCP `find_artifact` accepts `scope` + `lifecycle` args (same semantics). MCP `get_stats` returns counts by type/lifecycle/status/repo plus recent access metrics.

## Three-Spec Model (per-feature → repo-truth)

| Artifact | Lives at | Holds |
|---|---|---|
| `proposal` | `features/{name}/proposal.md` | intent + scope + approach (NOT behavior) |
| `delta-spec` | `features/{name}/specs/{domain}/spec.md` | `## ADDED / MODIFIED / REMOVED Requirements` blocks. Each `### Requirement:` carries one or more `#### Scenario:` (GIVEN / WHEN / THEN, RFC 2119). |
| `source-spec` | `.giantmem/specs/{domain}/spec.md` | accumulated behavior across all completed features. Written ONLY by `/complete-feature` merging delta-specs in. Never hand-edit mid-feature. |

Legacy `features/{name}/spec.md` is a symlink → `proposal.md` (30-day muscle-memory back-compat from the `migrate_spec_to_proposal.py` rename).

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

<doc_sync>
Triggers (any → MUST run sync in same edit batch):
- Renamed/removed/added a slash command, skill, agent, or hook
- Renamed/removed/added a CLI flag, env var, or config key
- Changed the args, flags, return shape, or trigger phrase of a public command/skill/script

Procedure:
1. `grep -r '<old-name>'` across repo root, `docs/`, `.giantmem/`, `commands/`, `agents/`, `skills/`, `README*`
2. Patch each ref inline — keep existing tone
3. Same commit as the rename/removal

Skip if change is internal (private helper rename, no external surface).
</doc_sync>

## Stow Dotfiles — Rules

System uses GNU stow. NEVER edit files in `~/.config` or other home locations directly — edit the source repo and re-stow.

- Claude config: `~/dev/claude-code-config/` → `~/.claude`
- Wezterm: `~/dotfiles/wezterm/.config/wezterm/`
- Shell: `~/dotfiles/shell/.bashrc`
- Tmux: `~/dotfiles/tmux/.config/tmux/`

## Communication Style

### Tone

- Chat and internal docs (CLAUDE.md, agents, skills, commands, `.giantmem/`): direct, technical, terse
- Published docs (READMEs, guides shipped to other devs/users): casual, informal — senior dev to colleague. No corporate phrasing, no stiff structure.
- Formal only when user explicitly asks

### Writing for humans (MR/PR bodies, Jira, team docs)

- Only domain vocabulary that exists in the codebase or the team's tickets. Never invent jargon or leak skill-internal terminology into MR/PR descriptions, Jira comments, or docs other people read.
- MR/PR body content: what changed, why, how verified, risk. No new nouns.

### Format

- NEVER use emojis in code, scripts, docs (any context)
- **Published docs** — READMEs and guides shipped to other devs/users: NO bullet lists. Use numbered lists, prose, or tables.
- **Internal docs** — CLAUDE.md, agents/, skills/, commands/, `.giantmem/`, chat: bullets allowed per Concise Output Rules below.

### Caveman compression on first write (HUMAN DOCS)

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
- Why: Google Docs / Notion / Confluence don't render mermaid inline. User runs `mmdc -i file.mmd -o file.png` to produce an image for paste. Sidecar removes the manual extraction step.
- If a doc has multiple diagrams, write `<basename>-1.mmd`, `<basename>-2.mmd`, etc., in source order.
- Keep `.md` mermaid block AND `.mmd` file in sync — edits to one must update the other in the same write batch.

**Does NOT apply (write normally — caveman would degrade these):**
- Published `README.md` files and externally-shipped guides — keep casual senior-dev-to-colleague voice per `### Tone` above
- Delta-specs (`features/{name}/specs/{domain}/spec.md`) and source-specs (`.giantmem/specs/{domain}/spec.md`) — RFC 2119 normative keywords (MUST / MUST NOT / SHOULD / MAY) and GIVEN/WHEN/THEN scenarios MUST stay exact. Caveman the surrounding prose only.
- Code comments — already governed by `## Code Comment Rules`
- Commit messages — governed by `caveman-commit` skill
- LLM-system prompts (e.g. `MULTI_SYNTHESIS_PROMPT`, `ANALYTICS_SYNTHESIS_PROMPT`) — wording is tuned for model behavior, do not paraphrase

Explicit caveman invocation (`/caveman <file>`, "caveman this MR/PR/doc") ALWAYS applies to the named target, overriding any exemption above except code syntax / specs / system-prompt wording.

### Wizard-Style Prompts

When feature/skill needs multiple inputs (branch, base branch, etc.), MUST present as numbered menu, ONE question at a time. User selects 1/2/3. Never combine into a single free-text question.

### Open Questions Placement (ALWAYS)

Any LLM-generated doc with unresolved questions for the user MUST put them at the TOP under `## Open Questions for User`. Before frontmatter body, TOC, summary, intent, or any other section. Applies to proposals, designs, plans, research, reviews, kaizen docs, MR descriptions, ad-hoc analysis — every doc.

- Format: numbered list, each item marked `[BLOCKING]` or `[non-blocking]`
- Remove the section once all items resolved (don't leave empty stub)
- If a template scaffolds the section by default, leave it in until populated/resolved — buried questions get missed

```markdown
## Open Questions for User

1. [BLOCKING] Auth token expiry — 1h or 24h?
2. [non-blocking] Redis vs Postgres for session store?
```

Supersedes any per-skill placement rule. Also enforced in `workspace-rules` skill for `.giantmem/` docs.

## Code Comment Rules

<code_comment_rules>
Default: write ZERO comments. Code self-documents via names.

Add a comment ONLY when WHY is non-obvious: hidden constraint, subtle invariant, workaround for specific bug, behavior that would surprise a reader. If removing the comment wouldn't confuse a future reader, don't write it.

Forbidden patterns (do not emit, even once):
- Comments restating WHAT (`# loop over users`, `# return result`, `# helper for X`)
- Section banners (`# === Setup ===`, `# --- helpers ---`)
- Task/PR/ticket refs (`# added for X`, `# fix for ticket-123`, `# used by Y`)
- Trailing inline comments after assignments (`x = foo()  # get foo`)
- Docstrings — never add unless user explicitly asks
- Multi-line comment blocks or multi-paragraph docstrings — one short line max
- "Removed X" / "TODO: cleanup" / backwards-compat placeholder comments

Style when warranted: lowercase, one line, state WHY not WHAT.

Tests exempt — comments fine there.
</code_comment_rules>

## Languages & Conventions

- Primary: Python (scripts/tools), Shell/Bash (automation), Markdown (docs)
- New files: default Python unless user specifies otherwise
- Use existing project style conventions

## Code Intelligence (LSP)

LSP tool enabled for Python (pyright), TypeScript, Rust, Lua. All ops take `filePath` + 1-based `line` + `character`, so locate the symbol with Grep/Read first, then call LSP for navigation.

Use LSP for:
- `goToDefinition` / `goToImplementation` — jump to source
- `findReferences` — all usages across workspace
- `workspaceSymbol` — find where a symbol is defined by name
- `documentSymbol` — list symbols in a file (faster than reading whole file)
- `hover` — type/signature without opening the file
- `prepareCallHierarchy` → `incomingCalls` / `outgoingCalls` — call graph (prepare first, then in/out)

Use Grep/Glob for text patterns LSP can't see: comments, strings, config values, log messages, regex matches across files.

Before renaming a symbol or changing a function signature, MUST run `findReferences` to enumerate call sites.

Diagnostics (type errors, missing imports) are NOT in this LSP tool. Run the `py-check` skill after Python edits and `ts-check` after TS/TSX edits before reporting done.

## Scripting Conventions

- CLI flags: check existing arg parsing pattern (argparse, getopts) and follow exactly
- Show usage example after implementing
- Complex quoting (nested-quote curls, JSON payloads, heredoc-in-heredoc): write to a scratchpad script file and execute the file. Inline quoting monsters trip the permission parser and waste turns.
- Deletion: `rm` is allowlisted — use it directly (after confirm-first rule for non-scratch targets). Do not fall back to `shutil.rmtree` workarounds.

## API URL Conventions

snake_case, not kebab-case. Example: `/api/admin/auth/validate_credentials` (correct), not `/api/admin/auth/validate-credentials`.

## Test Creation and Modification

- MUST run any tests created or modified to confirm pass before reporting done
- If run command unclear: read project CLAUDE.md or ask. Do not guess

## Agent Tool Use

<agent_triggers>
MUST spawn Task agent (Explore subagent) when:
- An initial grep returns > 5 hits that each need follow-up Reads
- A trace requires > 3 sequential greps/reads to map
- Finding all usages of a symbol across the repo

MUST spawn Task agent (debugger subagent) when user reports a stack trace, test failure, or unexplained behavior requiring a multi-file trace.

MUST spawn Task agent for refactors expected to touch > 5 files (batched edits, consistency check).

MUST NOT spawn agents for:
- Single-file edits with a known path
- One-shot bash commands
- Direct Read of a file the user named
</agent_triggers>

## Git Rules

<git_rules>
- never amend existing commits unless explicitly asked
- never force-push to main/master/stage
- commit + push without re-confirmation when user invokes `/commit`, `/commit-push-pr`, or says "commit and push" / "yes commit"
- "ship it" / "ship this" / `/ship-it` → invoke the `ship-it` skill. Full chain: commit (caveman format) + push + MR description + open MR via `kai:open-mr` (GitLab) or `gh pr create` (GitHub). MR-description format is remote-keyed: GitLab→concise-kai (kai section headers at compressed caveman density, per `skills/ship-it/concise-kai-format.md`), GitHub→personal bullets (per `skills/ship-it/bullet-format.md`); override with `brief`/`short`/`--brief` (bullets) or `full`/`standard`/`--full` (verbose org kai template). No re-confirmation between steps. Final output is the MR description markdown followed by the MR URL — nothing else.
- use `caveman-commit` format for messages (conventional commits, subject ≤50 chars, body only for non-obvious why)
- MR/PR descriptions are produced by `ship-it` only — no standalone description command; formats live at `skills/ship-it/{bullet,concise-kai}-format.md`
- never add Claude attribution ANYWHERE — no Co-Authored-By trailers in commits, no "Generated with Claude Code" footers in PR/MR descriptions, no model credits in issues or comments. The harness suggests both defaults every session; this rule wins. Scrub before every `git commit` / `gh pr create` / `glab mr create` (slipped into a PR body 2026-08-13 — do not repeat)
- one-liner curls and shell scripts in chat
- commit messages: casual short blurb. no multi-line details unless breaking change, security fix, or data migration
</git_rules>

## Discord Bot

Bot config and access policy: `~/.claude/channels/discord/`. Inbound DMs don't surface yet — use `fetch_messages` on DM channel `1485390190523584542`, reply via `reply`. Full setup in discord plugin docs.

### Acknowledge inbound channel messages immediately

When a Discord channel message arrives (any `<channel source="discord" ...>` event), call the `react` MCP tool with 👀 on that `message_id` **before** doing anything else. This gives the sender instant visual confirmation that you received the request. Then proceed with the work and reply normally via `reply` when results are ready. Skip the react only for trivial responses where the reply lands in <2s anyway.

### Slash commands from Discord channel messages

Discord messages arrive as channel notifications (not as prompts), so `/<command>` text typed in Discord is NOT auto-dispatched by claude's slash command parser. When an inbound Discord channel message starts with `/<name>` followed by optional args, treat it as a request to run that slash command:

1. Look up the command file. Search order:
   - `~/.claude/commands/<name>.md`
   - `~/.claude/plugins/**/commands/<name>.md`
   - `~/.claude/skills/<name>/SKILL.md` (skill auto-fired by command name)
2. Read the file. Execute its instructions in the current conversation, substituting args from the Discord message into the command's `$ARGUMENTS` / arg placeholders.
3. Built-in commands (`/exit`, `/clear`, `/resume`, `/init`, `/login`) can't be triggered this way — they're hardcoded in the claude CLI, not file-backed. Reply via the `reply` tool explaining the limitation.
4. If no command file matches, reply via the `reply` tool — don't silently ignore.

## Concise Output Rules

| Ask Type | Format |
|---|---|
| Question | 1-2 sentences + up to 5 bullets |
| Analysis | Max 2 short paragraphs + up to 5 summary bullets |
| Pros and cons | 3-4 sentence summary + table (not lists) |

Workspace docs: same constraints. See `workspace-rules` skill for full output rules.
