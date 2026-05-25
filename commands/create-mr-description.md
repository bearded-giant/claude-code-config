---
description: Create a GitLab merge request description for the current branch. Writes to active feature dir, .giantmem/, or repo root. Auto-fires when user says "draft MR description", "write up an MR", "ready for MR", "create MR description", or after a successful `git push -u origin <feature-branch>` when on a non-base branch. Skip if branch is base (main/master/stage).
---

Create a GitLab merge request description file for the current branch.

## Output location

- Active feature: `.giantmem/features/{feature}/mr-description.md`
- Else if `.giantmem/` exists: `.giantmem/mr-description.md`
- Else: `mr-description.md` in project root

Always overwrite. After writing, print the markdown in chat, then the file path on its own line.

## Steps

1. **Base branch**: check project CLAUDE.md for `mr_base_branch: <branch>`. If absent, ask user. Save their choice as `mr_base_branch: <branch>`.

2. **Branch context**: current branch, commits via `git log <base>..HEAD`, full diff via `git diff <base>..HEAD`. Read diff for understanding.

3. **Identify the theme, not the changes**: read the diff to understand what the MR *accomplishes* — the user-visible behavior change, the architectural shift, the bug fix. Write to that level. Reviewers read the diff for what changed file-by-file; the description tells them *why this MR exists* and *how the pieces fit together at a high level*.

   Group bullets by theme only when the branch genuinely has multiple distinct themes (e.g., a feature + an unrelated bug fix snuck into the same MR). Single-theme branches — even large ones spanning many files — get ONE cluster, no subheadings. Do NOT create subheadings per file or per module (`### prompt changes (file.py)`, `### graph + synthesis (graph.py, post_synthesis.py)`) — that's the diff's job, not the description's.

4. **Betaflags (diff only, NOT whole codebase)**: scan added lines for `BetaService` imports or `is_enabled(` calls. Note flag strings. Omit section if none.

5. **API endpoints**: find new/modified Flask routes. Generate curl examples using `api.rechargeapps.com`. Include example response body when inferable.

## Output structure

```markdown
# description

<optional 1-2 sentence summary if branch theme isn't obvious from bullets. Otherwise skip.>

- key change one with the why baked in
- another change in same cluster, file refs (file.py) and field types (is_admin (bool)) OK
- third bullet, can have commas and clauses, no need to split

### optional subheading for second commit/theme

- first bullet of next cluster
- second bullet, can cite symbol like TokensController.validate_claims → 404 on chat endpoints
- third bullet on same cluster

## betaflags

- `flag_name` — what it gates

## example requests

```bash
curl -X POST https://api.rechargeapps.com/... \
  -H "X-Recharge-Access-Token: $TOKEN" \
  -d '{...}'
```

example response:

```json
{...}
```
```

## Style — bullets are the format

**Bullets, not prose paragraphs.** User has consistently wanted bullets for MR descriptions. Previous attempts at prose were wrong direction.

**Length target: 3–7 bullets total.** File count is irrelevant. A branch touching 1 file = 3–7 bullets. A branch touching 15 files = 3–7 bullets. A branch touching 50 files = 3–7 bullets. The diff scales; the description does not. If you find yourself listing files or modules, stop and ask "what is the *behavior* this MR changes?" — write that instead.

**Scale test (apply before writing):** if this branch hypothetically grew to 15 files across 6 directories, what would change in the description? Answer MUST be: nothing. Same 3–7 bullets, same themes. If you can't pass this test, you're describing implementation, not change.

Bullet style:
- lowercase first letter
- no trailing period
- substantive: pack what + why into one bullet, commas/clauses OK
- describe the *behavior or architectural shift*, not the file edits — `"compound questions trigger both tools and synthesize one reply"` beats `"counts distinct tool slugs in graph.py, forces synthesize_response=True"`
- code refs are OK when they identify *what* changed at the system level (a public endpoint, a public function, a tool slug) — NOT to enumerate every internal helper that moved
- include the "why" inline when it's not obvious: `sentinel caused NoResultFound in TokensController.validate_claims → 404 on chat endpoints`
- arrows OK: `→` for cause/effect, `=` for equivalence
- past tense or present, match what reads naturally

Cluster style:
- single-theme branch (default — 95% of MRs) → ONE cluster, NO `###` subheadings, even if the branch touches many files
- multi-theme branch (rare — bundles distinct unrelated changes, e.g. a feature plus an unrelated bug fix) → one cluster per theme, separated by blank lines, optional `### short header` per cluster
- subheadings MUST describe **distinct functional themes** (`### fix unrelated JWT 404`) — NEVER files, modules, directories, layers, or stages of one feature:
  - banned: `### prompts.py changes`, `### graph + synthesis`, `### orchestrator/`, `### backend`, `### tests`, `### docs`, `### config`, `### step 1`, `### prompt layer`, `### synthesis layer`
  - all of the above are *one theme*: the feature. Use one cluster with no subheading.
- if every subheading you're considering describes a different *part of the same feature*, the answer is zero subheadings, not several

