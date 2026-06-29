---
name: vuln-triage
description: Forensic triage + verification of a security/bug report (HackerOne, SEC/JIRA ticket, IDOR, cross-tenant, auth bypass) BEFORE trusting or fixing it. Three-layer evidence chain — verbatim code trace, prod logs (Splunk), ground-truth DB rows — to confirm a vuln is real vs a misdiagnosis. Auto-fires when user says "triage this report", "verify this vulnerability", "is this HackerOne/SEC report real", "trace this IDOR / cross-tenant / auth bypass", "confirm the vuln before fixing", "I can't reproduce this issue", or hands a SEC/H1 ticket + evidence files. Pairs with local-cerebro (code), watchtower splunk (logs), dba-mcp (DB).
---
<!-- caveman:compressed -->

Verify a security report end-to-end before believing it OR fixing it. Many "vulns" are misdiagnoses (one user with multi-store membership read as cross-tenant; a 200 read as disclosure). The reporter, the ticket, and even the security team's static read are CLAIMS — prove each against running prod.

## Core principle

Report / code / docs / comments = snapshots. **Live prod (Splunk logs + DB rows) = truth.** Adversarially verify every load-bearing claim. The bug exists only if the served identity/resource actually belonged to a DIFFERENT principal than the actor — confirm that, don't assume it.

## When to use

- Triaging a HackerOne / SEC / JIRA vuln report, esp. IDOR, broken access control, cross-tenant, auth bypass.
- "I can't reproduce this" — often because it's not a real bug; this finds out why.
- Before writing a fix for a reported auth hole (avoid fixing a non-bug — see SEC-3953: a global cache "fix" broke ~38 test shards chasing a misdiagnosis).

## Not for

