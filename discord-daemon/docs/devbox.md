# Cloud Claude on the devbox

Claude Code sessions that run on a GCP devbox, each one with its own Discord thread, started and steered from a phone or from the laptop. The laptop stays the place where you think; the devbox is where long sessions live. Architecture and flows: [`cloud-claude-architecture.md`](cloud-claude-architecture.md). Extending the daemon: [`../HACKING.md`](../HACKING.md). Things that bit us before: [`cloud-claude-lessons.md`](cloud-claude-lessons.md).

## What runs where

| Piece | Where | Notes |
|---|---|---|
| discord-daemon | devbox, user unit `discord-daemon` | owns the Discord gateway, one thread per session, HTTP + SSE on loopback `127.0.0.1:7777` |
| session-mcp | inside every claude session on the devbox | registers the session with the daemon, streams its thread into the session |
| `dclaude` | devbox, `~/.local/bin` | `claude` with the Discord channel, bypass permissions, a credentials slot, and the rule that Discord messages get answered in Discord |
| tmux | devbox | one session per repo directory; the daemon spawns into it, `cvps` attaches to it |
| giantmemd + ingest timer | devbox, user units | same memory stack as the laptop, rebuilt from synced files |
| mutagen | laptop daemon, agent on the devbox | carries transcripts, doit lists, the vault, and per-repo `.giantmem` dirs both ways |
| repos | git clones on both machines | push from either side; nothing syncs `.git` |

The devbox is reachable only over Twingate. The laptop's `~/.ssh/config` has `Host devbox` with the hostname, user, and `ForwardAgent yes`, and every script here uses that alias.

### The path bridge

Hooks, `config/repos.csv`, transcript slugs under `~/.claude/projects`, and giantmem keys all carry the laptop's absolute home path. The devbox answers to that same path: `scripts/setup-vps.sh` bind-mounts the devbox home onto it (`BRIDGE` in the script). A bind mount, not a symlink, because `getcwd()` through a symlink returns the physical path and claude would file transcripts under a devbox-only slug. Repos get cloned under the bridged path, `tmux -c` uses it, and every session on the devbox then has the same cwd string as on the laptop.

`$BRIDGE` below means that path. Always `cd` through it on the box, never through the physical home: a session started from the physical path gets its own transcript slug and its own giantmem key, and nothing you synced applies to it.

## Bootstrap

1. Add `Host devbox` to `~/.ssh/config` and check `ssh devbox true`.
2. From the laptop run `scripts/bootstrap-vps.sh devbox`. It syncs your shell dotfiles and `.creds.secret`, pulls the `claude-code-config` clone on the box (or seeds it with rsync the first time), cross-builds giantmem, copies the daemon `.env` and `access.json` if the box has none, then streams `scripts/setup-vps.sh` over ssh. Setup is idempotent: bridge, apt deps, bun, node shim, claude CLI, gh and glab, giantmem units, stow of `~/.claude`, `settings.local.json` (bypass permissions, xhigh effort, the Discord plugin off), the daemon unit, `~/.claude-devbox.sh`, the `dclaude` link, the MCP registration. `--skip-embed` skips the sentence-transformers venv (slow, large), `--skip-lsp` the language servers, `--restore <tar.age>` feeds a daemon state backup.
3. Clone the repos: `scripts/devbox-clone-repos.sh devbox` reads `config/repos.csv` and recreates the `-wt/.bare` worktree layouts under the bridged path. `--dry-run` prints the manifest, `--only <alias>` does one repo. GitLab goes over https with `GITLAB_TOKEN` from `.creds.secret`, GitHub over ssh.
4. Log in on the box, one slot per account: `claude-team auth login`, then `claude-ent auth login`. Each prints a URL to open in the laptop browser. The authorize page grants whatever organization is active in that browser and shows no selector, so switch organization on claude.ai first, or open the URL in a private window and pick the organization at sign-in. Check with `claude-ent auth status | grep subscriptionType`.
5. Bot token: regenerate it in the Discord developer portal, put it in `~/.claude/channels/discord/.env` as `DISCORD_BOT_TOKEN` on both machines, `systemctl --user restart discord-daemon`, and look for `gateway connected as <bot>` in `journalctl --user -u discord-daemon`. `DISCORD_SESSIONS_CHANNEL_ID` is the channel that holds the threads; a private channel needs the bot added as a member.
6. Allowlist your Discord user id in `access.json` (`allowFrom`).
7. Git from unattended sessions: add the devbox's `~/.ssh/id_ed25519.pub` (setup prints it) to GitHub, then `gh auth login --git-protocol ssh` and `glab auth login --hostname <gitlab host> --token "$GITLAB_TOKEN"` on the box.
8. State sync from the laptop: `scripts/mutagen-sync-state.sh` creates the `claude-projects`, `doit`, and `vault` sessions; `scripts/mutagen-sync-giantmem.sh <alias|path>` adds a repo's `.giantmem` dirs. Sessions pause while Twingate is down and resume on their own.

