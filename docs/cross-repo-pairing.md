# Cross-Repo Pairing

Coordinate changes across two (or more) repos from a single Claude Code session. Replaces the deprecated `/sync-feature` pattern.

## Why

Two Claude sessions coordinating via shared file (the old `/sync-feature` approach) failed in practice:

- Each session carried a stale view of peer state.
- Async writes + no interrupts meant the human shuttled messages between tabs.
- Coordination became a chat protocol reinvented through markdown.

Single session with both repos accessible + sub-agents for peer deep dives keeps the plan coherent and the main context clean.

## Should you pair at all?

Most cross-repo work does **not** need `/pair-repo`. Your `additionalDirectories` permission already covers both repos when both live under `~/`; Claude can `Read`/`Edit`/`Grep`/`Glob` across both paths inline. Pairing adds nothing to file access — it's a registry convenience for `/peer-scout`.

Sanity check — answer before pairing:

1. Do you already know which files on each side need to change? **Yes** → no pair, edit both directly.
2. Does the change touch ≤ 5 files per side? **Yes** → no pair.
3. Is the peer repo huge (monorepo, deep trees, lots of call sites)? **Yes** → pair + scout. Sub-agent isolation saves context.
4. Will you investigate the peer 3+ times in this session? **Yes** → pair (short-name resolution beats re-typing paths).
5. Do you need active_feature context surfaced in sub-agent briefs? **Yes** → pair (probe captures `active_feature`).
6. Will cross-cutting edits run in parallel across both repos? **Yes** → pair + `/peer-scout --mode parallel`.

If every answer says "no pair," just work on both paths directly.

### Decision table

| Situation | Command |
|---|---|
| Know files on both sides, small change | nothing — Read + Edit both |
| Small investigation, quick grep on peer | nothing — `Grep`/`Read` inline on peer path |
| Deep investigation in peer, don't want context bloat | `/pair-repo <peer>` then `/peer-scout <name> "<question>"` |
| Repeated investigations on same peer | `/pair-repo <peer>` once, then `/peer-scout` N times |
| Contract change hitting 10+ files both sides | `/pair-repo <peer>`, then `/peer-scout` with `--mode edit` or `--mode parallel` |
| Specialist review of peer (security, correctness) | `/pair-repo <peer>`, then `/peer-scout` with `--agent kai:code-reviewer` |
| Two active features, one per repo, both driven | Two sessions, each `/pair-repo`s the other. Rare. |

## Model

| Layer | Responsibility |
|-------|---------------|
| Main session | Owns the plan, cross-cutting edits, synthesis |
| `/pair-repo` | Attaches peer repo, captures metadata, primes the brief |
| `/peer-scout` | Dispatches sub-agent into the peer — isolated context, returns summary |
| `peers.md` | Per-session record of paired repos + roles (no cross-session shared state) |

No background polling, no shared file, no `sync_*` metadata on features. The sub-agent report is ephemeral and lives only in the main session's context.

## Commands

### `/pair-repo <abs-path> [--role owner|caller|sibling]`

Attach a peer repo. Captures branch, dirty state, active feature, top-level layout. Writes a block to `peers.md`. If the peer path isn't reachable via `additionalDirectories`, offers three options: write to `settings.local.json`, run the built-in `/add-dir` now, or relaunch with `--add-dir`.

`--unpair <name>` removes the entry. Multiple peers supported — run `/pair-repo` once per peer.

### `/peer-scout <peer-name> "<brief>" [--mode explore|edit|parallel] [--agent <type>]`

Dispatch a sub-agent into a paired peer.

Modes:
- `explore` (default) — read-only. Grep/Read/Glob only.
- `edit` — allow peer edits. No commit, no push.
- `parallel` — spawn one agent per paired peer in a single message.

`--agent <type>` overrides the default sub-agent (e.g. `kai:code-reviewer`, `debugger`).

If only one peer is paired, `<peer-name>` may be omitted.

## Roles

Role describes the **peer**, not the parent. Parent = the repo the session is running in.

| Role | Meaning | Scout focus |
|------|---------|-------------|
| `owner` | Peer owns/exposes an interface. Parent calls peer. | Exposed contracts, endpoint signatures, request/response shapes, auth requirements, error codes. Report what parent needs to call peer correctly. |
| `caller` | Peer calls into parent. Parent is the service. | Peer's call sites into parent, payload construction, response/error handling, retry/timeout, cached assumptions. Report how parent changes break peer. |
| `sibling` | Bidirectional or unknown. | Symmetric. Report findings as asked, flag whichever direction matters. |

Role is persisted in `peers.md` and injected into every scout brief's `Direction` + `Focus` lines. Change via re-running `/pair-repo <path> --role <new>` (overwrites entry).

