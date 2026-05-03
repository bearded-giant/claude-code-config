#!/usr/bin/env python3
"""fetch claude.ai usage data for all chat-capable orgs, write to local cache."""

import hashlib
import json
import os
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import time
import urllib.request

CACHE_DIR = os.path.expanduser("~/.cache/claude-usage")
CACHE_FILE = os.path.join(CACHE_DIR, "cache.json")
LOCK_FILE = os.path.join(CACHE_DIR, ".lock")
COOKIE_DB = os.path.expanduser(
    "~/Library/Application Support/BraveSoftware/Brave-Browser/Default/Cookies"
)

USAGE_TTL = 60
COOKIE_TTL = 600
UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Brave/131.0.0.0 Chrome/131.0.0.0 Safari/537.36"
)


def get_keychain_password():
    r = subprocess.run(
        ["security", "find-generic-password",
         "-s", "Brave Safe Storage", "-a", "Brave", "-w"],
        capture_output=True, text=True,
    )
    if r.returncode != 0:
        raise RuntimeError("keychain access failed")
    return r.stdout.strip()


def derive_key(password):
    return hashlib.pbkdf2_hmac("sha1", password.encode(), b"saltysalt", 1003, dklen=16)


def decrypt_value(blob, key):
    if not blob or len(blob) <= 3 or blob[:3] != b"v10":
        return ""
    iv = b"\x20" * 16
    r = subprocess.run(
        ["openssl", "enc", "-aes-128-cbc", "-d", "-nopad",
         "-K", key.hex(), "-iv", iv.hex()],
        input=blob[3:], capture_output=True,
    )
    if r.returncode != 0:
        return ""
    raw = r.stdout
    pad_len = raw[-1]
    if 0 < pad_len <= 16:
        raw = raw[:-pad_len]
    # brave/chrome prepends 32-byte hmac to the plaintext
    if len(raw) > 32:
        return raw[32:].decode("utf-8", errors="replace")
    return raw.decode("utf-8", errors="replace")


def read_cookies(key):
    tmp = tempfile.mktemp(suffix=".db")
    shutil.copy2(COOKIE_DB, tmp)
    try:
        conn = sqlite3.connect(tmp)
        c = conn.cursor()
        c.execute(
            "SELECT name, value, encrypted_value FROM cookies "
            "WHERE host_key LIKE '%claude.ai'"
        )
        cookies = {}
        for name, plaintext, encrypted in c.fetchall():
            if plaintext:
                cookies[name] = plaintext
            elif encrypted and len(encrypted) > 3:
                val = decrypt_value(encrypted, key)
                if val:
                    cookies[name] = val
        conn.close()
        return cookies
    finally:
        os.unlink(tmp)


def api_get(cookies, path):
    url = f"https://claude.ai{path}"
    cookie_str = "; ".join(f"{k}={v}" for k, v in cookies.items())
    req = urllib.request.Request(url)
    req.add_header("Cookie", cookie_str)
    req.add_header("Accept", "application/json")
    req.add_header("User-Agent", UA)
    with urllib.request.urlopen(req, timeout=10) as resp:
        return json.loads(resp.read())


def org_label(org):
    caps = org.get("capabilities", [])
    if "claude_max" in caps:
        return "max"
    name = org.get("name", "")
    # strip common suffixes like "'s Organization"
    if "'s Organization" in name:
        name = name.split("@")[0] if "@" in name else name.split("'s")[0]
    return name.lower()[:12]