## Starting a session

### From the laptop

`cvps` from a repo directory attaches a devbox tmux session named after that directory, started in the same path. Inside a `-wt` layout the name is `<base>-wt-<branch>`, so `dev/python/cc-wt/master` becomes `cc-wt-master`. From your home directory `cvps` opens the `main` session. `cvps-shell` is a plain ssh. The tmux session is just a shell until you start claude in it:

```
dclaude                                  # team slot, xhigh effort
dclaude --acct ent                       # enterprise slot
dclaude --acct ent --effort max          # one heavy run; any claude flag passes through
dclaude --resume <session-id>            # pick up a laptop session that mutagen already delivered
```

| Flag or variable | Effect |
|---|---|
| `--acct team\|ent` | credentials slot (`CLAUDE_SECURESTORAGE_CONFIG_DIR`); `DCLAUDE_ACCT` sets the default |
| `--effort <level>` | per-session override. The default is xhigh from the box's `settings.local.json`; `/effort` changes it inside the session |
| `--model <name>`, `--resume <id>`, anything else | passed straight to `claude` |

Inside tmux, `dclaude` also answers the three dialogs an interactive claude shows and that no flag can skip: the development-channels warning, a fresh folder's trust prompt, and the external CLAUDE.md imports prompt. That watcher stops once the prompt is up. `dclaude` appends one rule to the system prompt: messages tagged `<channel source="discord">` get answered with the `reply` tool, chat_id from the tag. A session started with plain `claude` still receives thread messages (the `discord` MCP is user-scope) but answers only in its terminal, so always use `dclaude` on the box.

### From the phone

DM the bot. Sessions never read DMs; DMs are control only.

| DM | Effect |
|---|---|
| `start [relpath] [--acct team\|ent] [--effort low..max] [--model opus\|sonnet\|fable]` | spawn `dclaude` in a tmux session at `$BRIDGE/<relpath>` (`mkdir -p` if missing); no path: `sandbox/`, a throwaway directory outside any repo |
| `projects` | repos and worktrees under `dev/` on the box, to depth 3; paste one back into `start` |
| `list` | sessions, cwd, heartbeat age |
| `status <label>` | one session in detail |
| `send <label> <text>` | post into that session's thread without opening it |
| `tail <label> [n]` | last n inbox events |
| `kill <label>` | hard-remove the registry entry and archive the thread |

The relpath is relative to the bridged home, so `start dev/python/cc-wt/master --acct ent` starts the monolith session. The tmux session and the Discord thread take the directory's name (worktree dirs: `<base>-wt-<branch>`), the same name `cvps` uses, so `cvps` from that directory on the laptop attaches to the session the phone started. `start` into a directory whose tmux session already exists reports the clash and creates nothing. `start` has no resume; a phone-started session is always fresh.

A new session posts `session <label> online` in its thread within a few seconds. Reply in the thread to talk to it; the thread link is `https://discord.com/channels/<guild id>/<thread id>`, or open the sessions channel and use the Threads view.

