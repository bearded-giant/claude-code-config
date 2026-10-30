# Claude Code Hooks

Hooks that run at various Claude Code lifecycle events.

Some launch paths run hooks under macOS `/usr/bin/python3` (3.9), where an `X | None` annotation raises at import. A hook that uses one starts with `from __future__ import annotations`. Tests: `python3 hooks/test_py39_compat.py`.

## workspace_session_end.py

**Hook:** `SessionEnd`

Writes one session file per session, appends an index line, regenerates the Features and Timeline tables in `WORKSPACE.md`, then spawns a detached child that summarizes the session with `claude -p --model haiku`. Auto-initializes a minimal `.giantmem/` if none exists. Full behavior and file formats: `docs/workspace-hooks.md`.

### Output Files

| File | Description |
|------|-------------|
| `.giantmem/history/sessions/{timestamp}_{session_id}.md` | Session file: topic, brief, outcomes, prompts, files touched, tool usage, commands |
| `.giantmem/history/sessions.md` | Index with one line per session |
| `.giantmem/WORKSPACE.md` | `## Features` and `## Timeline` regenerated |

### Auto-Init Behavior

If `.giantmem/` doesn't exist when the session ends, the hook creates:

```
.giantmem/
  .gitkeep
  WORKSPACE.md          # with project name, date, git branch
  context/
  plans/
  history/
    sessions/
  filebox/
  research/
  reviews/
```

## workspace_session_hook.py

**Hook:** `SessionStart`

On `startup` in a dir without `.giantmem/`, runs `workspace_init` from `workspace-lib.sh` (`lib/workspace/`). Then injects `.giantmem/WORKSPACE.md` and `.giantmem/plans/current.md` as session context.

On `clear`, warns `FULL RESTART REQUIRED` when `~/.claude/plugins/installed_plugins.json` is newer than the running `claude` process, since `/clear` does not reload plugins. Finds the process by walking the parent chain; no `claude` ancestor means no warning.

## clear_capsule.py

**Hook:** `SessionStart` (via dispatch)

`/clear` keeps the `claude` process and starts a new session id, so every SessionStart records `{session_id, transcript_path, lstart}` in `/tmp/claude-clear-capsule-<claude pid>.json`. On `source: clear` it reads the entry left by the session that was just cleared and starts a detached `clear_capsule.py --handoff <id> <transcript> <out>`, so the hook returns at once. The handoff lands in `$OBSIDIAN_VAULT/handoffs/<project>/clear/<YYYYMMDD_HHMMSS>_<id8>.md` (`<project>` from `doit_session_prime.project`). It never touches the `<project>/<branch>.md` or `features/<name>.md` handoff that `/wrap` writes. The prompt tells the writer to redact secrets, since the vault syncs to GitHub. The hook prints a `systemMessage` with the path, which the terminal shows as `SessionStart:clear says: handoff for cleared session <id8>: <path>`. The new session also gets a short reminder with the path, the `claude --resume <id>` line, and the last three user asks.

The writer builds an extract of the transcript. It starts with the last compaction summary, then lists each later user ask, assistant reply, thinking block (first 1,500 chars; transcripts drop many text blocks, and the thinking often holds the finding), and tool call (one line, tool output dropped), then every edited file, capped at 240k chars with the head and tail kept. The prompt tells the writer to mark claims found only in thinking as inferred. It sends the extract and `config/compact-instructions.md` to `claude -p --model sonnet` with `--setting-sources ""` and a one-line system prompt, so the child loads no CLAUDE.md and runs no hooks. The note gets handoff frontmatter (`status: ready`, `lifecycle: candidate`) and ends with `## Start here`. A small session is written in seconds and a long one in about a minute. When the summarizer fails, the file holds the tail of the extract, so the path always points at something.

Keying on the pid avoids depending on SessionEnd finishing first. The process start time in the marker rejects one left by a dead process that had the same pid. Skips `claude -p` children. Tests: `python3 hooks/test_clear_capsule.py`.

## agent_model_default.py

**Hook:** `PreToolUse` (matcher: Agent, Task)

Fills in `model: haiku` for `Explore` and `model: sonnet` for `general-purpose` calls that pass no `model`, through `updatedInput`. Both otherwise inherit the session model. `CLAUDE_CODE_SUBAGENT_MODEL` can't do this: built-in Explore is pinned to `inherit` and ignores it. An explicit `model` on the call always wins, and agent types outside the table keep their frontmatter. Tests: `python3 hooks/test_agent_model_default.py`.

## debug_stop_check.py

**Hook:** `Stop`

