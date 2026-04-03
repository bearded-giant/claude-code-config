---
description: Grab recent server logs from prestage VM
allowed-tools: Bash, Read
---

Fetch the last N lines of server.log from the prestage environment. This is a non-blocking snapshot, not a live tail.

## Usage

$ARGUMENTS is the number of lines to grab. Default: 200.

## Steps

1. Run: `scripts/pre-envs/grab-logs.sh prestage $ARGUMENTS`
   - If $ARGUMENTS is empty, run without the second arg (defaults to 200)
2. Display the output directly -- no summarizing or truncating unless the user asks
