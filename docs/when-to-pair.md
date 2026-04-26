# When to Pair — Sanity Check

Decide up-front whether cross-repo work needs pairing at all, and if so what flavor. Most cross-repo work does **not** need `/pair-repo`. Start here before invoking it.

## Default: single session, no pair

Your `additionalDirectories` permission already covers both repos (if both live under `~/`). Claude can `Read`, `Edit`, `Grep`, `Glob` across both paths right now. Pairing adds nothing to file access — it's a registry convenience for `/peer-scout`.

Start direct. Escalate to pairing only when the checklist below says so.

## Sanity check — answer before pairing

1. Do you already know which files on each side need to change?
   - **Yes** → no pair. Edit both directly.
   - **No** → continue.

2. How many files per side does the change touch?
   - **≤ 5 per side** → no pair. Edit direct.
   - **More, or unknown** → continue.

3. Is the peer repo huge (monorepo, deep trees, lots of call sites)?
   - **Yes** → pair + scout. Sub-agent isolation saves context.
   - **No** → continue.

4. Will you investigate the peer 3+ times in this session?
   - **Yes** → pair (registers peer for repeated scouts; short-name resolution beats re-typing paths).
   - **No** → one-off Grep/Read inline is fine, no pair.

5. Do you need active_feature context surfaced in sub-agent briefs?
   - **Yes** → pair. Probe captures peer's `active_feature`, scout includes it.
   - **No** → no pair.

6. Will cross-cutting edits run in parallel across both repos?
   - **Yes** → pair + `/peer-scout --mode parallel`. One agent per repo, single dispatch.
   - **No** → no pair, or pair without parallel.

If every answer says "no pair," just work on both paths directly.

## Decision table

| Situation | Command |
|-----------|---------|
| Know files on both sides, small change | nothing. Read + Edit both |
| Small investigation, quick grep on peer | nothing. `Grep`/`Read` inline on peer path |
| Deep investigation in peer, don't want context bloat | `/pair-repo <peer>` then `/peer-scout <name> "<question>"` |
| Repeated investigations (same peer, multiple questions) | `/pair-repo <peer>` once, then `/peer-scout` N times |
| Contract change hitting 10+ files both sides | `/pair-repo <peer>`, then `/peer-scout <name> "<task>" --mode edit` or `--mode parallel` |
| Specialist review of peer (security, correctness) | `/pair-repo <peer>`, then `/peer-scout <name> "<scope>" --agent kai:code-reviewer` |
| Two active features, one per repo, both driven | Two sessions, each `/pair-repo`s the other. Rare. |

## Pair flavor selection

Once you've decided to pair, pick the right scout mode.

### `/pair-repo` alone (no scout yet)
- You want peer in the registry so short-name works.
- You'll investigate later in the session, not sure when.
- Minimal overhead — just metadata capture + peers.md entry.

### Pair + `/peer-scout --mode explore` (default)
- Read-only investigation of peer.
- Sub-agent returns structured summary, main context clean.
- Use for: "find call sites," "what's the shape of X," "how does Y validate Z."

### Pair + `/peer-scout --mode edit`
- Sub-agent edits files in peer. No commit, no push.
- Use for: mechanical rename, config key update, code move isolated to peer.
- Risk: sub-agent context can't see parent edits in progress. Brief must be complete.

### Pair + `/peer-scout --mode parallel`
- One agent per paired repo, single dispatch.
- Use for: "check both sides for usages of X" or "apply matching renames in both repos."
- Best when task is symmetric across repos.

### Pair + `/peer-scout --agent <specialist>`
- Override default sub-agent type (e.g., `kai:code-reviewer`, `debugger`, `kai:backend-engineer`).
- Use when the task needs domain expertise, not just exploration.

## Concrete examples

### Example 1: small cross-cut, no pair
> "Add a new header `X-Request-Id` that orchestrator sets and agent-chat forwards."

You know the two files. Edit both. Done. No pair.

### Example 2: investigation first, then direct edit
> "Something about agent-chat's auth handling is mismatched with orchestrator's expectations."

Start in orchestrator session. Inline Grep on agent-chat path to find auth call sites. If results are <20 hits, read them directly. If investigation sprawls (grep returns 200 matches across many patterns), pair + scout.

### Example 3: deep investigation
> "How does agent-chat handle orchestrator's 429 backoff? I need to change backoff policy and want to know what breaks."

Pair + scout. Sub-agent reads retry logic, tests, config. Returns summary. You decide policy change. Edit orchestrator directly.

### Example 4: contract change, symmetric edits
> "Rename `session_tier` → `plan_tier` in the envelope schema. Both sides have validators and test fixtures."

Pair + `/peer-scout --mode parallel "rename session_tier to plan_tier in all validators, types, fixtures, and tests"`. One agent per repo. Main session applies matching changes in current repo in parallel (or waits for agents and reviews).

### Example 5: security review of peer
> "Before I change orchestrator's token minting, audit agent-chat's token consumption for assumptions."

Pair + `/peer-scout agent-chat "audit all assumptions about orchestrator tokens: claims, expiry, refresh, caching" --agent kai:code-reviewer`.

## When to stop pairing

- Feature closes → `/pair-repo --unpair <name>`. Or leave — peers.md archives with feature on `/complete-feature`.
- You realize the pair wasn't necessary → unpair + work direct. Cost of backing out is low.
- Scout reports keep returning "I couldn't find enough context" → peer repo may need its own `domains/` JSONs via `/plan-feature` first.

## Anti-patterns

- Pairing "just in case" before any investigation — adds noise without payoff.
- Pairing both directions when only one session is active — second pair is dead metadata.
- Using `/peer-scout --mode edit` for changes you haven't scoped. Always explore first, edit second.
- Chaining multiple `--mode parallel` scouts in a row — each dispatch is expensive. Batch into one brief covering all questions.

## TL;DR

Default: single session, no pair. Pair when peer investigation is deep or repeated. Pick scout mode by task shape (explore / edit / parallel / specialist). Unpair when done.
