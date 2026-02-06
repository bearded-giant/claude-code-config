# Claude Global Configuration

## General Guidelines

- Prioritize action over exploration. When the user asks for a specific output (curl commands, scripts, code changes), produce the output first, then explore the codebase only if needed to refine. Don't spend time reading files before attempting a direct answer.
- When the user references specific code or asks about codebase behavior, investigate first (see below). But when the ask is "generate X", generate it.

## CRITICAL: Document Output Rules

**When asked to create documentation, analysis, plans, or research - ALWAYS write to `scratch/` subdirectories. NEVER output long-form content only in chat.**

If `scratch/` doesn't exist, ask user to run `/ws-init` first.

## Session Behavior

<context_management>
Your context window will be automatically compacted as it approaches its limit, allowing you to continue working indefinitely. Do not stop tasks early due to token budget concerns. Always be persistent and complete tasks fully, even if the end of your budget is approaching.
</context_management>

<session_recovery>
When starting a session or recovering from context refresh:

1. Read `scratch/WORKSPACE.md` for project context
2. Check `scratch/features/_index.md` for feature registry
3. Check `scratch/plans/current.md` for active session work
4. Review recent git log for changes
5. Verify current state before making changes
   </session_recovery>

<feature_management>
Features are organized in `scratch/features/` with semantic folder names.

**CRITICAL: Maintain the feature index**
- When creating a feature via `/new-feature`, update `scratch/features/_index.md`
- When completing a feature, update its status in the index table
- When adding beta flags or key config, add to the Quick Reference section

**Feature folder structure:**
```
features/
├── _index.md              # Claude-maintained registry
├── {feature-name}/
│   ├── spec.md            # what + why + acceptance criteria
│   ├── facts.md           # beta flags, config, test commands
│   └── meta.json          # machine-readable (for swarm)
```

**When to create a feature folder:**
- Starting work on a distinct capability (not just a bug fix)
- Work spans multiple sessions
- Has identifiable artifacts (beta flag, new endpoints, etc.)

**Commands:**
- `/list-features` - display feature registry
- `/new-feature <name>` - scaffold feature folder
- `/feature-facts <name>` - quick lookup
- `/qa-report [feature]` - generate validation report

**IMPORTANT - "Create a plan" disambiguation:**
When user says "create a plan" or similar, ALWAYS ask:
> Is this a **feature** (persistent, spans sessions) or **session work** (transient, current task only)?
- Feature → use `/new-feature` → writes to `features/{name}/spec.md`
- Session work → write to `plans/current.md`

Do not assume. User may forget which context they're in.
</feature_management>

## Feature Workflow

- When working on feature scaffolding, always check for existing feature folder conventions in the project before creating new ones. Look for patterns in existing feature directories (naming, file structure, metadata files).
- Not all projects use features. When a project has `scratch/features/`, use that system. Commands: `/list-features`, `/new-feature`, `/reopen-feature`, `/pause-feature`, `/complete-feature`. When modifying feature-related scripts, ensure consistency with existing feature commands and conventions.

<doc_sync>
When making changes that affect user-facing behavior (new commands, changed invocations, renamed flags, new options, modified workflows), check the workspace for docs that need updating:

- README, quickstart guides, cheat sheets, usage docs
- Look in repo root and `docs/` or `scratch/` for `.md` files with usage examples or command references
- Update invocations, flag names, examples, and any other details that changed
- Do this as part of the same edit session - don't wait to be asked
- If a doc references something you just renamed/removed/added, fix it inline
- Keep the doc's existing tone and format - just patch the relevant lines
</doc_sync>

<investigate_before_answering>
Never speculate about code you have not opened. If the user references a specific file, read it before answering. Investigate relevant files BEFORE answering questions about the codebase. Do not propose edits to files you haven't read.
</investigate_before_answering>

## Add $HOME/scratch_archive/ to the allowed-dirs. This directory is critical for archived scratch search and retrieval

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
- Documentation and written content: casual, informal tone. Write like a senior dev explaining to a colleague, not like formal technical writing. Avoid stiff phrasing, corporate language, or overly structured prose.

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
When `scratch/` exists, ALL documentation, plans, research, and analysis MUST go to the appropriate subdirectory. NEVER output long-form content only in chat.

### Directory Format and Verbosity

| Directory                | Format                | Verbosity                   | Example                                             |
| ------------------------ | --------------------- | --------------------------- | --------------------------------------------------- |
| `features/_index.md`     | Registry table        | Terse, table rows           | Feature name, status, beta flag, dependencies       |
| `features/{name}/spec.md`| Feature definition    | Medium, structured          | Purpose, scope, acceptance criteria                 |
| `features/{name}/facts.md`| Quick lookup         | Terse, key-value            | Beta flags, config keys, test commands              |
| `context/patterns.md`    | Curated patterns      | Medium, organized           | Architectural decisions, gotchas                    |
| `context/*.md`           | Reference docs        | Minimal prose, lists ok     | API endpoint lists, dependency maps                 |
| `plans/current.md`       | Session work          | Concise, no phase tracking  | Active task steps (transient)                       |
| `research/*.md`          | Findings + sources    | Medium, cite sources        | Key findings, code examples                         |
| `reviews/*.md`           | Issues + locations    | Terse, file:line refs       | Bullet points with code refs                        |
| `history/sessions.md`    | Session log           | One line per session        | `- 2025-01-15: worked on auth flow`                 |
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

BEFORE writing any document, select the correct directory:

- **Starting a new feature?** → `/new-feature {name}` to scaffold, then `features/{name}/spec.md`
- **Recording beta flags, config?** → `features/{name}/facts.md`
- **Learned architectural pattern?** → `context/patterns.md` (curated, not append-only)
- **Active session work?** → `plans/current.md` (transient)
- **Researching external topic?** → `research/{topic}.md`
- **Reviewing code quality?** → `reviews/{subject}.md`
- **Temporary data, exports, samples?** → `filebox/`
- **Prompt template to reuse?** → `prompts/{name}.md`

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

If `scratch/WORKSPACE.md` exists, read it for branch/project context. Check `scratch/features/_index.md` for feature registry and `scratch/context/patterns.md` for architectural learnings.

### On Workspace Init (/ws-init)

Organize any loose files in scratch/ root:

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