What NOT to do:
- no prose paragraphs in description body — bullets only
- no "this MR adds", "this PR introduces", "this branch implements" — drop the meta phrase, start with the verb: "adds X", "enables Y"
- no splitting one substantive bullet into three thin ones
- **no per-file or per-module subheadings.** `### prompt changes (orchestrator/prompts.py)` is wrong. `### graph + synthesis (graph.py, post_synthesis.py)` is wrong. The reviewer can read the diff for which files moved. Subheadings only exist for genuinely distinct themes (unrelated bug fix bundled in, etc.).
- no enumerating every file edited — list the *behavior change*, not the implementation walk-through
- **NO tests in the description.** Skip test files entirely. Do NOT add an "integration tests" / "unit tests" / "test coverage" cluster. Do NOT mention `tests/...` paths. Do NOT describe what the tests cover. Reviewers see test files in the diff — they don't need a recap. This rule is absolute, no exceptions.
- no recap of internal helpers, constants, or config knobs renamed — only mention if they are public surface the reviewer needs to know about
- no walking through the diff layer-by-layer (prompt → graph → adapter → tests) — that *is* describing the diff

## Example output

Single-theme branch (default — note: NO subheadings, ~5 bullets, focused on the behavior change not the file walk-through):

```markdown
# description

- enables multi-tool turns: when a turn invokes 2+ distinct tool slugs, the orchestrator fuses outputs into one synthesized reply instead of returning the last tool's output
- driver: compound merchant questions like *"what's my cancellation rate this month and how can I reduce it"* — analytics for the metric, clay for the guidance, single answer back
- the LLM is now allowed to pick multiple tools in one turn; mutual-exclusion language in the system prompt that previously forced single-tool selection is gone
- single-tool turns unchanged, reuses the existing post-synthesis model knob, statsd tagged `multi=true|false` for downstream A/B
- runbook updated so new tools auto-participate in multi-tool turns with no extra wiring
```

Multi-theme branch (only when a branch genuinely bundles distinct unrelated changes):

```markdown
# description

- enables downstream services (Clay) to distinguish admin vs merchant callers via `is_admin (bool)` + `user_email (string)` on the orchestrator chat request
- values flow through ContextVars so any tool/hook reads them mid-turn; ask_clay forwards both to support-agent's `/api/chat_integration`
- purely additive, defaults make it backward-compatible

### fix JWT claims for agent chat internal token minting

- skip account_id claim when using sentinel 9999999 fallback (admin staff without matching account) — sentinel caused NoResultFound in TokensController.validate_claims → 404 on chat endpoints
- defense-in-depth preserved: account + user_id validation still runs for internal tokens with real account IDs
```

Counter-example — what NOT to produce (too granular, per-file subheadings, walks the diff):

```markdown
# description (BAD — do not emit)

### prompt changes (`orchestrator/prompts.py`)
- drop carve-outs in selection_rules
- new MULTI_SYNTHESIS_PROMPT constant
- compose_system_prompt emits `## Combining tools` section when len(fragments) > 1
- docstrings on analyze_merchant_data + ask_clay updated

### graph + synthesis (`orchestrator/graph.py`, `orchestrator/post_synthesis.py`)
- counts distinct tool slugs
- forces synthesize_response=True
- new synthesize_multi_response aggregates direct_outputs
...
```

That style describes implementation, not behavior. Collapse the whole thing into 3–5 thematic bullets.

## Section omission

- No betaflags in diff → omit `## betaflags` entirely
- No new/modified endpoints → omit `## example requests` entirely
- Single-theme branch → no `###` subheadings, one bullet cluster

## Curl formatting — REQUIRED

Every curl command MUST be inside a fenced code block (` ```bash ` or ` ``` `). Never inline. Never bare. Even single-line curls.

Continuation lines use `\` at end. Indent continuation with 2 spaces.

```bash
curl -sS https://api.rechargeapps.com/api/internal/zendesk_mcp/support_tickets?limit=5 \
  -H "X-Recharge-Service-Auth: recharge-mcp-zendesk:$TOKEN"
```

Multiple example curls: each in its own fenced block, separated by blank line + optional one-line label.

```bash
curl -sS https://api.rechargeapps.com/api/internal/zendesk_mcp/support_tickets/mcp_json_description \
  -H "X-Recharge-Service-Auth: recharge-mcp-zendesk:$TOKEN"
```

```bash
curl -sS -X POST https://api.rechargeapps.com/api/internal/zendesk_mcp/support_tickets/mcp_translate \
  -H "X-Recharge-Service-Auth: recharge-mcp-zendesk:$TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"question": "shipping refunds in Q1 2026"}'
```

Example response (when included): separate fenced ` ```json ` block right after the curl block.

## Post-processing

After writing, tighten phrasing — drop filler words, keep bullet structure. Do NOT convert bullets to prose. Do NOT split substantive bullets into thin ones. Do NOT add periods. Do NOT add "this MR" prefixes.
