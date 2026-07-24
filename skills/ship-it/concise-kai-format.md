# Concise-kai MR format

Wired default for the GitLab org path in `ship-it` Step 3. Keeps kai's exact
section headers; enforces THIS density instead of the kai default template's
paragraph-per-section verbosity. `--full`/`standard` opts back into the verbose
kai template when a high-risk MR genuinely needs it.

## Rule

Use kai's exact section headers (below). Do NOT expand into the kai default
template's paragraph-per-section verbosity. Every section = minimum signal.
Caveman the prose (drop articles/filler/hedging, fragments OK).

- `## Description`: 1 line problem, then the change as tight bullets. Name the mechanism (key/header/flag/field), not prose. Include the one non-obvious WHY (e.g. why header not body).
- `## Impacted Areas`: functional area(s), 1-2 bullets. Not file lists.
- `## Related Issues`: ticket or `N/A`.
- `## Post Deploy Monitoring`: 1 concrete check (metric or MCP/query call). Skip dashboards prose.
- `## How to QA`: 1 bullet, the actual steps inline. No numbered walkthrough.
- `## Post Deploy Action`: `None` or the single action.
- `## Risk Assessment`: `:green_circle: LOW - <one clause>` + kill switch. (yellow/red as warranted.)

Cut: restated context, per-file change lists, multi-step QA numbering, monitoring
prose, "this ensures/allows" filler. Keep: mechanism names, flags, keys, kill switch,
the one WHY that isn't obvious from the diff.

Preserve code identifiers exactly (keys, headers, env vars, paths). Never caveman those.

## Scope gate (MUST run before ship-it Step 4)

MR desc is reviewer-facing: WHAT changed, WHY correct, risk. NOT the investigation story.
FAIL + cut if any line carries workspace/investigation narrative:
- how-we-figured-it-out saga ("phantom handoff", "turned out", "no infra gap", "root cause was")
- internal decisions/agreements ("agreed", "decided to", "reuse-X = agreed")
- what does NOT exist / paths not taken ("no eval GSA exists", "was void")
- doit/feature/session references

Keep only: the change, the mechanism, the one WHY a reviewer needs, verification, risk.
Workspace context belongs in .giantmem/, never the MR.

## Density gate (MUST run before ship-it Step 4)

After writing `mr-description.md`, re-read it. FAIL if any bullet:
- has articles (a/an/the) or filler (this ensures / allows / in order to / we now)
- is a full sentence where a fragment carries the same signal
- restates diff context or lists per-file changes

Rewrite every failure to fragment density (see exemplar). Only then open the MR.
This gate is not optional — the format was under-applied when skipped.

## Section template

```text
## Description
<1-line problem>. <what/why in tight bullets naming the mechanism>

## Impacted Areas in Application
- <functional area>

## Related Issues
<ticket or N/A>

## Post Deploy Monitoring
- <one concrete check>

## How to QA
- <steps inline, one bullet>

## Post Deploy Action
<None or single action>

## Risk Assessment
:green_circle: LOW - <one clause>. Kill switch <FLAG=0>.
```

## Exemplar (target density)

```text
## Description
Analytics agent saw only orchestrator-reconstructed query, never merchant's raw question. No way to trace merchant intent to agent SQL.

Now capture raw merchant turn text, tie to each `analyze_merchant_data` call, two ways:

- **Audit/MCP:** `audit:outbound` record carries `user_message` (raw, redacted) next to `sent_prompt.query` (reconstruction). One record = raw + reconstruction + response; surfaces via MCP `get_downstream_prompt`.
- **Wire header:** `POST /api/v2/analyze` sends `X-User-Message` (raw, percent-encoded, capped 1024). Header not body — free text is unicode/newline/CRLF-injectable. Flag `LG_ANALYTICS_SEND_USER_MESSAGE` (default on).

Analytics-only. Clay / tool_summary unchanged.

## Impacted Areas in Application
- Analytics tool outbound path + audit stream (orchestrator).

## Related Issues
N/A

## Post Deploy Monitoring
- MCP `get_downstream_prompt` on a fresh analytics turn shows `user_message` + `sent_prompt.query`.

## How to QA
- Run open-ended analytics turn. Confirm audit record has raw `user_message`; `X-User-Message` header present + `unquote`s to raw. Flag `=0` drops header, keeps audit.

## Post Deploy Action
None. Data team wires `X-User-Message` into their GCS separately.

## Risk Assessment
:green_circle: LOW - additive audit field + additive header, agent ignores until wired. No change to query/body/response. Kill switch `LG_ANALYTICS_SEND_USER_MESSAGE=0`.
```
