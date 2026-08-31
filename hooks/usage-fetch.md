# usage-fetch

Pulls Claude.ai usage data (5h/7d rate limits) from the browser and displays it in the Claude Code statusline.

## How it works

1. Reads encrypted cookies from Brave's SQLite DB (Keychain + AES-128-CBC decryption)
2. Calls `claude.ai/api/organizations/{orgId}/usage` for each chat-capable org
3. Writes results to `~/.cache/claude-usage/cache.json` (60s TTL)
4. `statusline.js` reads the cache synchronously and spawns a background refresh when stale

## Statusline output

```
Opus │ ~/dev/project │ main │ ◑ 57% │ max 5h ○ 0% │ recharge 5h ◔ 30% ~1h46m 7d ◔ 5% ~6d4h
```

Org labels are auto-derived: `claude_max` capability becomes "max", team orgs use the org name.

## Commands

```
python3 hooks/usage-fetch.py              # fetch and cache (called by statusline)
python3 hooks/usage-fetch.py --dump       # print cache (cookies redacted)
python3 hooks/usage-fetch.py --list       # show orgs + visibility
python3 hooks/usage-fetch.py --toggle <label>   # toggle org visibility
python3 hooks/usage-fetch.py --only <label>     # show only one org
python3 hooks/usage-fetch.py --show-all          # reset filter
```

## Files

| File | Purpose |
|------|---------|
| `hooks/usage-fetch.py` | Cookie extraction, API fetch, cache write, toggle CLI |
| `hooks/statusline.js` | Reads cache, renders pie gauges, spawns refresh when stale |
| `~/.cache/claude-usage/cache.json` | Cached usage data (60s TTL) + cookies (10min TTL) |
| `~/.cache/claude-usage/config.json` | Visibility filter (which orgs to show) |
| `~/.cache/claude-usage/.lock` | Prevents concurrent fetches |

## Requirements

macOS only (Keychain-based cookie decryption). Logged into claude.ai in Brave or Chrome. No pip dependencies (stdlib only).

## Using Chrome instead of Brave

The script defaults to Brave. To use Chrome, change these three values in `usage-fetch.py`:

| Constant | Brave (default) | Chrome |
|----------|-----------------|--------|
| `COOKIE_DB` | `~/Library/Application Support/BraveSoftware/Brave-Browser/Default/Cookies` | `~/Library/Application Support/Google/Chrome/Default/Cookies` |
| Keychain service (`-s`) | `Brave Safe Storage` | `Chrome Safe Storage` |
| Keychain account (`-a`) | `Brave` | `Chrome` |

The three lines to edit:

```python
# line 19 — cookie database path
COOKIE_DB = os.path.expanduser(
    "~/Library/Application Support/Google/Chrome/Default/Cookies"
)

# line 34 — keychain lookup (both -s and -a flags)
        ["security", "find-generic-password",
         "-s", "Chrome Safe Storage", "-a", "Chrome", "-w"],
```

Everything else (encryption scheme, API calls, cache format) is identical between Brave and Chrome.
