# Claude Global Configuration

## General Guidelines

- Prioritize action over exploration. When the user asks for a specific output (curl commands, scripts, code changes), produce the output first, then explore the codebase only if needed to refine. Don't spend time reading files before attempting a direct answer.
- When the user references specific code or asks about codebase behavior, investigate first (see below). But when the ask is "generate X", generate it.

## CRITICAL: Document Output Rules

**When asked to create documentation, analysis, plans, or research - ALWAYS write to `.giantmem/` subdirectories. NEVER output long-form content only in chat.**

If `.giantmem/` doesn't exist, ask user to run `/ws-init` first.

## Session Behavior

<context_management>
Your context window will be automatically compacted as it approaches its limit, allowing you to continue working indefinitely. Do not stop tasks early due to token budget concerns. Always be persistent and complete tasks fully, even if the end of your budget is approaching.
</context_management>

<session_recovery>
When starting a session or recovering from context refresh:

1. Read `.giantmem/WORKSPACE.md` for project context
2. Check `.giantmem/features/features.json` for feature cache (or `_index.md` as fallback)
3. Identify the active feature (status `in_progress` in features.json)
4. Check `.giantmem/domains/_index.json` for domain knowledge base (load relevant domain JSONs for active feature)
5. If active feature exists, check `features/{active-feature}/plans/current.md` for session work; otherwise check `.giantmem/plans/current.md`
6. Review recent git log for changes
7. Verify current state before making changes
   </session_recovery>

<feature_management>
Features are organized in `.giantmem/features/` with semantic folder names.

**CRITICAL: Maintain the feature cache and index**
- Every feature command (new, start, pause, complete, reopen) MUST update `.giantmem/features/features.json`
- Also update `.giantmem/features/_index.md` for human-readable registry
- When adding beta flags or key config, add to the Quick Reference section

**Feature folder structure:**
```
features/
├── features.json          # feature cache (all commands read/write this)
├── _index.md              # Claude-maintained registry (human-readable)
├── {feature-name}/
│   ├── spec.md            # what + why + acceptance criteria
│   ├── facts.md           # beta flags, config, test commands
│   ├── meta.json          # machine-readable (for swarm)
│   ├── plan.md            # implementation plan (created by /plan-feature)
│   ├── plan_context.json  # which domains informed this plan
│   ├── plans/             # session work scoped to this feature
│   │   └── current.md
│   ├── research/          # research scoped to this feature
│   ├── reviews/           # code reviews scoped to this feature
│   └── filebox/           # data, exports, samples for this feature
```

**Domain knowledge base:**
```
domains/
├── _index.json            # registry of all domain explorations
├── {domain-name}.json     # LLM-consumable exploration of a code domain
```
Domains are repo-level, not feature-scoped. Created by `/plan-feature`, updated by `/update-domains` and `/complete-feature`. Load relevant domain JSONs at session start instead of re-reading code.

**When to create a feature folder:**
- Starting work on a distinct capability (not just a bug fix)
- Work spans multiple sessions
- Has identifiable artifacts (beta flag, new endpoints, etc.)

**Commands:**
- `/list-features` - display feature registry
- `/new-feature <name>` - scaffold feature folder (auto-detects pending vs in_progress)
- `/plan-feature [name] [--refresh]` - explore code domains (auto-derived), output domain JSONs, draft implementation plan
- `/list-domains [--verbose]` - show all indexed domains from the knowledge base
- `/search-domains <query> [--load]` - search domain JSONs for files, functions, patterns, concepts
- `/update-domains [domains] [--all-stale]` - refresh domain JSONs after code changes
- `/feature-facts <name>` - quick lookup
- `/qa-report [feature]` - generate validation report

**IMPORTANT - "Create a plan" disambiguation:**
When user says "create a plan" or similar, ALWAYS ask:
> Is this a **feature** (persistent, spans sessions) or **session work** (transient, current task only)?
- Feature → use `/new-feature` → writes to `features/{name}/spec.md`
- Session work → if active feature exists, write to `features/{active-feature}/plans/current.md`; otherwise `plans/current.md`

Do not assume. User may forget which context they're in.

**Feature-scoped output routing:**

When a feature has status `in_progress` in `features.json`, it is the **active feature**. All session output that would normally go to top-level `.giantmem/` subdirectories MUST instead go inside the active feature's directory:

| Without active feature | With active feature `{name}` |
|------------------------|------------------------------|
| `.giantmem/plans/current.md` | `.giantmem/features/{name}/plans/current.md` |
| `.giantmem/research/{topic}.md` | `.giantmem/features/{name}/research/{topic}.md` |
| `.giantmem/reviews/{subject}.md` | `.giantmem/features/{name}/reviews/{subject}.md` |
| `.giantmem/filebox/*` | `.giantmem/features/{name}/filebox/*` |