Prevents Claude from stopping when there are active (unresolved) debug sessions. Works with the persistent debug state protocol in `agents/debugger.md`.

Checks `.giantmem/debug/` and any `features/{name}/debug/` directories for markdown files that don't have a filled-in Resolution section. If found, blocks the stop and tells Claude to update `next_action` or move the file to `debug/resolved/`.

Skips the check when `stop_hook_active` is true (already continuing from a prior stop hook) to prevent infinite loops.

## open_edges_gate.py

**Hook:** `Stop` (via dispatch)

Mechanical half of CLAUDE.md `### Proactive execution` report-time triage. Reads the last assistant turn from the transcript, finds an `Open edges` / `Not done` section, and blocks the stop once when an item there has a shape the rule says to close or verify rather than report: `I haven't checked / tested / run X`, `not verified`, `say "ship it" and I'll`, a pre-existing failure the session did not touch, a doit item parked for `/burn`, a scratch clone or `/private/tmp` path, `not committed` / `not pushed` / `no MR`. An item that names an owed twin (`daily #N`), states an expectation (`expect`, `to check:`, `on failure`), or carries a dependency (`dep on`, `blocked by`, `waits on`) is already a gate or a sequenced item and is skipped. Scanning stops at the next heading, so a `What changed` list is never matched. The block reason quotes each item with its tag, and the model gets one turn to do the work or restate the item as a GATE or LIMIT.

Skips when `stop_hook_active` is true, so a report blocked once goes through on the second stop. `OPEN_EDGES_GATE=off` in the environment disables it. Tests: `python3 hooks/test_open_edges_gate.py`.

## created_links_gate.py

**Hook:** `Stop` (via dispatch)

Makes the links a turn created land where the user sees them. It reads the turn (records since the last real user prompt; teammate messages, task notifications, and local command output are not prompts) plus every subagent transcript under `<session>/subagents/` with records inside that window, and collects what was created: MRs/PRs from `glab mr create` / `gh pr create` (matched in the command, or `Creating merge request for` in the output when a script ran it), dashboards from the `splunk|chronosphere|newrelic` `create|put|update_dashboard` MCP tools (the result's `url` field, else its first https URL), and Chronosphere dashboards after a `chronoctl apply` / `create` that was not `--dry-run`. chronoctl prints no URL, so any `https://<tenant>.chronosphere.io/dashboards/<slug>` that shows up later in that transcript's tool results or the agent's own text counts. A create whose output hid the URL falls back to a harness `pr-link` record first seen in the turn; a `pr-link` alone never counts, since the harness writes one for an MR that was only viewed.

Each new link opens once per session in the browser (macOS `open`). The hook then blocks the stop once when a link is missing from the last 12 non-empty lines of the final message, listing each as `<repo>!N <url>`, `<repo>#N <url>`, or `<kind> dashboard <url>`. A link that reached those last lines once is marked delivered and never demanded again. State lives in `/tmp/claude-created-links/<session>.json` (`opened`, `delivered`).

Skips `claude -p` children and `stop_hook_active` stops (a blocked report goes through on the second stop; opening still runs). `CREATED_LINKS_GATE=off` disables it. Tests: `python3 hooks/test_created_links_gate.py`.

## auto_mode.py

**Hook:** `UserPromptSubmit` and `Stop` (via dispatch)

Backs CLAUDE.md `### Autonomous mode` (entry, hard stops) and `commands/auto.md` `## Rules of engagement`. A prompt of `/auto <scope>` writes `/tmp/claude-auto-mode/<session>.json` (`started`, `scope`, `shipped`), and `/auto off` deletes it. While the file exists, every prompt gets a one-line reminder of the mode and its exit command, so the mode survives compaction. `python3 ~/.claude/hooks/auto_mode.py --on [scope]` / `--off` does the same from a Bash call, keyed on `CLAUDE_CODE_SESSION_ID`, for a session that enters the mode without typing `/auto`.

At Stop it blocks once when either holds: a ready `claude:` item sits on the session doit list (pending, and every `(dep on #N)` it carries points at a done item), or a branch pushed since entry has no MR/PR. Pushes come from Bash results in the transcript: each `To <remote>` line followed by ` <flag> ... <src> -> <dst>`, skipping rejected refs and `main`/`master`/`stage`/`develop`/`HEAD`. The remote is normalized to `host/group/repo` (glab `-R` rejects the scp form) and checked live with `glab mr list --source-branch <b> --all` or `gh pr list --head <b> --state all`. A branch with an MR is cached in `shipped`; a failed lookup fails open. A blocked item drops out once it carries a dep on an open `gate` item, which is how the rule says to park it.

Skips `claude -p` children and `stop_hook_active` stops. `AUTO_MODE_GATE=off` disables the Stop gate. Tests: `python3 hooks/test_auto_mode.py`.

## guard_protected_paths.py

**Hook:** `PreToolUse` (matcher: Write, Edit, MultiEdit)

Blocks writes under `~/.claude/plugins` and this repo's `archive/`, plus any `node_modules/`. Returns a top-level block decision, which a permission decision would not do here: `defaultMode` is `bypassPermissions`, so `ask` and `deny` are advisory and only a block actually stops the write.

Matching is on the resolved path, anchored to those roots — an earlier version matched `/archive/` and `/plugins/cache/` as substrings, which silently blocked those directory names in every repo on the machine.

Bash is not in the matcher, so this guards tool-driven edits only. A `sed -i` or heredoc into a protected path goes through.

## greptile_rereview.py

PostToolUse on Bash. Greptile reviews a GitLab MR or a GitHub PR only when it opens, so every later push needs an `@greptile review` comment (`@greptileai review` on GitHub, where `@greptile` is not the bot). After a session runs `git push`, this posts that comment on the GitLab MR of the pushed branch and, when origin is a skio-org / RechargePayments GitHub repo or the repo has a `github` twin remote, on the branch's open PR too (only when `.greptile/` exists or the PR body carries Greptile's summary), and tells the session so it does not post a second one. It skips when Greptile already reviewed the pushed head.

