# Cloud Claude on the devbox

Claude Code sessions that run on a GCP devbox, each one with its own Discord thread, started and steered from a phone or from the laptop. The laptop stays the place where you think; the devbox is where long sessions live. Architecture and flows: [`cloud-claude-architecture.md`](cloud-claude-architecture.md). Extending the daemon: [`../HACKING.md`](../HACKING.md). Things that bit us before: [`cloud-claude-lessons.md`](cloud-claude-lessons.md).

## What runs where

| Piece | Where | Notes |
|---|---|---|
| discord-daemon | devbox, user unit `discord-daemon` | owns the Discord gateway, one thread per session, HTTP + SSE on loopback `127.0.0.1:7777` |
| session-mcp | inside every claude session on the devbox | registers the session with the daemon, streams its thread into the session |
| `dclaude` | devbox, `~/.local/bin` | `claude` with the Discord channel, bypass permissions, and a credentials slot |
| tmux | devbox | one session per repo worktree; the daemon spawns into it, `cvps` attaches to it |
| giantmemd + ingest timer | devbox, user units | same memory stack as the laptop, rebuilt from synced files |
| mutagen | laptop daemon, agent on the devbox | carries transcripts, doit lists, the vault, and per-repo `.giantmem` dirs both ways |
| repos | git clones on both machines | push from either side; nothing syncs `.git` |

The devbox is reachable only over Twingate. The laptop's `~/.ssh/config` has `Host devbox` with the hostname, user, and `ForwardAgent yes`, and every script here uses that alias.

### The path bridge

Hooks, `config/repos.csv`, transcript slugs under `~/.claude/projects`, and giantmem keys all carry the laptop's absolute home path. The devbox answers to that same path: `scripts/setup-vps.sh` bind-mounts the devbox home onto it (`BRIDGE` in the script). A bind mount, not a symlink, because `getcwd()` through a symlink returns the physical path and claude would file transcripts under a devbox-only slug. Repos get cloned under the bridged path, `tmux -c` uses it, and every session on the devbox then has the same cwd string as on the laptop.

## Bootstrap

1. Add `Host devbox` to `~/.ssh/config` and check `ssh devbox true`.
2. From the laptop run `scripts/bootstrap-vps.sh devbox`. It syncs your shell dotfiles and `.creds.secret`, pulls the `claude-code-config` clone on the box (or seeds it with rsync the first time), cross-builds giantmem, copies the daemon `.env` and `access.json` if the box has none, then streams `scripts/setup-vps.sh` over ssh. Setup is idempotent: bridge, apt deps, bun, node shim, claude CLI, gh and glab, giantmem units, stow of `~/.claude`, the daemon unit, `~/.claude-devbox.sh`, the `dclaude` link, the MCP registration. `--skip-embed` skips the sentence-transformers venv (slow, large), `--skip-lsp` the language servers, `--restore <tar.age>` feeds a daemon state backup.
3. Clone the repos: `scripts/devbox-clone-repos.sh devbox` reads `config/repos.csv` and recreates the `-wt/.bare` worktree layouts under the bridged path. `--dry-run` prints the manifest, `--only <alias>` does one repo. GitLab goes over https with `GITLAB_TOKEN` from `.creds.secret`, GitHub over ssh.
4. Log in on the box, one slot per account: `claude-team auth login`, then `claude-ent auth login`. Each prints a URL to open in the laptop browser. The authorize page grants whatever organization is active in that browser and shows no selector, so switch organization on claude.ai first, or open the URL in a private window and pick the organization at sign-in. Check with `claude-ent auth status | grep subscriptionType`.
5. Bot token: regenerate it in the Discord developer portal, put it in `~/.claude/channels/discord/.env` as `DISCORD_BOT_TOKEN` on both machines, `systemctl --user restart discord-daemon`, and look for `gateway connected as <bot>` in `journalctl --user -u discord-daemon`. `DISCORD_SESSIONS_CHANNEL_ID` is the channel that holds the threads; a private channel needs the bot added as a member.
6. Allowlist your Discord user id in `access.json` (`allowFrom`).
7. Git from unattended sessions: add the devbox's `~/.ssh/id_ed25519.pub` (setup prints it) to GitHub, then `gh auth login --git-protocol ssh` and `glab auth login --hostname <gitlab host> --token "$GITLAB_TOKEN"` on the box.
8. State sync from the laptop: `scripts/mutagen-sync-state.sh` creates the `claude-projects`, `doit`, and `vault` sessions; `scripts/mutagen-sync-giantmem.sh <alias|path>` adds a repo's `.giantmem` dirs. Sessions pause while Twingate is down and resume on their own.

