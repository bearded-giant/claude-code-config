# CLAUDE.md

Before answering any question, reason step by step. Many questions contain subtle constraints, hidden assumptions, or trick aspects invisible to surface-level pattern matching. Verify the answer you are about to give is sensible given ALL details, not just the most salient one.

Global behavior for `~/.claude` (stowed from `~/dev/claude-code-config`). Repo internals, hook pipeline, key commands → see `README.md`.

## General Guidelines

Decision rule for action-vs-exploration:

| Ask shape | Default |
|---|---|
| "Generate X" / "write Y" / "give me a curl for Z" | Action first. Produce output, refine after. Do not pre-read files. |
| "Why does X" / "How does Y work" / "What's wrong with Z" | Investigate first. Read referenced files. No speculation. |
| User names a specific file or symbol | MUST Read it before proposing edits. |

<context_management>
Context auto-compacts as it approaches limits. Continue indefinitely. Do not stop early for token concerns. Be persistent, complete tasks fully.
</context_management>

<session_recovery>
On session start or context refresh, IF files exist, read in order:

1. `.giantmem/WORKSPACE.md`
2. `.giantmem/features/features.json` — find active feature (status `in_progress`)
3. Active feature's `plans/current.md` if exists, else `.giantmem/plans/current.md`

Skip steps where file missing. Do not stat every directory ritually.
</session_recovery>

## Feature & Workspace Output

Two on-demand skills carry the heavy rules:

- **`feature-management` skill** — feature folder lifecycle, "create a plan" disambiguation, feature-scoped output routing. Auto-fires on feature commands and "create a plan".
- **`workspace-rules` skill** — `.giantmem/` directory selection, format, verbosity, anti-patterns, file naming. Auto-fires before any `.giantmem/**` write.

Trust the skills. Don't reload these rules into root context.

Quick reminder of the only invariants worth keeping in root:
- When feature has status `in_progress`, plans/research/reviews/filebox go inside that feature dir
- Never write to repo `docs/` unprompted — goes to `.giantmem/context/` or active feature's `research/`
- "Create a plan" → MUST AskUserQuestion (feature vs session work) before any file write

<doc_sync>
Triggers (any → MUST run sync in same edit batch):
- Renamed/removed/added a slash command, skill, agent, or hook
- Renamed/removed/added a CLI flag, env var, or config key
- Changed an invocation signature

Procedure:
1. `grep -r '<old-name>'` across repo root, `docs/`, `.giantmem/`, `commands/`, `agents/`, `skills/`, `README*`
2. Patch each ref inline — keep existing tone
3. Same commit as the rename/removal

Skip if change is internal (private helper rename, no external surface).
</doc_sync>

<investigate_before_answering>
Never speculate about code you have not opened. If user references a specific file, read it. Investigate relevant files BEFORE answering. Do not propose edits to files you haven't read.
</investigate_before_answering>

`$HOME/giantmem_archive/` is allowed-dir — critical for archive search and retrieval.

## Stow Dotfiles — Rules

System uses GNU stow. NEVER edit files in `~/.config` or other home locations directly — edit the source repo and re-stow.

- Claude config: `~/dev/claude-code-config/` → `~/.claude`
- Wezterm: `~/dotfiles/wezterm/.config/wezterm/`
- Shell: `~/dotfiles/shell/.bashrc`
- Tmux: `~/dotfiles/tmux/.config/tmux/`

## Communication Style

### Tone

- Chat: direct, technical, terse
- Long-form docs (READMEs, guides, writeups): casual, informal. Senior dev to colleague. No corporate phrasing, no stiff structure
- Formal only when user explicitly asks

### Format

- NEVER use emojis in code, scripts, docs (any context)
- Long-form / external docs: NO bullet lists. Use numbered lists, prose, or tables
- Workspace docs (`.giantmem/`) and chat: bullets allowed per concise rules

### Wizard-Style Prompts

When feature/skill needs multiple inputs (branch, base branch, etc.), MUST present as numbered menu, ONE question at a time. User selects 1/2/3. Never combine into a single free-text question.

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

## Scripting Conventions

- CLI flags: check existing arg parsing pattern (argparse, getopts) and follow exactly
- Show usage example after implementing

## API URL Conventions

snake_case, not kebab-case. Example: `/api/admin/auth/validate_credentials` (correct), not `/api/admin/auth/validate-credentials`.

## Test Creation and Modification

- MUST run any tests created or modified to confirm pass before reporting done
- If run command unclear: read project CLAUDE.md or ask. Do not guess

## Agent Tool Use

<agent_triggers>
MUST spawn Task agent (Explore subagent) when:
- Searching unknown pattern across > 5 files
- Mapping a flow that requires > 3 sequential greps/reads
- Finding all usages of a symbol across the repo

MUST spawn Task agent (debugger subagent) when user reports stack trace, test failure, or unexplained behavior requiring multi-file trace.

MUST spawn Task agent for refactors touching > 5 files (batched edits, consistency check).

MUST NOT spawn agents for:
- Single-file edits with known path
- One-shot bash commands
- Direct Read of a file the user named
</agent_triggers>

## Git Rules

<git_rules>
- never amend existing commits unless explicitly asked
- never force-push to main/master/stage
- commit + push without re-confirmation when user invokes `/commit`, `/commit-push-pr`, says "ship it", "commit and push", or after explicit "yes commit"
- use `caveman-commit` format for messages (conventional commits, subject ≤50 chars, body only for non-obvious why)
- use `create-mr-description` skill for MR/PR descriptions
- never add Claude Code attribution or Co-Authored-By
- one-liner curls and shell scripts in chat
- commit messages: casual short blurb. no multi-line details unless breaking change, security fix, or data migration
</git_rules>

## Discord Bot

Bot config and access policy: `~/.claude/channels/discord/`. Inbound DMs don't surface yet — use `fetch_messages` on DM channel `1485390190523584542`, reply via `reply`. Full setup in discord plugin docs.

## Concise Output Rules

| Ask Type | Format |
|---|---|
| Question | 1-2 sentences + up to 5 bullets |
| Analysis | Max 2 short paragraphs + up to 5 summary bullets |
| Pros and cons | 3-4 sentence summary + table (not lists) |

Workspace docs: same constraints. See `workspace-rules` skill for full output rules.
