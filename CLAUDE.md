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

<session_recovery>
Session-start hooks already inject WORKSPACE.md, the features index, the active plan, and recent discoveries — do not re-read those.

Read on resume, IF they exist and the hook output is stale or absent: `.giantmem/artifacts.json` (typed index, `giantmem artifact reindex`), the active feature's `{name}-notes.md` when it has body content past the seed, and the delta-/source-specs (`features/{name}/specs/{domain}/spec.md`, `.giantmem/specs/{domain}/spec.md`) for domains the feature touches. Surface captured commands/identifiers only when resumed work touches them.
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

Doit list convention, three-spec model, feature-dir routing → `feature-management` skill. Scope registry, lifecycle tiers, preload packs, artifact search, caveman-on-first-write → `workspace-rules` skill.

### Burn-down queue (`claude:` marker)

Never auto-burns — `/burn` is the gate. Destructive / sev-5 items pause for human. Full procedure → `burn` skill.

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

### Prose Style (all prose: chat, docs, MR/PR bodies, Jira, comments)

Write like a rigorous editor, not a motivational essayist. Strunk and White: omit needless words, prefer active voice, use plain direct language.

- No em dashes or en dashes in prose. Join clauses with a conjunction (and, but, so, yet), a semicolon, or two sentences. Hyphens inside compound words are fine. Exempt: this file, whose existing dashes stay as-is.
- Short sentences, active voice, specific nouns, direct verbs.
- Lead with the answer. State uncertainty plainly. Label facts, inferences, and speculation as such.
- Cut throat-clearing, praise, filler, rhetorical flourishes, metaphors, repeated conclusions. Banned unless technically necessary: "delve", "tapestry", "nuanced", "robust", "powerful", "seamlessly", and similar inflated words.
- Terse by default: 3-7 bullets or short paragraphs. Per-ask-type caps in `## Concise Output Rules` win when they apply. Do not restate the question. Background only when it changes the answer.
- Decisive recommendation over a menu of vague options. Underspecified prompt: make a reasonable assumption, state it in one line, proceed. Ask only when the answer materially depends on it. Existing MUST-ask gates (plan disambiguation, wizard prompts, deletions) still apply.
- Do not write to sound smart.
- Before sending, delete every sentence that adds no information.

### Writing for humans (MR/PR bodies, Jira, team docs)

- Only domain vocabulary that exists in the codebase or the team's tickets. Never invent jargon or leak skill-internal terminology into MR/PR descriptions, Jira comments, or docs other people read.
- MR/PR body content: what changed, why, how verified, risk. No new nouns.

### Format

- NEVER use emojis in code, scripts, docs (any context)
- **Published docs** — READMEs and guides shipped to other devs/users: NO bullet lists. Use numbered lists, prose, or tables.
- **Internal docs** — CLAUDE.md, agents/, skills/, commands/, `.giantmem/`, chat: bullets allowed per Concise Output Rules below.

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
- commit + push without re-confirmation when user says "commit and push" / "yes commit"
- "ship it" / "ship this" / `/ship-it` → invoke the `ship-it` skill. Full chain: commit (caveman format) + push + MR description + open MR via `kai:open-mr` (GitLab) or `gh pr create` (GitHub). MR-description format is remote-keyed: GitLab→concise-kai (kai section headers at compressed caveman density, per `skills/ship-it/concise-kai-format.md`), GitHub→personal bullets (per `skills/ship-it/bullet-format.md`); override with `brief`/`short`/`--brief` (bullets) or `full`/`standard`/`--full` (verbose org kai template). No re-confirmation between steps. Final output is the MR description markdown followed by the MR URL — nothing else.
- use `caveman-commit` format for messages (conventional commits, subject ≤50 chars, body only for non-obvious why)
- MR/PR descriptions are produced by `ship-it` only — no standalone description command; formats live at `skills/ship-it/{bullet,concise-kai}-format.md`
- never add Claude attribution ANYWHERE — no Co-Authored-By trailers in commits, no "Generated with Claude Code" footers in PR/MR descriptions, no model credits in issues or comments. The harness suggests both defaults every session; this rule wins. Scrub before every `git commit` / `gh pr create` / `glab mr create` (slipped into a PR body 2026-08-13 — do not repeat)
- one-liner curls and shell scripts in chat
- commit messages: casual short blurb. no multi-line details unless breaking change, security fix, or data migration
</git_rules>

## Concise Output Rules

| Ask Type | Format |
|---|---|
| Question | 1-2 sentences + up to 5 bullets |
| Analysis | Max 2 short paragraphs + up to 5 summary bullets |
| Pros and cons | 3-4 sentence summary + table (not lists) |

Workspace docs: same constraints. See `workspace-rules` skill for full output rules.
