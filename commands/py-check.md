---
description: Run Python quality checks (black/ruff/pytest, optional isort/pylint) on modified files. Auto-fires before reporting a Python-touching task done — i.e., after editing any `.py` file in this repo, before final summary to user. Skip only if user explicitly disabled or the change is doc-only.
allowed-tools: Bash, Grep, Glob, Read, AskUserQuestion
---

Run quality checks on Python code.

## Steps

1. **Identify changes** - use `git diff --name-only HEAD` to find modified/added `.py` files

2. **Ask about optional tools** - use AskUserQuestion to ask:
   - "Run isort?" (yes/no) - not all projects use isort
   - "Run pylint?" (yes/no) - not all projects use pylint

3. **Run formatters** on changed files:
   - `black <files>` - code formatting (always)
   - `isort <files>` - import sorting (if user said yes)

4. **Run pylint** (if user said yes) - only on changed files:
   - `pylint <changed-files>` - lint only the modified `.py` files
   - Report any warnings/errors with file:line references

5. **Run tests** - only for modified/added test files:
   - Detect test runner (pytest is typical)
   - Run only changed test files: `pytest <test-files>`

## Project-specific notes

- Check for `pyproject.toml` or `setup.cfg` for project-specific configs
- Some projects use docker: `docker compose run --rm test pytest <files>`
- If CLAUDE.md exists in project root, check for test commands

## Output

- Report any formatting changes made
- Report pylint issues with file:line references (if enabled)
- Report test results with file:line references for failures
- If no test files changed, skip test step