### Same question, different role

```
/peer-scout billing-api "how does auth work?"
```

- `role=owner` → peer reports the tokens/headers parent must send.
- `role=caller` → peer reports how it obtains/caches/refreshes parent's tokens, what breaks on key rotation.
- `role=sibling` → both sides, user picks.

Same logic for impact analysis on a contract change: scout with `owner` checks peer's public surface for shape drift; `caller` checks peer's consumption sites for breakage.

## Usage

### Attach a peer

```
/pair-repo /Users/bryan/dev/billing-api --role owner
```

Output:
```
Paired: billing-api (owner) @ /Users/bryan/dev/billing-api
  branch: main   dirty: no   active feature: -

Coordination pattern:
  - This session owns the plan + cross-cutting edits.
  - For deep dives in billing-api, run:
      /peer-scout billing-api "<question or task>"
    Sub-agent reads/reports, main session stays clean.
  - For parallel edits across both repos, spawn two sub-agents in parallel
    (one per repo) from the main thread.

Peer record: .giantmem/features/webhook-refactor/peers.md
```

### Quick read-only question

```
/peer-scout billing-api "how does webhook auth validate JWTs? file:line please"
```

Dispatches an `Explore` sub-agent scoped to the peer path. Returns findings, main context unchanged.

### Check across both repos in parallel

```
/peer-scout "find all callers of /api/v2/subs/update" --mode parallel
```

One agent per paired peer, single message dispatch. Each peer's role drives its own `Direction/Focus` in the brief.

### Let the scout edit the peer

```
/peer-scout billing-api "rename WEBHOOK_KEY to WEBHOOK_SECRET in config + tests" --mode edit
```

Edits allowed, no commit, no push. Scout lists every file modified in its report.

### Use a specialist agent

```
/peer-scout billing-api "review the new auth middleware for security gaps" --agent kai:code-reviewer
```

### Coordinate cross-cutting edits

Main session drafts the plan (API contract, shared types) → dispatches one `--mode edit` scout per paired repo in parallel with matching briefs → applies matching changes in parent directly. No file-based handoff.

### Detach

```
/pair-repo --unpair billing-api
```

Removes the entry from `peers.md`. Does not touch `settings.json` / `settings.local.json` — user may want to keep directory access for other reasons.

## Storage

Peer record lives per-session:

- Active feature → `.giantmem/features/{active}/peers.md`
- No active feature → `.giantmem/context/peers.md`

Entry format:

```markdown
## billing-api

- path: /Users/bryan/dev/billing-api
- role: owner
- branch: main
- dirty: no
- active_feature: -
- paired: 2026-04-24 15:32
- layout: api  docs  migrations  src  tests
```

No equivalent record is written to the peer repo. Coordination state is one-directional and lives only in the session that initiated the pairing.

## When not to use

- Peer work is genuinely independent. Just open a second session; no coordination needed.
- Peer repo is too large for even a sub-agent to navigate usefully — consider adding `domains/` JSONs to peer via its own `/plan-feature` workflow first.
- Contract change is trivial (rename, comment) — edit directly in parent, let peer catch up on its own schedule.

## Internals

Both commands delegate peer metadata capture to `~/.claude/scripts/peer-probe <repo-path>`. The probe outputs key=value lines (git_root, short_name, branch, dirty, layout, has_claude_md, active_feature) and handles `features.json` in any shape: list-of-dicts (`{"features": [...]}`), dict-keyed-by-name (`{"features": {...}}`), or top-level dict. Requires `jq`.

If you previously saw Claude spawn 6+ bash calls with inline `python -c` during `/pair-repo` and hit `AttributeError: 'list' object has no attribute 'items'` on cross-repo schema drift — that path is closed. The probe is the single source.

## Migration from `/sync-feature`

The old commands (`/sync-feature`, `/read-sync`, `/update-sync`, `/sync-stop`) and the `sync-feature` skill have been removed. Old feature metadata fields `sync_refs`, `sync_last_read`, and the `sync_file:` line in `facts.md` are inert — safe to delete but not required to. The sync files under `~/giantmem_archive/sync/` are untouched by this change; delete manually if no longer needed.

## Anti-patterns

- Pairing "just in case" before any investigation — adds noise without payoff.
- Pairing both directions when only one session is active — second pair is dead metadata.
- Using `/peer-scout --mode edit` for changes you haven't scoped. Always explore first, edit second.
- Chaining multiple `--mode parallel` scouts in a row — each dispatch is expensive. Batch into one brief covering all questions.

## TL;DR

Default: single session, no pair. Pair when peer investigation is deep or repeated. Pick scout mode by task shape (`explore` / `edit` / `parallel` / `--agent <specialist>`). Unpair when done.
