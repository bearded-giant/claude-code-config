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

3. **Group changes into clusters**: each logical change (often one commit, sometimes multiple related commits) becomes one cluster of bullets. Multi-commit branches with distinct themes get multiple clusters separated by blank lines or `### subheading` lines.

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

Bullet style:
- lowercase first letter
- no trailing period
- substantive: pack what + why into one bullet, commas/clauses OK
- include code refs when they help the reviewer: file paths (`tokens_controller.py`), function names (`TokensController.validate_claims`), endpoints (`/api/chat_integration`), field names with types (`is_admin (bool)`, `user_email (string)`)
- include the "why" inline when it's not obvious: `sentinel caused NoResultFound in TokensController.validate_claims → 404 on chat endpoints`
- arrows OK: `→` for cause/effect, `=` for equivalence
- past tense or present, match what reads naturally

Cluster style:
- group related bullets together (no blank lines within cluster)
- separate clusters with blank lines
- multi-commit branches: optional `### short header` per cluster
- single-commit/single-theme branches: one cluster, no header

What NOT to do:
- no prose paragraphs in description body — bullets only
- no "this MR adds", "this PR introduces", "this branch implements" — drop the meta phrase, start with the verb: "adds X", "enables Y"
- no splitting one substantive bullet into three thin ones
- no listing changed files (the diff handles that)
- **NO tests in the description.** Skip test files entirely. Do NOT add an "integration tests" / "unit tests" / "test coverage" cluster. Do NOT mention `tests/...` paths. Do NOT describe what the tests cover. Reviewers see test files in the diff — they don't need a recap. This rule is absolute, no exceptions.

## Example output

```markdown
# description

- enables downstream services (Clay) to distinguish admin vs merchant callers
- adds is_admin (bool) and user_email (string) to orchestrator inbound chat request
- note: customcheckout resolves both at the agent_chat endpoint and sends in the POST body

- values flow through ContextVars so any tool or hook can read them during a turn
- ask_clay tool forwards both to support-agent's /api/chat_integration

- purely additive, defaults (is_admin=False, user_email=None) make it backward-compatible

### fix JWT claims for agent chat internal token minting

- remove duplicate store_id claim — already in base JWT from recharge_api_token_dto
- skip account_id claim when using sentinel 9999999 fallback (admin staff without matching account)
- sentinel caused NoResultFound in TokensController.validate_claims → 404 on chat endpoints
- remove stale comment in tokens_controller.py (redundant with outer is_internal guard)
- preserve defense-in-depth: account existence + user_id validation still runs for internal tokens with real account IDs
- only scope-subset check bypassed for internal callers (unchanged from original design)

### v2.2 chat path

- passed chart data straight to frontend with no fallback — analytics tables were invisible
- added markdown table conversion with proper value formatting (currency, integers, percentages) handling the column format from the orchestrator
- threaded charting beta flag through both POST and GET message paths so tables render consistently on send and history reload
```

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