def parse_usage(raw):
    result = {}
    if not isinstance(raw, dict):
        return result
    for key in ("five_hour", "seven_day"):
        window = raw.get(key)
        if not window or not isinstance(window, dict):
            continue
        util = window.get("utilization")
        if util is None:
            continue
        result[key] = {
            "used_pct": min(round(util), 100),
            "resets_at": window.get("resets_at"),
        }
    # spend cap (Enterprise): float utilization, monthly_limit in currency units
    eu = raw.get("extra_usage")
    if isinstance(eu, dict) and eu.get("is_enabled") and eu.get("monthly_limit"):
        util = eu.get("utilization", 0.0)
        result["spend_cap"] = {
            "used_pct": min(round(util * 10) / 10, 100.0),
            "used": eu.get("used_credits", 0.0),
            "limit": eu.get("monthly_limit"),
            "currency": eu.get("currency", "USD"),
            "resets_at": eu.get("resets_at"),
        }
    return result


def acquire_lock():
    os.makedirs(CACHE_DIR, exist_ok=True)
    try:
        if os.path.exists(LOCK_FILE):
            if time.time() - os.path.getmtime(LOCK_FILE) < 30:
                return False
            os.unlink(LOCK_FILE)
        fd = os.open(LOCK_FILE, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        os.write(fd, str(os.getpid()).encode())
        os.close(fd)
        return True
    except (FileExistsError, OSError):
        return False


def release_lock():
    try:
        os.unlink(LOCK_FILE)
    except OSError:
        pass


def main():
    if not acquire_lock():
        sys.exit(0)
    try:
        cached = None
        if os.path.exists(CACHE_FILE):
            try:
                with open(CACHE_FILE) as f:
                    cached = json.load(f)
            except (json.JSONDecodeError, IOError):
                pass

        now = time.time()
        cookies = None

        if cached and cached.get("cookies_expire_at", 0) > now:
            cookies = cached.get("cookies")

        if not cookies or "sessionKey" not in cookies:
            password = get_keychain_password()
            key = derive_key(password)
            cookies = read_cookies(key)

        if not cookies.get("sessionKey"):
            sys.exit(1)

        # fetch org list and filter to chat-capable orgs
        all_orgs = api_get(cookies, "/api/organizations")
        chat_orgs = [o for o in all_orgs if "chat" in o.get("capabilities", [])]

        orgs = []
        for org in chat_orgs:
            org_id = org.get("uuid", "")
            if not org_id:
                continue
            try:
                raw = api_get(cookies, f"/api/organizations/{org_id}/usage")
            except Exception:
                continue
            usage = parse_usage(raw)
            orgs.append({
                "id": org_id,
                "label": org_label(org),
                **usage,
            })

        cache = {
            "orgs": orgs,
            "fetched_at": now,
            "expires_at": now + USAGE_TTL,
            "cookies": cookies,
            "cookies_expire_at": now + COOKIE_TTL,
        }

        os.makedirs(CACHE_DIR, exist_ok=True)
        tmp = CACHE_FILE + ".tmp"
        with open(tmp, "w") as f:
            json.dump(cache, f, indent=2)
        os.rename(tmp, CACHE_FILE)
    except Exception:
        pass
    finally:
        release_lock()


def cmd_list():
    try:
        with open(CACHE_FILE) as f:
            cache = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        print("no cache yet -- run without flags first")
        sys.exit(1)

    for org in cache.get("orgs", []):
        label = org.get("label", "?")
        sc = org.get("spend_cap")
        if sc:
            used = sc.get("used", 0)
            limit = sc.get("limit", 0)
            pct = sc.get("used_pct", 0)
            cur = sc.get("currency", "USD")
            print(f"  {label:<14}  {pct}%  {used:.0f}/{limit} {cur}")
        else:
            print(f"  {label:<14}  no spend cap")


if __name__ == "__main__":
    args = sys.argv[1:]
    if not args:
        main()
    elif args[0] == "--dump":
        try:
            with open(CACHE_FILE) as f:
                data = json.load(f)
                data.pop("cookies", None)
                print(json.dumps(data, indent=2))
        except Exception as e:
            print(f"error: {e}", file=sys.stderr)
            sys.exit(1)
    elif args[0] == "--list":
        cmd_list()
    else:
        print("usage: usage-fetch.py [--dump|--list]")
        sys.exit(1)