## Day to day

`cvps` from a repo directory on the laptop attaches a devbox tmux session named after that directory, started in the same path. `cvps-shell` is a plain ssh. On the box, `dclaude` starts a Discord-attached session:

```
dclaude                                  # team slot
dclaude --acct ent --effort xhigh        # enterprise slot, any claude flag passes through
dclaude --resume <session-id>            # pick up a laptop session that mutagen already delivered
```

`--acct` selects the credentials slot (`CLAUDE_SECURESTORAGE_CONFIG_DIR`); `DCLAUDE_ACCT` sets the default. Inside tmux, `dclaude` also answers the three dialogs an interactive claude shows and that no flag can skip: the development-channels warning, a fresh folder's trust prompt, and the external CLAUDE.md imports prompt. That watcher stops once the prompt is up.

DM the bot from anywhere for control; sessions only read their own thread.

| DM | Effect |
|---|---|
| `list` | sessions, cwd, heartbeat age |
| `status <label>` | one session in detail |
| `send <label> <text>` | post into that session's thread |
| `tail <label> [n]` | last n inbox events |
| `kill <label>` | unregister and archive the thread |
| `projects` | repos and worktrees under `dev/` on the box, to depth 3 |
| `start [relpath] [--acct team\|ent] [--effort low..max] [--model opus\|sonnet\|fable]` | spawn `dclaude` in a tmux session at that path (no path: `scratch/`) |

Transcripts flow both ways through the `claude-projects` mutagen session, so `claude --resume <id>` works on either machine once the file has landed. `lift` (`scripts/lift-to-vps.sh`) copies one transcript by hand when sync is off. `scripts/restore-vps-tmux.sh` recreates sessions from `~/.claude/vps-sessions.yml` after a reboot. `scripts/pull-from-vps.sh <repo>` commits and pushes devbox edits and pulls them on the laptop, although git-native clones mean you can also just push from the box.

After a push to `claude-code-config`, `scripts/bootstrap-vps.sh devbox --skip-embed --skip-lsp` pulls the clone, reruns setup, and restarts the daemon. giantmem alone: `make -C giantmem deploy-devbox` in giant-tooling.

Daemon ops on the box: `systemctl --user status discord-daemon`, `journalctl --user -u discord-daemon -f`, `curl -H "x-daemon-token: $DISCORD_DAEMON_TOKEN" http://127.0.0.1:7777/sessions`. From the laptop, `ssh -L 7777:127.0.0.1:7777 devbox` and then `scripts/daemon-cli.sh` against the default URL. `scripts/backup-daemon-state.sh` pulls an age-encrypted copy of `.env`, `access.json`, and `sessions.json`.

## Troubleshooting

| Symptom | Cause and fix |
|---|---|
| `Discord start failed: DiscordjsError [TokenInvalid]` | Discord revoked the token; regenerate and set it in `.env` on both machines |
| a slot's `auth status` shows the wrong `subscriptionType` | the authorize page used the browser's active organization; switch it on claude.ai or sign in from a private window, then log in again |
| transcripts land under a `-home-...` slug | the bridge is a symlink or missing; `mount \| grep <bridge path>` on the box, rerun setup |
| stow refuses every link | `install.sh` ran from the bridged path; setup runs it from the physical home path |
| `git pull --ff-only` on the box refuses | the clone has untracked or edited files, usually from an old rsync; `git status`, clean, pull |
| mutagen session `[Paused]` | Twingate is down on the laptop; it resumes by itself. A session for a host that no longer exists: `mutagen sync terminate <name>` |
| a session started from a DM never answers | the tmux pane sits on a dialog the watcher does not know; `tmux attach -t <label>` on the box and read it |
| a thread appears for every `claude` run, `claude auth login` included | the user-scope `discord` MCP registers each run; expected, dormant entries fall out of `list` |
| `giantmem find` on the box misses a laptop doc | `.giantmem` files arrive without hooks; the ingest timer backfills live.db every ten minutes, or run `giantmem db index backfill` |
