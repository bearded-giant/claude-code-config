---
description: Run Python formatting and tests for modified files
allowed-tools: Bash, Grep, Glob, Read
---

Run quality checks on Python code.

## Steps

1. **Identify changes** - use `git diff --name-only HEAD` to find modified/added `.py` files
2. **Run formatters** on changed files:
   - `isort <files>` - import sorting
   - `black <files>` - code formatting
3. **Run tests** - only for modified/added test files:
   - Detect test runner (pytest is typical)
   - Run only changed test files: `pytest <test-files>`

## Project-specific notes

- Check for `pyproject.toml` or `setup.cfg` for project-specific isort/black configs
- Some projects use docker: `docker compose run --rm test pytest <files>`
- If CLAUDE.md exists in project root, check for test commands

## Output

- Report any formatting changes made
- Report test results with file:line references for failures
- If no test files changed, skip test step