## Moving a session between machines

Transcripts live under `~/.claude/projects/<slug>/<session id>.jsonl`, where the slug is the cwd with `/` replaced by `-`. The `claude-projects` mutagen session carries that directory both ways within seconds, and the bridge makes the slug identical on both machines, so a resume on either side is a plain `--resume`.

Laptop to devbox: find the session id (`ls -t ~/.claude/projects/<slug>/*.jsonl | head -1`; the newest file is the session you just left), check `mutagen sync list claude-projects` says `Watching for changes`, then `cvps` from the same directory and `dclaude --resume <id>`. Devbox to laptop: `claude --resume <id>` from the same directory. The resumed session keeps its history; on the box it gets a new Discord thread, because thread ids follow the daemon's session id, not claude's. `CLAUDE_SESSION_ID=<old daemon id> dclaude --resume <claude id>` reattaches to a dormant entry's existing thread; `status <label>` shows the daemon id.

When mutagen is off, `lift` (`scripts/lift-to-vps.sh [session-id]`) copies one transcript from the current directory to the box and prints the resume command.

## Directories on the box

| Path | Use |
|---|---|
| `$BRIDGE/sandbox/` | throwaway sessions not tied to a repo: `start` with no path lands here. The SessionStart hooks drop a `.giantmem/` in it; harmless |
| `$BRIDGE/dev/...` | repos, same layout as the laptop, cloned by `devbox-clone-repos.sh` |
| `$BRIDGE/.claude/projects` | transcripts, synced |
| `$BRIDGE/.local/share/nvim/doit` | doit lists, synced (`session.json` stays per machine) |
| `$BRIDGE/Recharge-Notes` | the vault, synced |
| `<repo>/.giantmem` | synced only for repos you added with `mutagen-sync-giantmem.sh`; everything else about giantmem (the `.db` files) is rebuilt per machine by the ingest timer |

## Repos and worktrees on the box

`devbox-clone-repos.sh` gives every `-wt` row in `repos.csv` the same `.bare` layout as the laptop, with one worktree checked out: the default branch (`cc-wt/.bare` plus `cc-wt/master`). Plain rows get a plain clone. Nothing syncs `.git`, so branches move through the remote: commit and push on one machine, fetch and check out on the other. Push works from unattended sessions (GitLab over https with the token, GitHub over the registered key).

The worktree prefix functions from dotfiles load on the box with their bases under the bridge, so the laptop commands work unchanged in a `cvps-shell`. With the monolith's prefix `cwt` as the example:

| Command | Effect |
|---|---|
| `cwta <branch> [base] [--push]` | add a worktree at `cc-wt/<branch>` for an existing or new branch |
| `cwt <branch>`, `cwt` | switch to that worktree; no argument toggles to the last one |
| `cwtl`, `cwtb`, `cwts` | list worktrees, list branches, status |
| `cwtp`, `cwtf` | pull, fetch |
| `cwtr <branch>` | remove the worktree |
| `cwtprune`, `cwtrepair` | prune stale worktree records, repair the layout |

A feature branch you want on both machines: push it from where it exists, `cwta <branch>` on the other machine, then from the laptop `scripts/mutagen-sync-giantmem.sh <alias>`. That script creates one `gm-<alias>-<branch>` session per worktree that exists on both sides and skips the rest, so run it again after adding a worktree. When the branch is done, `cwtr <branch>` on each machine and `mutagen sync terminate gm-<alias>-<branch>`.

`git worktree list` on the box prints physical home paths for worktrees the clone script made and bridged paths for ones the prefix functions made. Both resolve to the same files; the cwd you start sessions from is what matters, and that stays `$BRIDGE/...`.

`scripts/pull-from-vps.sh <path-under-dev>` commits and pushes box-side edits and pulls them on the laptop in one go, for when a phone session left work uncommitted.

## Managing sessions and the daemon

