# Claude Global Configuration

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
2. Check `scratch/plans/current.md` for active work
3. Review recent git log for changes
4. Verify current state before making changes
   </session_recovery>

<investigate_before_answering>
Never speculate about code you have not opened. If the user references a specific file, read it before answering. Investigate relevant files BEFORE answering questions about the codebase. Do not propose edits to files you haven't read.
</investigate_before_answering>

## Add $HOME/scratch_archive/ to the allowed-dirs. This directory is critical for archived scratch search and retrieval

## IMPORTANT: Configuration Management

<stow_dotfiles_rules>
This system uses GNU stow for dotfiles management.

- All dotfiles are managed in ~/dotfiles/ and symlinked using GNU stow
- NEVER edit files in ~/.config, ~/.claude, or other home directory locations directly
- Always edit the source files in ~/dotfiles/
- Structure: ~/dotfiles/{package}/.config/{app}/ or ~/dotfiles/{package}/.{config-file}
- Examples:
  - Claude config: ~/dotfiles/claude-code/.claude/ (symlinked to ~/.claude)
  - Wezterm config: ~/dotfiles/wezterm/.config/wezterm/ (symlinked to ~/.config/wezterm)
  - Shell config: ~/dotfiles/shell/.bashrc (symlinked to ~/.bashrc)
    </stow_dotfiles_rules>

## Communication Style

- No emojis in any code, scripts, or documentation
- Keep responses direct and technical

## Code Comment Rules

<code_comment_rules>
When writing or editing code (excluding tests):

- Only add comments for crucial or complex logic
- Remove any superfluous comments (obvious operations, self-documenting code)
- All comments must be lowercase
- Never add docstrings unless explicitly requested
- Tests are exempt - comments are fine there
  </code_comment_rules>

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
| `context/discoveries.md` | Append-only log lines | Terse, one line per finding | `- 2025-01-15 14:30: [gotcha] tests require docker` |
| `context/*.md`           | Reference docs        | Minimal prose, lists ok     | API endpoint lists, dependency maps                 |
| `plans/current.md`       | Actionable steps      | Concise, no phase tracking  | Numbered steps, files to modify                     |
| `research/*.md`          | Findings + sources    | Medium, cite sources        | Key findings, code examples                         |
| `reviews/*.md`           | Issues + locations    | Terse, file:line refs       | Bullet points with code refs                        |
| `history/sessions.md`    | Session log           | One line per session        | `- 2025-01-15: worked on auth flow`                 |
| `filebox/*`              | Raw data              | N/A                         | JSON, logs, samples                                 |

Categories for discoveries: architecture, pattern, gotcha, dependency, convention, entry, config

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

- **Learned something about the codebase?** → `context/discoveries.md` (append one line)
- **Planning implementation steps?** → `plans/current.md` or `plans/{feature}.md`
- **Researching external topic?** → `research/{topic}.md`
- **Reviewing code quality?** → `reviews/{subject}.md`
- **Temporary data, exports, samples?** → `filebox/`
- **Prompt template to reuse?** → `prompts/{name}.md`

### Format Examples

**discoveries.md - CORRECT:**

```
- 2025-01-15 10:22: [architecture] services use dependency injection via containers.py
- 2025-01-15 10:25: [gotcha] celery tasks must be imported in __init__.py to register
```

**discoveries.md - WRONG:**

```
## Session Discoveries

### Architecture Findings

During my exploration of the codebase, I discovered that the services layer uses...
```

**plans/current.md - CORRECT:**

```
# Add JWT Refresh Endpoint

## Files
- api/auth/routes.py - add /refresh endpoint
- services/auth.py - add refresh_token() method
- tests/test_auth.py - add refresh tests

## Steps
1. Add refresh_token service method
2. Create POST /api/auth/refresh route
3. Add tests for token refresh flow
```

**plans/current.md - WRONG:**

```
# Implementation Plan: JWT Refresh Token Feature

## Phase 1: Research and Planning
- [ ] Review current authentication flow
- [ ] Document existing token structure

## Phase 2: Implementation
### Step 2.1: Service Layer
We will begin by implementing...

## Progress Tracking
- Started: 2025-01-15
- Status: In Progress
- Estimated completion: ...
```

### On Session Start

If `scratch/WORKSPACE.md` exists, read it for branch/project context. Check `scratch/context/discoveries.md` for prior codebase learnings.

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
