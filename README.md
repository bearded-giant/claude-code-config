# BG's Claude Code Configuration

My personal Claude Code configuration with custom commands, hooks, agents, skills, and plugins. Managed via GNU stow from `~/dev/claude-code-config` and symlinked to `~/.claude`.

## Dependencies

This config is **not** standalone. It requires a companion repo for workspace lifecycle, archive search, and worktree management.

| Repo | What it provides |
|------|-----------------|
| [claude-code-config](https://github.com/bearded-giant/claude-code-config) (this repo) | CLAUDE.md, hooks, commands, agents, skills, settings, MCP configs |
| [giant-tooling](https://github.com/bearded-giant/giant-tooling) | Workspace library, giantmem search/archive/sessions, worktree helpers |

The workspace library (`workspace-lib.sh`) lives in giant-tooling and is symlinked into this repo at `lib/workspace/`. Session hooks, slash commands, and archive scripts all depend on it.

## Install

```bash
git clone https://github.com/bearded-giant/claude-code-config.git
cd claude-code-config
./install.sh
```

Clone it wherever you want. The install script detects its own location and clones giant-tooling as a sibling directory. To put giant-tooling somewhere else:

```bash
./install.sh --tooling-dir ~/my/path/giant-tooling
```

The install script handles everything:

1. Checks prerequisites (git, stow, python3)
2. Clones [giant-tooling](https://github.com/bearded-giant/giant-tooling) as a sibling directory if missing
3. Creates symlink: `lib/workspace/` -> `giant-tooling/workspace/`
4. Runs stow to wire `~/.claude`, then seeds `~/.claude/settings.json` with `sync_settings.py`
5. Prints any shell env lines you need to add
6. Verifies the install, including the giantmem CLI from giant-tooling, and exits non-zero if anything is missing

After install, restart Claude Code.

### Shell setup

The install script will tell you what to add. Typically:

```bash
export GIANT_TOOLING_DIR="$HOME/dev/giant-tooling"
source "$GIANT_TOOLING_DIR/workspace/workspace-lib.sh"
```

### Prerequisites

Required: git, stow, python3 (3.10+), Claude Code CLI, and the giantmem CLI (run `make bootstrap` in giant-tooling, which installs it to `~/.local/bin/giantmem`)

Optional: fzf (interactive search picker), bat (search previews)

## Structure

```
.claude/
  CLAUDE.md              # global instructions (loaded every session)
  settings.json          # permissions, hooks, MCP servers, env vars
  commands/              # 40+ slash commands
  agents/                # 10 specialized agent definitions
  hooks/                 # Python/JS lifecycle hooks
  scripts/               # utility scripts (session-search, sync-preprod)
  skills/                # multi-file skill definitions
  plugins/               # plugin config and runtime
  mcp/                   # MCP server configs
  lib/workspace/         # -> giant-tooling/workspace/ (symlink)
  docs/                  # reference docs
```

## Hook Pipeline

All hooks are Python (stdlib only) except statusline (Node.js) and `claude_tmux_state.sh` (bash, since it runs on every tool call). Configured in `settings.json`.

| Event | Hook | Purpose |
|-------|------|---------|
| SessionStart | `sync_settings.py` | Merges repo `settings.json` into live `~/.claude/settings.json` (see note below) |
| SessionStart | `session_prime.py` | Injects giantmem workspace/feature primer, plus open MRs/PRs opened or touched by this project's sessions |
| SessionStart | `doit_session_prime.py` | Surfaces the repo-qualified doit todo list for this session plus its pending items, so the running todo is in context from turn one (`claude:` assignment + `/burn`). Links the session's tmux window to that list when the window has no link or links to `daily`, so the doit chip shows the session's active item; a window linked to another project list keeps it |
| SessionStart | `workspace_session_hook.py` | Bootstraps `.giantmem/`, injects workspace context |
| SessionStart | `giantmem_vault.py` | Detached rebuild of `~/giantmem-vault`, a second Obsidian vault of symlinks mirroring `$HOME`: one link per live `.giantmem`; a dir with workspaces below it stays a real folder and its own docs sit at `<dir>/_giantmem`. Hidden dirs, `Library`, caches, and `~/giantmem_archive` are skipped (archived workspaces live in the giantmem CLI/GUI). A removed worktree's folder lingers in Obsidian until the next SessionStart prunes its link. Real files and `.obsidian/` are never touched |
| SessionStart | `memory_ingest.py` | Detached `giantmem db ingest --source memory-md`: harness memory into archives.db (durable, backed up, survives a live.db rebuild) |
| UserPromptSubmit | `giantmem_recall.py` | Injects top giantmem FTS5 hits for the prompt (cross-project recall) |
| SessionEnd | `session_end_ingest.py` | Ingests the session transcript into giantmem |
| SessionEnd | `workspace_session_end.py` | Writes the session file and index line, refreshes WORKSPACE.md tables, spawns the haiku summarizer (see `docs/workspace-hooks.md`) |
| Stop | `debug_stop_check.py` | Blocks a stop while an unresolved `.giantmem/debug/` file has a stale `next_action` |
| Stop | `open_edges_gate.py` | Blocks a report once when its open-edges list holds work the session could do itself (CLOSE or VERIFY shapes, not gates); `OPEN_EDGES_GATE=off` bypasses |
| Stop | `doit_active_gate.py` | Blocks a stop once when the session's doit list has pending items and none `in_progress`, so the chip always shows the active or next item. Links an unlinked tmux window to a list created mid-session. Skips `claude -p` children; `DOIT_ACTIVE_GATE=off` bypasses |
| Stop | `created_links_gate.py` | Opens the MRs/PRs and dashboards a turn created (main transcript and its subagents) in the browser once, and blocks a stop once when they are missing from the last lines of the final message, so links never hide in tool output. Skips `claude -p` children; `CREATED_LINKS_GATE=off` bypasses |
| PostToolUse | `live_index.py` | Indexes `.giantmem/` + harness memory `*.md` writes into giantmem live.db |
| PostToolUse | `code_comment_nudge.py` | Flags comment shapes CLAUDE.md forbids in non-test `.py` — 2+ line comment blocks, docstrings, banners, ticket refs |
| PreToolUse | `artifact_gate.py` | Blocks an `Artifact` publish whose page lacks a visible `Rev N · YYYY-MM-DD HH:MM` stamp or carries a changelog-shaped heading (`claude-artifact` skill) |
| PostToolUse | `greptile_rereview.py` | After a session `git push` to a GitLab MR branch in a Greptile repo, posts `@greptile review`, since Greptile reviews only on MR open |
| PreToolUse | `guard_protected_paths.py` | Blocks writes to protected directories, and writes through `~/giantmem-vault` (names the real `.giantmem` path instead) |
| PreToolUse | `voice_gate.py` | Blocks MR/PR comments, thread replies, Jira comments, and Slack messages posted as the user that break `config/voice.md` (capitalized starts, first person, dashes, code outside backticks, length) |
| SessionStart, UserPromptSubmit, PreToolUse (AskUserQuestion/ExitPlanMode), PostToolUse, PermissionRequest, Notification, Stop, SessionEnd, SubagentStart, SubagentStop | `claude_tmux_state.sh` | Sets the pane options `@claude_state` (`busy`/`ask`/`ready`, unset on exit), `@claude_state_at`, and `@claude_agents` (running subagent count) so tmux-sessionx and status bar formats can show what each Claude pane is doing; `err`/`errclear` (called by the statusline) set `@claude_err`; drops `@claude_attention` (set by `request_attention.py`) on prompt submit; `ask`, `ready`, and `err` post a tmux `display-message` toast when the pane is off screen. The statusline also writes `@claude_ctx` and `@claude_model` to the pane, and `usage-fetch.py` writes `usage.tmux` next to its cache for a status bar chip |

Unlike everything else here, `settings.json` is **not** a stow symlink. Claude Code rewrites that file at runtime (theme, model, plugin toggles, survey state), so a symlink either gets clobbered by the app's atomic save or pollutes the git tree with machine-local state. Instead `sync_settings.py` runs each session start and merges: the repo wins for structural config (hooks, env, statusLine, mcpServers, marketplaces, permission mode); `enabledPlugins`, `permissions.allow` and `permissions.deny` are unioned so runtime additions survive; `permissions.ask` is repo-owned instead, since union is write-once and one "don't ask again" click would pin a rule no repo edit could ever remove; and `model`, `effortLevel`, `theme`, `feedbackSurveyState` stay whatever the live file says. Edit structural config in the repo and it goes live next session — no restow, no manual copy. It only writes the home file, never the repo copy, so `git status` stays clean.

`.stow-local-ignore` is what keeps `settings.json` out of the stow, along with repo-only files like `install.sh`, `package.json`, `node_modules/` and `kai-local/`, plus editor and cache junk. It replaces stow's built-in ignore list, so the defaults (`.git`, `README*`, `LICENSE*`) are repeated at the top. Add a line there before you drop anything into the repo root that shouldn't land in `~/.claude`.

## Key Commands

### Search and History

| Command | Purpose |
|---------|---------|
| `scripts/session-search` (`css` alias) | Search/list Claude JSONL sessions across projects |

### Analysis (read-only)

| Command | Purpose |
|---------|---------|
| `/swarm <task>` | Aspect-parallel analysis via `workflows/swarm-analyze.js`, per-agent artifacts on disk (`--no-artifacts` to skip) |

### Execution (read-write)

| Command | Purpose |
|---------|---------|
| `/swarm-exec <plan>` | Parallel execution via `workflows/swarm-exec.js`: plan -> implementers -> validator + tests (never commits) |

### Features

| Command | Purpose |
|---------|---------|
| `/new-feature <name>` | Scaffold a feature folder |
| `/plan-feature` | Ground on the code areas a feature touches, draft implementation plan |
| `/list-features` | Show feature registry |
| `/complete-feature` | Mark feature complete, update tracking |
| `/abandon-feature` | Drop a framed-but-dead feature: mark abandoned, no spec merge, archive |

### Workspace

| Command | Purpose |
|---------|---------|
| `/ws-init` | Initialize `.giantmem/` workspace |
| `/wrap [--feature]` | Pre-exit check before you end a session or close a feature: git and MR state, doit sync, docs, running processes, and a handoff for the next session. Ends with `safe to exit: yes/no` |
| `/mr-trace [ref]` | Find the Claude session and worktree behind an MR/PR (`repo!N`, a URL, or a bare `!N` that lists every repo with that number), or list the open MRs/PRs your sessions opened or touched, with live status. Wraps `giantmem mr whose` and `giantmem mr list` |
| `/eod-status [--days N] [--dry-run]` | Draft the end-of-day status DM to your manager. Reads Slack (the manager DM, the manager's asks, your own messages), your GitLab MRs and reviews, your GitHub PRs, release-central releases that carry your MRs, and the Claude activity in the vault daily notes, then sends the draft to your self-DM for a hand copy. `--days 3` or `--days 7` rolls the window up by topic. Per-person IDs live in `~/.config/eod-status/config.json`; `eod: <rule>` self-DMs teach it standing rules. Optional weekday launchd schedule in `skills/eod-status/scripts/eod-status.plist` |
| `/jira-status [ref]` | Read-only check of the Jira ticket behind the current branch, another branch, or an MR: key, status, and whether it matches what the MR implies. Wraps `glmon-jirad --lookup` |
| `/sec-ticket <key or url>... [--repo alias] [--fix] [--status s] [--queue] [--sweep]` | Research a security or bug ticket against the code: confirm it, find the root cause, propose the fix, each scored 1-5, as a vault note `areas/security/<repo>/<KEY>-<slug>.md` with rev, modified, and status (`new` `ready` `blocked` `in_progress` `in_review` `done` `wont_fix`). One item per ticket on doit list `security-tickets` holds the session log. `--fix` implements a note on a `<KEY>-<slug>` branch per repo with the key in every commit subject; `--fix --status ready` works every approved note. `--sweep` closes tickets whose MRs merged |

## Archive Search

Unified FTS5 search across workspace archives and session transcripts. See [giant-tooling/docs/search-usage.md](https://github.com/bearded-giant/giant-tooling/blob/main/docs/search-usage.md) for full usage.

```bash
giantmem find "jwt refresh"               # live docs + archives + sessions
giantmem find "jwt refresh" -s session    # sessions only
giantmem find "auth flow" -p my-repo      # one project
giantmem stats                            # index breakdown
```

Also available as MCP tool `search_archive` for agent use.

## License

MIT