- Writing the fix (that's after verdict=real). Authoring detections only (use splunk skill).
- Repos already checked out + small — read code directly, skip cerebro.

## Method — 4 phases

### Phase 0 — Ground the claim
Read the report (XML/JIRA), repro steps, and EVERY evidence file. Extract exact identifiers into a scratch list:
- request_ids, session id/sid, attacker IP, hosts/subdomains
- store_id / account_id / user_id / object ids, timestamps (note tz; convert to UTC)
- precise HTTP shape (method, path, query, headers, cookie names)
Separate what the report ASSERTS from what it PROVES. List the claims you'll refute.

### Phase 1 — Trace the code (read-only, VERBATIM)
Pull verbatim code at every auth/decision checkpoint the report names. Never paraphrase code — quote it with file:line.
- Repo not checked out → `local-cerebro` skill: `~/.claude/skills/local-cerebro/scripts/cerebro-ask.sh "NAME the repo + ask; cite files" opus`. One question/call, stateless.
- Big/high-stakes (ultracode) → `Workflow`: parallel pull each checkpoint → synthesize runtime trace → adversarial verifiers each try to REFUTE a load-bearing claim via cerebro. (Refuting overturned both my and the security team's first guesses on SEC-3953.)
- Then find the ONE determining fact — the branch/return that decides allow-vs-deny — and verify it DIRECTLY. Do not let the synthesis ASSUME it. (SEC-3953 hinged on whether `_user_has_access_to_store` returns `(None,None)` or `(store,None)` when account is None.)
- Answer: what does the code do for a TRUE outsider (independent principal, no membership)? Usually that's the 401/deny path — meaning the PoC needs something the report omitted.

### Phase 2 — Confirm against prod (truth)
Do NOT stop at code. Pull the ACTUAL requests + entities.

Splunk (watchtower MCP, `splunk_search` / `splunk_create_job`+`splunk_job_results` for big windows):
- find the PoC request_ids; read served identity, status, resolved store, response size.
- aggregate the WHOLE attacker session: every (store, served account_id, served user_id, status) — does any foreign identity ever appear?
- monolith app logs: `index=k8s-customcheckout-prod sourcetype=customcheckout`; edge: `index=k8s-nginx-ingress-prod`. Useful fields: `funcName=log_request_end` (has `jwt_claims.*`, `store_id`, `status_code`), `log_request_start` (pre-auth — `store_id=null` here; do NOT read auth state from it), `remote_addr`, `session_sid`, `bytes_sent` (nginx).

DB (dba-mcp-prod MCP, `execute-query-<db>-database`, read-only):
- ground-truth the entities that decide the boundary. Ownership/membership rows.
- find tables first: `information_schema.tables WHERE table_name LIKE '%x%'`; columns via `information_schema.columns`. (Recharge: `customcheckout.account` (singular), cols `user_id,store_id,is_owner,...`; one User → many Accounts, one per store.)

### Phase 3 — Reconcile + verdict
Code says X, prod says Y, report says Z — state divergence directly (code wins over docs; prod wins over code's theory). Verdict = real only if served identity/resource ≠ the acting principal's own. Else misdiagnosis. Note residual hardening separately (defense-in-depth ≠ active exploit).

## False-positive traps (check every one)

| Trap | Test |
|---|---|
| HTTP 200 ⇒ "disclosure" | Did the body actually contain FOREIGN data? 200 alone proves nothing. |
| Different id, same data | Identical `bytes_sent` across varied id/param = identical payload = param inert / own resource returned. Cheapest decisive test. |
| Cross-tenant claim | Is served `user_id` CONSTANT across the "victim" stores? Constant = same actor. Multi-store membership ≠ breach. |
| "logged out / jwt_claims empty" | Read `log_request_end`, not `log_request_start` (start = pre-auth). |
| "two independent accounts" | gmail `+`-aliases / SSO collapse to one User. Check DB: same `user_id`? |
| "audit mis-attributed to victim" | Owner-attribution can be CORRECT — the owner really acted. |

## Decisive questions

- IDOR / cross-tenant: did the served account/resource belong to a DIFFERENT tenant than the authenticated principal? → DB ownership query settles it.
- Auth bypass: trace to the allow/deny branch; what is its input for a genuine outsider? Verify that branch verbatim.

## Tools

| Need | Tool |
|---|---|
| Verbatim code, repo not checked out | `local-cerebro` skill (cerebro-ask.sh) |
| Big code trace + adversarial refute | `Workflow` (parallel pull → synth → refute → verify the deciding fact) |
| Prod request logs | watchtower `splunk_search` (tight window) / `splunk_create_job`+`splunk_job_results` (wide) |
| Ground-truth entities | `dba-mcp-prod` `execute-query-<db>-database` (read-only) |
| Evidence files | `Read` the report XML + repro + all attachments first |

## Output — engineering analysis doc

Write `<TICKET>-engineering-analysis.md` next to the evidence. Shape:
1. Header + **Verdict** (real / misdiagnosis) + recommendation.
2. TL;DR (one paragraph: the actual mechanism).
3. Evidence chain, 3 layers: verbatim code gate → Splunk served-identity/status/byte proof → DB ground truth.
4. Per-claim refutation table (report claim | prod reality).
5. Reconciliation + why it (didn't) reproduce.
6. Residual hardening (minor, non-exploit) — kept separate from the verdict.
7. Appendix: every query + identifier, so a reviewer re-verifies independently.

Security doc overturning a High finding → write CLEAR prose (not caveman); precision + credibility over compression.

## Worked example

SEC-3953 (H1 "cross-tenant admin read/write via apex cookie", rated High). Method verdict: **misdiagnosis**. Code gate 401s a true outsider; Splunk showed served `user_id` constant 448668 across all stores + `/api/store` returned identical 3417 bytes for every `store_id` param (inert); DB `account` showed user 448668 `is_owner=1` on BOTH "independent" stores. One user, own stores. Full writeup: `~/Desktop/SEC-3953/SEC-3953-engineering-analysis.md`.