## voice_gate.py

**Hook:** `PreToolUse` (matcher: Bash, the Slack send/draft/schedule MCP tools, Jira `addCommentToJiraIssue`)

Lints text posted under the user's name against `config/voice.md`. That covers MR/PR notes and thread replies (`glab mr note`, `gh pr comment|review`, and `glab api`/`gh api`/`curl` posts to notes, discussions, comments), Slack messages, and Jira comments. MR descriptions are out of scope. It blocks on capitalized sentence starts, first person (except on Slack), a lowercase `i`, em/en dashes, code outside backticks, markdown headers/tables/bold, unicode emoji, filler, Claude attribution, and length over the surface cap (reply 80 words, comment 150, Slack 80, Jira 150). The block reason lists each violation, so the model rewrites and retries.

The body is read from `-m`, `--body`, `--body-file`, `--input`, `-F body=@file`, `$(cat file)`, `--data @file`, and heredocs written earlier in the same command. A body it can't read (a shell variable, JSON built by a script) blocks with instructions to post from a file. `VOICE_GATE=off` in the command skips the check and is for the user's own verbatim words only; MCP calls have no bypass.

A capitalized sentence start is flagged only when the word is common English (a starter list plus `/usr/share/dict/words`), so names and product names pass. It returns the legacy top-level `decision: block` for the same reason as `guard_protected_paths.py`. The hook command in `settings.json` runs a shell `case` first and only starts python when the payload mentions `glab`, `gh`, `curl`, or `mcp__`, so an ordinary Bash call costs about 10ms instead of a pyenv-shimmed interpreter start. Tests: `python3 hooks/test_voice_gate.py`.

## standing_constraints.py

**Hook:** `UserPromptSubmit`

Prints `config/standing-constraints.md` to re-assert scope / artifact-vs-execution / precedence invariants late in context, where they survive conflicts with project-level instructions.

It does not fire every prompt. UserPromptSubmit context accumulates in the transcript, so injecting 1.6KB per turn cost roughly 40k tokens by turn 100, re-stating rules CLAUDE.md already holds in the system prompt for the whole session. What actually erodes those rules is compaction, so it now fires on the first prompt, on the first prompt after each compact (reading the marker the PreCompact hook writes), and every 25 prompts as a drift backstop. Per-session counters live in `$TMPDIR/claude-standing-constraints/`.

Edit the md file to change the injected rules, keeping it in sync with the matching CLAUDE.md sections. Keep it under about 7,000 characters: Claude Code saves any hook stdout over 10,000 characters to a file and shows the model only a 2,000-character preview, and dispatch prints these rules in the same stdout as the giantmem recall hits. Override path via `CLAUDE_STANDING_CONSTRAINTS`. Best-effort: missing file prints nothing. Tests: `python3 hooks/test_standing_constraints.py`.

## giantmem_recall.py

