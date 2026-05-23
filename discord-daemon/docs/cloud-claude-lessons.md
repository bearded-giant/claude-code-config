# Cloud Claude — Lessons & Ongoing Notes

Running log of non-obvious findings, gotchas, and operational lore. Append new entries at the top with a date. Anything in here was either discovered the hard way or surprises new readers.

> **Format:** `## YYYY-MM-DD — title` → 1–3 paragraphs (or bullets). Include code/log snippets if they're load-bearing. Avoid restating the runbook; capture what's not in the spec.

Companion docs:
- [`cloud-claude-architecture.md`](cloud-claude-architecture.md)
- [`cloud-claude-quickstart.md`](cloud-claude-quickstart.md)
- [`cloud-claude-provisioning-runbook.md`](cloud-claude-provisioning-runbook.md)
- [`discord-daemon/HACKING.md`](../HACKING.md)

---

## 2026-05-23 — Initial provisioning lessons

Captured during the first real run; subsequently incorporated into the runbook and quickstart but kept here too as the canonical "do not relearn this" list.

- **Stow 2.3.1** on Ubuntu 24.04 won't create the target dir. `mkdir -p ~/.claude` before running `install.sh`.
- **Daemon must bind `0.0.0.0`**, not the tailnet IP. Otherwise same-host claude session-mcp can't reach the daemon over loopback. Hetzner firewall (SSH+ICMP) blocks public 7777.
- **Tailscale SSH strips file mode bits** during SFTP. Mutagen's uploaded agent lands chmod 644 → "Permission denied". Use the public IP for Mutagen sync, not the tailnet hostname.
- **`--channels`** is a hidden flag and rejects `server:` entries alone. The right invocation: `claude --dangerously-load-development-channels server:discord`.
- **MCPs must be registered via `claude mcp add`** — `mcpServers` blocks in `~/.claude/settings.json` are not auto-loaded by the CLI.
- **Stowed hooks hardcode laptop paths.** Bridge with `sudo ln -s /home/bryan /Users/bryan` plus a node symlink at the laptop's nvm path. Future fix: rewrite hook commands to use `$HOME`.
- **Private channels** require explicitly adding the bot under Channel Settings → Permissions → Add Member. Default server-wide bot permissions do not include private channels.
- **`access.json` is re-read every gate check** — allowlist additions take effect live without restart. The bundled plugin in-memory caches DM channel state, though, so restart MCP after pre-allowlist failures.
- **Initial Mutagen sync** of ~80GB raw → ~12GB post-excludes takes 30–60 min over typical home upload. The wrapper script's exclude list is non-negotiable for avoiding hundreds of plugin-cache conflicts.

## 2026-05-23 — Mutagen specifics

- Default symlink mode is `portable` which rejects any absolute-target symlink. Real-world repos have lots of these (Python venvs, our `lib/workspace → /Users/bryan/...`, dbt container paths). Use `--symlink-mode=posix-raw`. Combined with the `/Users/bryan → /home/bryan` root symlink, most laptop-absolute symlinks resolve correctly on the VPS.
- **Sync mirrors code, not runtime.** Venvs, `node_modules`, `target/`, `build/`, `dist/` are excluded. Recreate them on the VPS the first time you want to run something there.
- Sync is **alpha→beta one-way-safe** by default in `scripts/mutagen-sync-dev.sh`. Beta-only files survive but the VPS cannot ever push edits back to the laptop. Use git or `scripts/pull-from-vps.sh` to round-trip code edits.

## 2026-05-23 — Bundled discord plugin DM bug

Plugin `discord@claude-plugins-official` 0.0.4 has a `fetchAllowedChannel` bug: when fetching a DM channel by ID, `ch.recipientId` is null because the channel is partial (Partials.Channel intent). Every tool call against a DM fails with "channel not allowlisted" even when the user IS allowlisted.

Upstream fixed it at HEAD (commit `48aa4351`, PR #1365, 2026-04-14) using a different mechanism (`dmChannelUsers` cache). Marketplace hasn't published a new version yet.

Workaround:
- `scripts/patches/discord-dm-recipient.patch` — partial-fetch fallback
- `scripts/apply-discord-patch.sh` — idempotent applicator
- `hooks/discord_patch_apply.py` — SessionStart hook that re-applies after plugin cache is wiped

The daemon (our session-mcp path) does NOT have this bug — it owns the gateway and routes via thread membership, not partial DM channel introspection.

## 2026-05-23 — Daemon shutdown semantics

The daemon does **not** archive threads on `SIGTERM`. Reason: systemd default is `Restart=always`, so SIGTERM usually precedes a restart. After restart, the daemon hydrates `sessions.json`, the live sessions' heartbeats land in the loaded entries, and the threads are seamlessly reused. Archiving would orphan a fresh thread on every restart.

If you want a true teardown (e.g. retiring the VPS), set `DAEMON_ARCHIVE_ON_EXIT=1` before stopping the service. The shutdown handler will iterate the registry and archive each thread with reason `daemon SIGTERM`.

Stale entries — sessions whose claude died but heartbeat lapsed — get **marked dormant** by the periodic sweep (default 15s loop, 90s stale cutoff), not evicted. The thread is archived (Discord auto-unarchives on next send) but the `sessionId → threadId` mapping in the registry is preserved so a later `dclaude` in the same cwd reattaches to the same thread. Hard delete only via `kill <label>` DM command.

## 2026-05-23 — Permission relay scope

The daemon's permission relay (`POST /sessions/:id/permission_request` → DM with buttons) authenticates the responder via `access.allowFrom`. Buttons in guild channels are intentionally ignored — the security model is "single-user, allowlisted DM only," same as the bundled plugin.

If you want collaborator approvals, that's a wider design change: add a `permissionApprovers` list distinct from `allowFrom`, or per-tool ACLs. Not implemented.

---

## How to add an entry

```markdown
## YYYY-MM-DD — short title

1-3 paragraphs (or bullet list) describing the finding. Include:
- What surprised you / cost time
- The root cause if known
- The workaround or fix
- A pointer to code if relevant (`src/foo.ts:123`)
```

Append at the top of the file. Don't re-flow older entries.
