---
type: notes
status: complete
repo: claude-code-config
lifecycle: durable
---
<!-- caveman:compressed -->

# MCP OAuth: refresh tokens + access-token TTL

Notes for fixing `Claude Code` MCP servers that re-prompt the Google OAuth flow on every new session. Symptom: user authed N hours ago, opens fresh Claude Code session, instantly redirected to Google.

Applied to:

| Repo | Provider file | Tests |
|---|---|---|
| `~/dev/ai/chat-orchestrator-wt/mcp` (chat-inspector) | `chat_inspector_mcp/oauth_provider.py` | `tests/test_chat_inspector_oauth_provider.py` |
| `~/dev/ai/recharge-watchtower` (watchtower) | `app/oauth_provider.py` | `tests/test_oauth_provider.py` |

Both MCPs share the same Google→Recharge bridge pattern (watchtower is the upstream source the chat-inspector was ported from). Identical patch on both.

## Symptom

```
21:43:01 GET  /.well-known/oauth-protected-resource 200
21:43:01 GET  /mcp                                   401  → Claude Code launches DCR + Google flow
```

MCP logs in `~/Library/Caches/claude-cli-nodejs/<cwd>/mcp-logs-<name>/*.jsonl`:

```
"Token expires in: 900"
"Has refresh token: false"
```

## Root cause (orch-mcp / chat-inspector specifically)

| What backend does | What MCP told Claude |
|---|---|
| Recharge `internal_session` mints a JWT, validates rolling 30d via `/api/admin/auth/validate_credentials` | `expires_in=900` (15 min), no `refresh_token` |

`exchange_authorization_code` returned an `OAuthToken` with 15-min `expires_in` and no `refresh_token`. `load_refresh_token` returned `None`. `exchange_refresh_token` raised `NotImplementedError`. Claude Code SDK then has nothing to do at minute 15 except start over — full Google OAuth dance every time.

Per-session Dynamic Client Registration also produces a fresh `client_id` + random localhost callback port per Claude session, so token caches don't share across sessions on disk — but the 15-min TTL is the dominant reason re-auth keeps firing even within a single session past 15 min.

## Options considered

| # | Fix | Lift | Effect |
|---|---|---|---|
| 1 | Bump `_TOKEN_TTL_DEFAULT` to 24h | 1 line | Claude Code stops re-OAuthing every 15 min. `load_access_token` re-validates every request anyway, so longer cache is safe. |
| 2 | Honor underlying JWT `exp` claim | small | Aligns Claude Code cache window with real session window. Requires decoding the upstream JWT. |
| 3 | Issue `refresh_token`, implement `load_refresh_token` + `exchange_refresh_token` | medium | SDK silently refreshes. Claude Code prompts re-auth only when the upstream rolling session itself dies. |
| 4 | Pin `client_id` / skip DCR | big | Tokens shareable across sessions. Skip unless 1–3 not enough. |

Picked **#1 + #3** — refresh path covers cross-session re-auth, 24h TTL covers single-session cache churn.

## Patch applied to `chat-orchestrator-wt/mcp`

File: `chat_inspector_mcp/oauth_provider.py`

1. Added imports: `RefreshToken`, `TokenError`.
2. `_TOKEN_TTL_DEFAULT` 900 → 86400 (24h).
3. Added `_REFRESH_TTL = 30 * 86400` (30d, matches Recharge rolling session) and `_KIND_REFRESH = "refresh"`.
4. Extracted `_mint_token_pair(client_id, jwt_token, email, scopes)` — signs a `kind=refresh` JWT carrying the recharge session JWT, returns `OAuthToken` with both `access_token` and `refresh_token`.
5. Wired `exchange_authorization_code` to call `_mint_token_pair`.
6. `load_refresh_token` now verifies the signed refresh JWT (kind + client_id match) and returns `RefreshToken(token, client_id, scopes, expires_at)`.
7. `exchange_refresh_token`:
   - verifies refresh JWT
   - calls `_validate_via_recharge(jwt_token)` (re-checks rolling session is still good)
   - on `TransientAuthError` → `TokenError("invalid_grant", "session validation temporarily unavailable")`
   - on `None` (session expired) → `TokenError("invalid_grant", "underlying session expired")`
   - on success → returns rotated `_mint_token_pair` result (new refresh JWT each time)
8. `revoke_token` signature widened to `AccessToken | RefreshToken | None`; on refresh-token revocation extracts the inner JWT and drops it from the email LRU.

Refresh token contents (HS256 over `STATE_SIGNING_KEY`):

```json
{
  "kind": "refresh",
  "client_id": "<DCR client_id JWT>",
  "jwt": "<recharge session JWT>",
  "email": "<user>",
  "scopes": ["mcp:tools"],
  "iat": ..., "exp": iat + 30d
}
```

Stateless — any pod with the shared `STATE_SIGNING_KEY` can mint or verify. No new storage. Same pattern as existing `_KIND_CODE` / `_KIND_PENDING`.

## Tests added

File: `tests/test_chat_inspector_oauth_provider.py`

- `test_exchange_code_returns_refresh_token` — initial token pair has refresh_token + 24h expires_in
- `test_load_refresh_token_roundtrip` — sign → verify
- `test_load_refresh_token_rejects_wrong_client` — refresh JWT bound to issuing client_id
- `test_exchange_refresh_token_success` — happy path, new pair verifies
- `test_exchange_refresh_token_invalid_when_session_expired` — `/validate` returns None → `TokenError(invalid_grant)`
- `test_exchange_refresh_token_invalid_when_upstream_transient` — `/validate` 503 → `TokenError(invalid_grant)` (forces client re-auth instead of letting the user think they're authed when the backend is degraded)

Full suite: `543 passed`.

## Expected user-facing behavior after deploy

| Window | Before | After |
|---|---|---|
| First 15 min | works | works |
| 15 min – 24h, same session | Google OAuth dance | silent refresh, no UI |
| 24h – 30d, same session | Google OAuth dance | refresh-grant call, no UI |
| New session within 30d | Google OAuth dance | DCR + new refresh from existing recharge session (still needs `/validate` to pass — no shared client_id cache yet, see option #4) |
| 30d+ idle / backend session expired | Google OAuth dance | Google OAuth dance (expected — upstream session genuinely dead) |

Cross-session sharing still re-auths because each Claude Code session does its own DCR. Option #4 (static client_id, skip DCR) would close that gap but is out of scope for this patch. Refresh + 24h TTL covers the dominant pain — long-running sessions.

## Unrelated finding worth noting

Logs also show:

```
"HTTP Connection failed after 5297ms: Streamable HTTP error: Error POSTing to endpoint: Internal Server Error (code: 500)"
```

That 500 is downstream of a successful token issuance — tokens save, then `/mcp` POST 500s on the same client. Not the cause of re-auth, but worth investigating in MCP app logs.

## Files changed

chat-orchestrator-wt/mcp:
- `chat_inspector_mcp/oauth_provider.py` — provider patch
- `tests/test_chat_inspector_oauth_provider.py` — 6 new tests (543 pass total)

recharge-watchtower:
- `app/oauth_provider.py` — same patch
- `tests/test_oauth_provider.py` — updated `expires_in` assertion (900 → 86400), 6 new refresh tests (95 pass total)

## Followups

- Decide whether to pursue option #4 (static DCR) so a single Google login covers every Claude Code session machine-wide.
- Triage the 500 on `/mcp` POST after successful auth (chat-inspector only).
- Confirm Recharge `internal_session` rolling window is still 30d — `_REFRESH_TTL` assumes it. If shorter, drop `_REFRESH_TTL` to match so the refresh JWT can't outlive the backend session.
