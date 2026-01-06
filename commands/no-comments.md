---
description: Remove superfluous comments from specified files
allowed-tools: Read, Edit, Glob
argument-hint: <file-or-pattern>
---

Review the specified files and remove superfluous comments.

Target: $ARGUMENTS

Rules:
- Keep only comments explaining crucial or complex logic
- Remove obvious/self-documenting comments
- Make remaining comments lowercase
- Skip test files entirely
- Do not add new comments

If no target specified, ask the user which files to process.
