---
description: "Attach a peer repo to the current session for cross-repo coordination. Captures peer metadata, registers as an additional working dir, primes the session on coordination pattern."
argument-hint: "<abs-path-to-peer-repo> [--role owner|caller|sibling]"
---

Pair a peer repo into this session so the main thread owns the cross-cutting plan and sub-agents do deep dives in the peer. Replaces the deprecated `/sync-feature` pattern (two sessions + shared file = doesn't work).

## Why this exists

Two Claude sessions coordinating via shared file failed in practice: stale views, async drift, human shuttling messages between tabs. Single session with both repos accessible + sub-agents for peer exploration keeps plan coherent and context clean.

## Arguments

- `abs-path-to-peer-repo`: absolute path to the peer repo's git root. Required.
- `--role`: (optional) relationship from **parent's perspective** (parent = current repo where this command runs). Written to peer record; drives `/peer-scout` brief (direction + focus).
  - `owner`: parent **calls** peer. Peer is downstream (service/lib parent depends on). Scout focuses on peer's exposed contracts.
  - `caller`: peer **calls** parent. Parent is the service, peer is the consumer. Scout focuses on peer's call sites into parent.
  - `sibling` (default): bidirectional or unknown. Scout stays neutral.

  Mnemonic: role describes the **peer**. "peer is the owner" → parent is consumer. "peer is the caller" → parent is service.

## Steps

1. **Validate peer path**
   - Run `git -C <peer-path> rev-parse --show-toplevel`. If non-zero exit, error: "Not a git repo: <path>". Stop.
   - Normalize to absolute canonical path (output of `rev-parse --show-toplevel`).
   - Reject if peer path == current repo path (`git rev-parse --show-toplevel`). "Peer must be a different repo."

2. **Capture peer metadata** (one-shot, terse)
   - Peer short name: `basename <peer-path>`.
   - Peer branch: `git -C <peer-path> rev-parse --abbrev-ref HEAD`.
   - Peer status (dirty?): `git -C <peer-path> status --porcelain | wc -l`.
   - Peer top-level layout: `ls <peer-path>` (one line).
   - Peer's CLAUDE.md path if exists: `<peer-path>/CLAUDE.md`.
   - Peer's `.giantmem/features/features.json` active feature (if any): parse, grab `in_progress` name.

3. **Ensure peer dir is accessible**
   - Check `settings.json` + `settings.local.json` `permissions.additionalDirectories`. If peer path (or a parent of it) already listed: OK.
   - Else: tell the user one of these three options, let them pick:
     1. Add to `settings.local.json` (session-scoped; takes effect next restart) — I can write it.
     2. Run built-in `/add-dir <peer-path>` now (live, this session only).
     3. Re-launch claude with `--add-dir <peer-path>`.
   - If user picks 1: merge peer path into `permissions.additionalDirectories` in `~/.claude/settings.local.json` (create file if missing, preserve other keys).

4. **Persist peer record**

   Determine scope:
   - Active feature exists (`in_progress` in `.giantmem/features/features.json`) → write to `.giantmem/features/{active}/peers.md`.
   - No active feature → write to `.giantmem/context/peers.md`.

   Append (or create) an entry block:
   ```markdown
   ## <peer-short-name>

   - path: <abs-path>
   - role: <role>
   - branch: <branch>
   - dirty: <yes|no>
   - active_feature: <name or "-">
   - paired: <YYYY-MM-DD HH:MM>
   - layout: <ls oneline>
   ```

   If the peer already has an entry (match by path), overwrite in place — do not duplicate.

5. **Prime the session brief**

   Print this block verbatim to the user (and keep it in conversation context — do not silently drop):

   ```
   Paired: <peer-short-name> (<role>) @ <abs-path>
     branch: <branch>   dirty: <yes|no>   active feature: <name or ->

   Coordination pattern:
     - This session owns the plan + cross-cutting edits.
     - For deep dives in <peer-short-name>, run:
         /peer-scout <peer-short-name> "<question or task>"
       Sub-agent reads/reports, main session stays clean.
     - For parallel edits across both repos, spawn two sub-agents in parallel
       (one per repo) from the main thread.

   Peer record: <path-to-peers.md>
   ```

6. **Output summary**
   - Mode used (added to settings / used existing / add-dir suggested).
   - Peer short name and role.
   - Peer record path.
   - Reminder of `/peer-scout` for sub-agent dispatch.

## Unpair

If user passes `--unpair <peer-short-name>`:
- Remove the entry from `peers.md` (match by short name or path).
- Do NOT touch `settings.json` / `settings.local.json` (user may have other reasons to keep dir access).
- One-line confirmation.

## Notes

- Multiple peers supported — run `/pair-repo` multiple times. Each gets its own entry in `peers.md`.
- `peers.md` is the source of truth for `/peer-scout` to look up paths by short name.
- Do not write to the peer repo's `.giantmem/` — respect its boundary. Coordination state lives only in this session's workspace.
