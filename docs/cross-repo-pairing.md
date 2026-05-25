# Cross-repo pairing

Coordinate changes across multiple repos from one Claude session. Replaces `/sync-feature`.

## Should you pair?

Most cross-repo work does NOT need pairing. `additionalDirectories` already lets Claude `Read`/`Edit`/`Grep`/`Glob` across both repos. Pairing is just a registry convenience for `/peer-scout`.

| Pair when | Don't pair when |
|---|---|
| Deep investigation in peer (avoid context bloat) | You know which files to change |
| 3+ peer investigations this session | ≤ 5 files per side |
| Need `active_feature` in scout briefs | Small grep is enough |
| Cross-cutting parallel edits | Trivial rename / comment |

Decision table:

| Situation | Action |
|---|---|
| Know files both sides, small | Read + Edit both, no pair |
| Quick grep on peer | inline `Grep`/`Read`, no pair |
| Deep investigation | `/pair-repo <peer>` + `/peer-scout` |
| Contract change 10+ files both sides | pair + `/peer-scout --mode edit` or `--mode parallel` |
| Specialist review | pair + `/peer-scout --agent kai:code-reviewer` |

## Commands

```bash
/pair-repo <abs-path> [--role owner|caller|sibling]   # attach
/pair-repo --unpair <name>                            # detach

/peer-scout <peer-name> "<brief>" [--mode explore|edit|parallel] [--agent <type>]
```

`--mode explore` (default) = read-only. `--mode edit` = peer edits allowed, no commit/push. `--mode parallel` = one agent per paired peer, single dispatch. `<peer-name>` optional when only one peer paired.

## Roles

Role describes the **peer**, not the parent.

| Role | Meaning | Scout focus |
|---|---|---|
| `owner` | Peer owns interface. Parent calls peer. | Exposed contracts, signatures, auth, error codes. |
| `caller` | Peer calls parent. Parent is service. | Peer's call sites, payload construction, retry. |
| `sibling` | Bidirectional / unknown. | Symmetric. |

Persisted in `peers.md`. Change via re-running `/pair-repo <path> --role <new>`.

## Storage

| Location | When |
|---|---|
| `.giantmem/features/{active}/peers.md` | active feature exists |
| `.giantmem/context/peers.md` | no active feature |

Entry shape:

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

One-directional. No record written to peer repo.

## Examples

```bash
/pair-repo /Users/bryan/dev/billing-api --role owner
/peer-scout billing-api "how does webhook auth validate JWTs? file:line please"
/peer-scout "find all callers of /api/v2/subs/update" --mode parallel
/peer-scout billing-api "rename WEBHOOK_KEY to WEBHOOK_SECRET in config + tests" --mode edit
/peer-scout billing-api "review the new auth middleware" --agent kai:code-reviewer
```

## Anti-patterns

- Pairing "just in case" before investigation.
- Pairing both directions when only one session is active (second pair is dead metadata).
- `/peer-scout --mode edit` without scoping first.
- Chaining multiple `--mode parallel` scouts — batch into one brief.

## Internals

Both commands delegate to `~/.claude/scripts/peer-probe <repo-path>`. Probe emits key=value (git_root, short_name, branch, dirty, layout, has_claude_md, active_feature). Handles `features.json` in any shape. Requires `jq`.

## Migration from `/sync-feature`

`/sync-feature`, `/read-sync`, `/update-sync`, `/sync-stop` removed. Old feature fields `sync_refs`, `sync_last_read`, `sync_file:` are inert — safe to delete. Sync files under `~/giantmem_archive/sync/` untouched.

## TL;DR

Default: single session, no pair. Pair when peer investigation is deep or repeated. Pick scout mode by task shape. Unpair when done.