UserPromptSubmit hook. Two arms run concurrently: a keyword OR-query through `giantmem find -s memory --json` (FTS5 bm25 over live workspace docs plus archived memory docs) and the full prompt through `giantmem artifact search --repo all --json` (chunked bge vectors; only real `vector_score > 0` hits kept, so a cold daemon degrades to FTS). Repo-first: current-repo hits fill first, at most `GIANTMEM_RECALL_CROSS_MAX` (default 1) lines come from other repos, worktree siblings of one doc collapse to one line. Output is packed into `GIANTMEM_RECALL_BUDGET` tokens (default 600, `ceil(len/4)`), with `GIANTMEM_RECALL_LIMIT` lines (default 8) as a ceiling and `GIANTMEM_RECALL_SNIPPET_CHARS` (default 400) per passage. Best-effort: prints nothing on miss/timeout so the prompt is never blocked. Query terms present in more than `GIANTMEM_RECALL_MAX_DF` of `live_docs` (default 0.2; `session`, `giantmem`, `config` in this corpus) are dropped before the FTS arm runs, so the overlap floor counts only discriminative terms. Other tunables: `GIANTMEM_RECALL_SINCE`, `GIANTMEM_RECALL_MIN_OVERLAP`, `GIANTMEM_RECALL_SEMANTIC`. Every injected line is also appended to `live.db.recall_log` (session, rank, signal, slot, path); `giantmem recall report --since 30d` joins that against the session transcript and `live_docs` writes to report precision per signal, slot, and rank, so ranker changes are compared on numbers. Regression checks: `python3 hooks/giantmem_recall_check.py`. Replaced the dead RLabs `:8765` hooks (`memory_inject`, `memory_session_start`, `memory_curate`).

## Hook Wiring Summary

Most events run through `dispatch.py`, which loads several modules in one process so an event pays one interpreter start instead of N. It calls each module's `main()` with the same stdin, merges every `additionalContext` into one object, joins any `systemMessage` notices into that object, and lets a control object (a block or permission decision) win alone. It catches everything a module raises, including `SystemExit`, and logs the traceback to `~/.cache/giantmem/hook.log` — without that log a crashing hook is indistinguishable from a quiet one.

The caveman plugin registers its own SessionStart and UserPromptSubmit hooks through its `plugin.json`, so `settings.json` is not the whole picture.