**Always global (never feature-scoped):**
- `domains/` - repo-level code knowledge, not feature-scoped
- `history/` - session log spans all features
- `prompts/` - reusable templates
- `context/patterns.md` - curated architectural patterns (repo-level)
- `WORKSPACE.md`, `features/_index.md`, `features.json`

Create the subdirectories inside the feature folder on first write (don't require them to exist upfront).

When no feature is `in_progress`, use top-level `.giantmem/` subdirectories as before.
</feature_management>

## Feature Workflow

- When working on feature scaffolding, always check for existing feature folder conventions in the project before creating new ones. Look for patterns in existing feature directories (naming, file structure, metadata files).
- Not all projects use features. When a project has `.giantmem/features/`, use that system. Commands: `/list-features`, `/new-feature`, `/plan-feature`, `/update-domains`, `/reopen-feature`, `/pause-feature`, `/complete-feature`. When modifying feature-related scripts, ensure consistency with existing feature commands and conventions.

<doc_sync>
When making changes that affect user-facing behavior (new commands, changed invocations, renamed flags, new options, modified workflows), check the workspace for docs that need updating:

- README, quickstart guides, cheat sheets, usage docs
- Look in repo root and `docs/` or `.giantmem/` for `.md` files with usage examples or command references
- Update invocations, flag names, examples, and any other details that changed
- Do this as part of the same edit session - don't wait to be asked
- If a doc references something you just renamed/removed/added, fix it inline
- Keep the doc's existing tone and format - just patch the relevant lines
</doc_sync>

<investigate_before_answering>
Never speculate about code you have not opened. If the user references a specific file, read it before answering. Investigate relevant files BEFORE answering questions about the codebase. Do not propose edits to files you haven't read.
</investigate_before_answering>

## Add $HOME/giantmem_archive/ to the allowed-dirs. This directory is critical for archived workspace search and retrieval

## IMPORTANT: Configuration Management

<stow_dotfiles_rules>
This system uses GNU stow for dotfiles management.

- Most dotfiles are managed in ~/dotfiles/ and symlinked using GNU stow
- NEVER edit files in ~/.config or other home directory locations directly
- Always edit the source files in their respective repositories
- Structure: ~/dotfiles/{package}/.config/{app}/ or ~/dotfiles/{package}/.{config-file}
- Examples:
  - Claude config: ~/dev/claude-code-config/ (symlinked to ~/.claude via stow)
  - Wezterm config: ~/dotfiles/wezterm/.config/wezterm/ (symlinked to ~/.config/wezterm)
  - Shell config: ~/dotfiles/shell/.bashrc (symlinked to ~/.bashrc)
    </stow_dotfiles_rules>

## Communication Style

- No emojis in any code, scripts, or documentation
- Chat responses: direct and technical
- Documentation and written content: casual, informal tone by default. Write like a senior dev explaining to a colleague, not like formal technical writing. Avoid stiff phrasing, corporate language, or overly structured prose. Only use formal tone when the user explicitly asks for it.
- No bullet points in long-form or external docs (READMEs, guides, writeups). Use numbered lists, prose, tables, or other structures instead. Bullet lists make docs look like slide decks. Internal workspace docs (`.giantmem/`) and chat responses follow the Concise Output Rules below instead.
- **Wizard-style prompts**: When features/skills need multiple inputs (branch name, base branch, etc.), present them as numbered menu options one at a time, not as a combined free-text question. User selects 1/2/3 etc.

## Concise Output Rules

When the user asks for "concise" output or summary, follow these format constraints:

| Ask Type | Format |
|----------|--------|
| Question | 1-2 sentences + up to 8 bullet points of detail |
| Analysis | Max 2 paragraphs + summary bullet points |
| Pros and cons | 4-6 sentence summary + table (not lists) |

**Workspace docs (`.giantmem/`):** "Concise" means the same constraints as chat responses apply to markdown files:
- Bullet points and tables over prose
- Code snippets as examples over prose explanations
- No filler paragraphs between sections

## Code Comment Rules

<code_comment_rules>
When writing or editing code (excluding tests):

- Only add comments for crucial or complex logic
- Remove any superfluous comments (obvious operations, self-documenting code)
- All comments must be lowercase
- Never add docstrings unless explicitly requested
- Tests are exempt - comments are fine there
  </code_comment_rules>

## Languages & Conventions

- Primary languages: Python for scripts/tools, Shell/Bash for automation, Markdown for documentation
- When creating new files, default to Python unless the user specifies otherwise
- Always use existing project style conventions

## Scripting Conventions

- When implementing CLI flags or command modifications, check the existing argument parsing pattern in the script (argparse, getopts, etc.) and follow it exactly
- Show a usage example after implementing

## API URL Conventions

- API URLs must use snake_case, not hyphens (kebab-case)
- Example: `/api/admin/auth/validate_credentials` (correct) not `/api/admin/auth/validate-credentials` (incorrect)

## Test Creation and Modification

- must run any tests you create or update to ensure they pass
- if how to run for a given project is not clear check the CLAUDE.md file for the project or ask the user for clarification

## Test Running

- tests are ran with docker
- `docker compose run --rm test pytest -s --disable-warnings {test file}`
- Example: `docker compose run test pytest -s --disable-warnings tests/services/merchant_auth/test_merchant_two_factor_integration.py`

## Working Modes

### Mode: "sync to preprod"

When user says this phrase, enter auto-sync mode where:

- After any file edit/update that's NOT in .gitignore
- Automatically sync the file to preprod using scp
- Show a brief confirmation like "→ Synced: customcheckout/api/blueprint.py"
- Continue in this mode until user says "stop syncing" or similar

Example workflow:

```
User: "working local sync to preprod"
Claude: Entering auto-sync mode. Files will sync to preprod on save.

[After editing a file]
Claude: [makes the edit]
→ Synced: customcheckout/api/merchant_two_factor_auth.py
```

## Smart Agent Triggers

**Proactively use the Task tool with specialized agents when:**

- **Searching for code patterns across multiple files**: Use Task agent to search efficiently
- **Refactoring >5 files**: Use Task agent with batched operations for consistency
- **Debugging test failures**: Use Task agent to run tests and analyze failures systematically
- **Complex multi-step operations**: Use Task agent when a task requires 4+ coordinated steps
- **Finding all usages of a function/class**: Use Task agent for comprehensive codebase search
- **Implementing features across layers**: Use Task agent to modify model, API, and frontend together

Examples of when to automatically trigger:

- User: "Find all places where we call validateCredentials" → Use Task agent
- User: "Rename this function everywhere" → Use Task agent
- User: "Why is this test failing?" → Use Task agent to investigate
- User: "Add this field to the model and API" → Use Task agent for multi-layer changes

## Git Rules

<git_rules>

- never commit unless explicitly asked to do so
- never add Claude Code attribution or Co-Authored-By lines to commits
- never create git commits that are more than a casual short blurb. no multi-line details
- do not auto-push to origin. confirm first
- return all curls and shell scripts as oneliners
  </git_rules>

## Workspace Output Rules

<workspace_output_rules>
When `.giantmem/` exists, ALL documentation, plans, research, and analysis MUST go to the appropriate subdirectory. NEVER output long-form content only in chat.

**CRITICAL: Feature-scoped routing applies here.** When a feature is `in_progress`, plans, research, reviews, and filebox output go inside the active feature directory. See the feature-scoped output routing table in `<feature_management>` for exact paths.

### Directory Format and Verbosity

**Global directories (always at `.giantmem/` level):**

| Directory                | Format                | Verbosity                   | Example                                             |
| ------------------------ | --------------------- | --------------------------- | --------------------------------------------------- |
| `features/_index.md`     | Registry table        | Terse, table rows           | Feature name, status, beta flag, dependencies       |
| `features/{name}/spec.md`| Feature definition    | Medium, structured          | Purpose, scope, acceptance criteria                 |
| `features/{name}/facts.md`| Quick lookup         | Terse, key-value            | Beta flags, config keys, test commands              |
| `features/{name}/plan.md`| Implementation plan   | Concise, actionable         | Steps, file paths, function names                   |
| `features/{name}/plan_context.json`| Domain linkage | Machine-readable         | Which domains informed this plan                    |
| `domains/_index.json`    | Domain registry       | Machine-readable            | Domain names, key paths, feature refs               |
| `domains/{name}.json`    | Domain exploration    | Machine-readable, detailed  | Entry points, key files, architecture, gotchas      |
| `context/patterns.md`    | Curated patterns      | Medium, organized           | Architectural decisions, gotchas                    |
| `context/*.md`           | Reference docs        | Minimal prose, lists ok     | API endpoint lists, dependency maps                 |
| `history/sessions.md`    | Session log           | One line per session        | `- 2025-01-15: worked on auth flow`                 |
| `prompts/*.md`           | Prompt templates      | N/A                         | Reusable prompt templates                           |

**Feature-scoped directories (inside active feature when one exists, otherwise at `.giantmem/` level):**

| Directory                | Format                | Verbosity                   | Example                                             |
| ------------------------ | --------------------- | --------------------------- | --------------------------------------------------- |
| `plans/current.md`       | Session work          | Concise, no phase tracking  | Active task steps (transient)                       |
| `research/*.md`          | Findings + sources    | Medium, cite sources        | Key findings, code examples                         |
| `reviews/*.md`           | Issues + locations    | Terse, file:line refs       | Bullet points with code refs                        |
| `filebox/*`              | Raw data              | N/A                         | JSON, logs, samples                                 |

NOTE: `context/discoveries.md` is deprecated. Use `context/patterns.md` for curated architectural patterns instead.

### Anti-Patterns - DO NOT

- Write "Phase 1:", "Step 1 of 5:", or progress tracking headers
- Add "Work in Progress", "Status:", or progress banners
- Create verbose summaries of what you're about to do
- Dump everything into `plans/` - use the correct directory
- Add motivational or filler text ("Great!", "Let's begin by...")
- Create multiple files when one suffices
- Add section headers in discoveries.md (it's append-only log lines)

### Directory Selection

BEFORE writing any document, determine the correct path:

1. Check if a feature is `in_progress` in `features.json` → that is the **active feature**
2. If active feature exists, feature-scoped outputs go to `features/{active-feature}/` subdirs
3. If no active feature, use top-level `.giantmem/` subdirs

**Always global:**
- **Starting a new feature?** → `/new-feature {name}` to scaffold, then `features/{name}/spec.md`
- **Planning a feature?** → `/plan-feature` to explore code domains and draft plan
- **Recording beta flags, config?** → `features/{name}/facts.md`
- **Explored a code domain?** → `domains/{domain}.json` (created by `/plan-feature`, updated by `/update-domains`)
- **Learned architectural pattern?** → `context/patterns.md` (curated, not append-only)
- **Prompt template to reuse?** → `prompts/{name}.md`

**Feature-scoped (inside active feature dir when one exists):**
- **Active session work?** → `{feature}/plans/current.md` or `plans/current.md`
- **Researching external topic?** → `{feature}/research/{topic}.md` or `research/{topic}.md`
- **Reviewing code quality?** → `{feature}/reviews/{subject}.md` or `reviews/{subject}.md`
- **Temporary data, exports, samples?** → `{feature}/filebox/` or `filebox/`

### Format Examples

**features/_index.md - CORRECT:**

```markdown
| Feature | Status | Beta Flag | Builds On |
|---------|--------|-----------|-----------|
| [jwt-session-cookie](jwt-session-cookie/) | complete | `enable_jwt_session_cookie` | - |
| [jwt-session-enforcement](jwt-session-enforcement/) | in_progress | `enable_jwt_session_enforcement` | jwt-session-cookie |
```

**features/{name}/facts.md - CORRECT:**

```markdown
## Identifiers
beta_flag: enable_jwt_session_enforcement
config_keys:
  - JWT_SESSION_SECRET

## Test Commands
docker compose run --rm test pytest -s --disable-warnings tests/services/auth_session/
```

**context/patterns.md - CORRECT:**

```markdown
## Session Layer
- Redis key format: `rc_session_{user_id}_{store_id}_{session_id}`
- Lookup by session_id: use SCAN with pattern `rc_session_*_*_{session_id}`

## Gotchas
- SQLAlchemy session isolation causes stale cache in tests
```

**plans/current.md - CORRECT (transient session work):**

```markdown
# Active: Add session lookup endpoint

## Steps
1. Add get_session_by_session_id to session_store.py
2. Create API resource
3. Register route
```

**WRONG - verbose phase tracking:**

```markdown
## Phase 1: Research and Planning
- [ ] Review current authentication flow
## Progress Tracking
- Started: 2025-01-15
- Status: In Progress
```

### On Session Start

If `.giantmem/WORKSPACE.md` exists, read it for branch/project context. Check `.giantmem/features/features.json` for feature cache (or `_index.md` as fallback) and `.giantmem/context/patterns.md` for architectural learnings. Identify the active feature (status `in_progress`) and use its subdirectories for all feature-scoped output during the session.

### On Workspace Init (/ws-init)

Organize any loose files in .giantmem/ root:

1. Move `.md` files (except WORKSPACE.md) to appropriate subdirs:
   - `*_analysis.md`, `*_research.md` → `research/`
   - `*_plan.md`, `*_design.md` → `plans/`
   - `*_endpoints.md`, `*_api.md` → `context/`
   - `*_review.md` → `reviews/`
   - Other `.md` files → `context/` (default)

2. Move non-markdown files (`.json`, `.yaml`, `.sh`) → `filebox/`

### File Naming

- Use snake_case: `auth_flow_plan.md`, `replica_lag_analysis.md`
- Suffix indicates type: `*_plan.md`, `*_analysis.md`, `*_api.md`

</workspace_output_rules>
