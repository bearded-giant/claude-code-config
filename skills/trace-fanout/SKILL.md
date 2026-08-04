---
name: trace-fanout
description: Parallel multi-repo root-cause investigation. Fans out read-only agents — one per repo/data-source — each returning claims with hard citations (file:line, exact log query/SQL + output). Lead reconciles into an evidence-ranked hypothesis table. NO code edits during investigation. Auto-fires when user says "trace this across repos", "multi-repo trace", "fan out the trace", "parallel root cause", "which repo is dropping X", or invokes /trace-fanout. Skip for single-repo bugs (use debugger agent) or known-cause fixes.
---
<!-- caveman:compressed -->

Parallel evidence gathering across repos + runtime state. Hypothesis comes AFTER all agents report — never before. Kills serial log-and-guess loops.

## When to use

- Symptom plausibly spans 2+ repos / services / clusters
- Serial debugging already looped once ("same thing again")
- User names multiple candidate repos

Single repo, known file → `debugger` agent instead.

## Steps

### 1. Intake

Need: symptom (exact error/behavior), candidate repos, candidate runtime sources (logs, redis, DB, k8s). Missing pieces → wizard-style, ONE numbered question at a time.

Repos not checked out locally → `local-cerebro` covers frost/customcheckout/dapr services without checkout. Checked-out peers → `/pair-repo` conventions.

### 2. Auth preflight (BEFORE any dispatch)

Check access to every source that will be queried: `gcloud auth print-access-token`, `kubectl auth can-i`, DB MCP reachability, splunk token — whatever the trace plan needs. Anything expired → STOP, list re-auth commands for user (`! gcloud auth login` etc.), wait. Mid-investigation auth death wastes the whole fan-out.

### 3. Dispatch (parallel, read-only)

One message, multiple Task agents (Explore subagent type; cap 4):

- **Per repo** (1 each): trace the symptom's call chain. Where does the field/message/request enter, transform, exit. Return exact functions, file:line.
- **Runtime state** (1): query prod logs / redis / DB via the NAMED access paths only — no substitution. Return exact query + output.
- **Change bisect** (1, when "it worked before"): recent tags/commits/deploys touching the affected paths. Return commit shas + diff hunks.

Every agent instruction MUST include: read-only, no edits, no fix proposals; claims require citations (file:line for code, exact command + output for runtime); anything unverifiable goes in an explicit `could not verify` list, never asserted.

### 4. Reconcile

Build the hypothesis table only after ALL agents report:

| Hypothesis | Supporting evidence | Contradicting evidence | Confidence |
|---|---|---|---|

- Every cell cites agent evidence (file:line / command). No citation → row marked speculative.
- Explicit `Could NOT verify` section — never silently assert.
- Conflicting agent reports → name the conflict, do not average.

### 5. Stop

Present table + recommendation. NO code edits, NO added logging during investigation. User picks a hypothesis → then minimal fix + regression test (normal flow, or hand to `debugger` for the confirmed repo).

## Output

Report → active feature's `research/trace-{slug}.md`, else `.giantmem/research/trace-{slug}.md`. Frontmatter: `type: research`, `status: complete`, `lifecycle: candidate`, `feature:` or `repo:`. Chat gets the table + one-line recommendation only; file holds full agent evidence.

## Hard rules

- NO Edit/Write to repo code during investigation (report file exempt)
- Named access paths are contracts — agent may not substitute psql/run_sql/Snowflake MCP for a named GraphQL/scripted path
- No hypothesis ranking before all dispatched agents return
- Two reconcile rounds without a confident hypothesis → present what exists, stop; do not re-dispatch the same agents with the same instructions
