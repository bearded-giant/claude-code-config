#!/usr/bin/env python3
import json
import os
import re
import subprocess
import sys
import tempfile
from concurrent.futures import ThreadPoolExecutor

GITLAB_HOST = "gitlab.rechargeapps.net"

CHECKS = {
    "gcloud": ["gcloud", "auth", "print-access-token"],
    "adc": ["gcloud", "auth", "application-default", "print-access-token"],
    "glab": ["glab", "auth", "status", "--hostname", GITLAB_HOST],
    "gh": ["gh", "auth", "status"],
    "vault": ["vault", "token", "lookup", "-format=json"],
}

# vpn down or offline is not an expired login; render it as unknown, not red
NETWORK_ERROR_RE = re.compile(
    r"TLS handshake timeout|i/o timeout|connection (refused|reset)|no such host|dial tcp"
    r"|network is unreachable|could not resolve|Could not connect|Failed to connect"
    r"|timed out|context deadline exceeded|EOF$",
    re.IGNORECASE | re.MULTILINE,
)


def classify(returncode, output):
    if returncode == 0:
        return True
    if NETWORK_ERROR_RE.search(output):
        return None
    return False


def run_check(argv):
    try:
        r = subprocess.run(
            argv, check=False, capture_output=True, text=True, timeout=15
        )
    except FileNotFoundError:
        return "missing"
    except subprocess.TimeoutExpired:
        return {"ok": None}
    # stdout can hold an access token: classify it, never persist it
    return {"ok": classify(r.returncode, f"{r.stdout}\n{r.stderr}")}


def write_json(path, data):
    fd, tmp = tempfile.mkstemp(dir=os.path.dirname(path), suffix=".tmp")
    with os.fdopen(fd, "w") as f:
        json.dump(data, f)
    os.replace(tmp, path)


def main():
    with ThreadPoolExecutor(len(CHECKS)) as pool:
        results = dict(zip(CHECKS, pool.map(run_check, CHECKS.values())))
    write_json(sys.argv[1], {k: v for k, v in results.items() if v != "missing"})


if __name__ == "__main__":
    main()