| Event | Scripts | Context injection? |
|-------|---------|-------------------|
| SessionStart | `giantmem daemon start`, then dispatch: `sync_settings`, `workspace_session_hook`, `clear_capsule`, `ensure_personal_claude`, `session_prime`, `doit_session_prime`, `daily_note`, `memory_ingest`, `giantmem_vault` | Yes (one-time, ~4.9KB; `clear_capsule` adds up to ~1KB after `/clear` only, plus a `systemMessage` naming the handoff file) |
| UserPromptSubmit | dispatch: `standing_constraints`, `giantmem_recall`, `auto_mode`; plus `caveman-mode-tracker.js` | Yes (recall every prompt, constraints on the cadence above, one auto mode line while it is on) |
| PreCompact | timestamp file, then `precompact_capture.py`, then `cat ~/.claude/config/compact-instructions.md` | Yes: PreCompact stdout becomes the compaction's custom instructions (merged with `/compact <args>`), so the summary keeps files, findings, commits, decisions, and open state for the next task. Every other PreCompact hook must keep stdout empty. The window stays at each model's default (`docs/autocompact.md`) |
| SessionEnd | dispatch: `workspace_session_end`, `session_end_ingest` | No (stderr + file writes) |
| PreToolUse | `guard_protected_paths.py` (Write/Edit/MultiEdit) | No (JSON decision only) |
| PreToolUse | `agent_model_default.py` (Agent/Task) | No (`updatedInput` only) |
| PreToolUse | `voice_gate.py` (Bash, Slack send/draft/schedule, Jira comment) | No (JSON decision only) |
| PostToolUse | `greptile_rereview.py` (Bash, `git push` only) | Yes (one line after it posts) |
| SessionStart, PostToolUse | `daily_note.py` (Artifact, Write/Edit/MultiEdit, Bash `note.py new`): appends to the vault daily note `daily/<date>.md`, creating it from `templates/dailytemplate.md`. One `## CLAUDE SESSIONS` line per interactive session (repo list, tmux, `claude --resume <id>`; headless `sdk-cli` runs skipped), one `## CLAUDE LINKS` line per artifact publish, vault note write, or vault `handoffs/**` write. flock-guarded, section-scoped dedupe. Tests: `python3 hooks/test_daily_note.py` | No (file write only) |
| Stop, PreCompact, SessionEnd | `session_bundle.py`: detached rsync of the session's `/private/tmp/claude-*/<slug>/<sid>/{scratchpad,tasks}` (purged by macOS) into `~/giantmem_archive/bundles/<slug>/<sid>/`, skipping `.venv`, `node_modules`, caches, binaries, files over 20MB, and symlinks. PreCompact and SessionEnd also copy `~/.claude/projects/<slug>/<sid>/{subagents,workflows,tool-results}` and the transcript into `claude/`. Writes `bundle.json` (cwd, branch, first prompt, resume command, file list with kinds). Archive only: files the session deletes stay. After the SessionEnd sync it re-runs `giantmem db ingest -s session-bundle`, so the final files are indexed even when `session_end_ingest` got there first. `--backfill [--from DIR]` sweeps existing tmp dirs or a saved copy. Tests: `python3 hooks/test_session_bundle.py` | No (file write only) |
| SessionStart | `session_prime.py` renders `giantmem prime --json`: active feature, recent `.giantmem/` writes, and `open_mrs` (MRs/PRs this project's sessions opened or touched that are not merged or closed, one line each: `repo!N  state  opener  url`). Skips the prime only when all three are empty. Tests: `python3 hooks/test_session_prime.py` | Yes |
| SessionStart | `doit_session_prime.py` also prints the session id + tmux `session:window` + `resume` line, the owed count, `DRIFT` lines for owed twins out of sync with `daily`, and the project's `status: ready` handoffs from `$OBSIDIAN_VAULT/handoffs/<project>/` (`--handoff-path [--feature <name>]` prints where `/wrap` writes one). Tests: `python3 hooks/test_doit_session_prime.py` | Yes |
| Stop | dispatch: `debug_stop_check`, `open_edges_gate`, `doit_active_gate`, `created_links_gate`, `auto_mode` | No (JSON decision only; `created_links_gate` also opens created links in the browser) |
| SessionStart, UserPromptSubmit, PreToolUse (AskUserQuestion/ExitPlanMode), PostToolUse, PermissionRequest, Notification, Stop, SessionEnd | `claude_tmux_state.sh` (bash, not dispatch: it runs on every tool call) | No (tmux pane options only) |
| statusLine | `statusline.js` (spawns `usage-fetch.py`, `preflight_check.py`, `mr_status.py` detached; each writes a cache the next tick reads) | N/A (terminal only) |

Undocumented above but present: `live_index.py` (PostToolUse, indexes `.giantmem/` and memory writes into live.db), the PostToolUse nudges (`caveman_artifact_nudge`, `code_comment_nudge`), `artifact_gate.py` (PreToolUse on `Artifact`, blocks a publish with no `Rev N · timestamp` stamp or a changelog heading; PostToolUse on `Artifact`, caches the published page per note and rev under `~/.local/share/claude-artifact/` for cross-account mirrors; tests: `python3 hooks/test_artifact_gate.py`), `request_attention.py` (not a hook: `commands/babysit.md` calls it to set or `--clear` the pane option `@claude_attention`; a new reason sends a desktop notification, and `claude_tmux_state.sh submit` drops the flag on the next prompt), and `_giantmem_log.py`, a shared logger imported by several of them.

Run the statusline unit tests with `npm test` from this directory, and the fetcher tests with `python3 hooks/test_statusline_fetchers.py`.

Recall and workspace hooks all run on one local backend: giantmem (SQLite FTS5 + sqlite-vec). `giantmem_recall.py` reads it for cross-project recall; `session_prime.py`, `session_end_ingest.py`, `live_index.py`, and `precompact_capture.py` write sessions, `.giantmem/` artifacts, and harness memory files (`~/.claude/projects/<slug>/memory/*.md`, tagged `dir_type=memory`) into it.

Durability + speed: SessionStart runs `giantmem daemon start` (a unix-socket daemon that kills ~700ms cold starts, so per-prompt recall is sub-ms) and `memory_ingest.py` (detached `giantmem db ingest --source memory-md`, which lands every memory md in archives.db, the durable, backed-up store; `live_index.py` still writes them into live.db on PostToolUse for same-session recall, and the recall hook's `find -s memory` reads both).

Backup is handled by the giant-tooling db-backup script (`giantmem/scripts/giantmem-db-backup.sh`) on a launchd timer (`com.bryan.giantmem-db-backup`, every 2h), not a hook. Per db it takes a consistent `sqlite3 .backup` of `live.db` + `archives.db`, runs `PRAGMA integrity_check`, gpg-encrypts (asymmetric, key `33F36CDDD530C52910A4608D61258A79557ECB4A`), and publishes to iCloud Drive (`giantmem-db-backups/`), overwriting the single current copy only after validation (one `.prev` kept). No VPS/tailscale. The DBs already hold the ingested sessions + memory md, so they are the backed-up unit. Restore: `gpg --decrypt live.db.gpg > live.db` — needs the private key, stored in 1Password.