A registry entry is `active` while its session-mcp heartbeats and `dormant` after the claude process exits or the heartbeat lapses. Dormant entries keep their thread id (for `CLAUDE_SESSION_ID` reattach), archive their thread, and stay in `list` tagged `(dormant)`. Only the `kill` DM removes an entry for good. Every `claude` run on the box, `claude auth login` included, registers and leaves a dormant entry behind; expected.

Shipping a change to the box after a push to `claude-code-config`:

| Changed | Do |
|---|---|
| scripts (`dclaude`, `setup-vps.sh`, anything under `scripts/`) | `ssh devbox 'bash -lc "git -C $BRIDGE/dev/claude-code-config pull --ff-only"'`; `dclaude` is a symlink into the clone, running sessions keep the old copy until restarted |
| daemon, session-mcp, the unit, setup steps | `scripts/bootstrap-vps.sh devbox --skip-embed --skip-lsp`: pulls, reruns setup, restarts the daemon. Running sessions reconnect their SSE stream and keep their threads |
| giantmem | `make -C giantmem deploy-devbox` in giant-tooling |

Daemon ops on the box: `systemctl --user status discord-daemon`, `journalctl --user -u discord-daemon -f`, `curl -H "x-daemon-token: $DISCORD_DAEMON_TOKEN" http://127.0.0.1:7777/sessions`. From the laptop, `ssh -L 7777:127.0.0.1:7777 devbox` and then `scripts/daemon-cli.sh` against the default URL. `scripts/backup-daemon-state.sh` pulls an age-encrypted copy of `.env`, `access.json`, and `sessions.json`.

State sync: `mutagen sync list` for everything, `mutagen sync list | grep -E '^Name|^Status' | paste - -` for one line per session, `mutagen sync monitor <name>` to watch one. `[Paused]` means Twingate is down on the laptop; it resumes by itself.

After a devbox reboot, `scripts/restore-vps-tmux.sh` recreates sessions from `~/.claude/vps-sessions.yml` (one `cwd:` entry per session, optional `label:`), or DM `start` for each one you want back.

## Troubleshooting

| Symptom | Cause and fix |
|---|---|
| `Discord start failed: DiscordjsError [TokenInvalid]` | Discord revoked the token; regenerate and set it in `.env` on both machines |
| a slot's `auth status` shows the wrong `subscriptionType` | the authorize page used the browser's active organization; switch it on claude.ai or sign in from a private window, then log in again |
| transcripts land under a `-home-...` slug | the session started from the physical home path, or the bridge is a symlink or missing; `mount \| grep <bridge path>` on the box, start from `$BRIDGE/...`, rerun setup if the mount is gone |
| the session answers in its terminal but nothing reaches the thread | it was started with plain `claude`, not `dclaude`; the reply rule lives in `dclaude` |
| DM `start` says the tmux session already exists | a session for that directory is running; `cvps` from the directory attaches to it, or `kill <label>` and `tmux kill-session -t <label>` first |
| a session runs at the wrong effort | the launch passed `--effort`; `/effort xhigh` inside it, or restart without the flag |
| `git pull` over ssh fails with `HTTP Basic: Access denied` | the command ran without a login shell, so `GITLAB_TOKEN` was not loaded; wrap it in `bash -lc` |
| stow refuses every link | `install.sh` ran from the bridged path; setup runs it from the physical home path |
| `git pull --ff-only` on the box refuses | the clone has untracked or edited files, usually from an old rsync; `git status`, clean, pull |
| mutagen session `[Paused]` | Twingate is down on the laptop; it resumes by itself. A session for a host that no longer exists: `mutagen sync terminate <name>` |
| a session started from a DM never answers | the tmux pane sits on a dialog the watcher does not know; `tmux attach -t <label>` on the box and read it |
| a thread appears for every `claude` run, `claude auth login` included | the user-scope `discord` MCP registers each run; expected, `kill <label>` clears the dormant entries |
| `giantmem find` on the box misses a laptop doc | `.giantmem` files arrive without hooks; the ingest timer backfills live.db every ten minutes, or run `giantmem db index backfill` |
