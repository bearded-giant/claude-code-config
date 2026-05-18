---
description: Run TypeScript lint, typecheck, and tests on modified files (pnpm + turbo monorepos). Handles `.nvmrc` Node switching. Auto-fires before reporting a TS/React-touching task done — i.e., after editing any `.ts`/`.tsx` file, before final summary to user. Skip only if user explicitly disabled or the change is doc-only.
allowed-tools: Bash, Grep, Glob, Read
---

Run quality checks on TypeScript/React code. Designed for pnpm + turbo monorepos.

## Prerequisites

**Node version**: Check `.nvmrc` or `.node-version` and switch if needed:
```bash
source ~/.nvm/nvm.sh && nvm use
```

This is critical - Node 24+ causes tsc to crash with "Map maximum size exceeded".

## Steps

1. **Switch Node version** - run `source ~/.nvm/nvm.sh && nvm use` in the project root
2. **Identify changes** - use `git diff --name-only HEAD` to find modified/added `.ts`/`.tsx` files
3. **Determine package** - identify which package(s) the changes are in (e.g., `packages/merchant-portal/core`)
4. **Run checks** in order:
   - `pnpm lint --filter=<package>` - eslint
   - `pnpm typecheck --filter=<package>` - tsc
   - `pnpm test --filter=<package> -- <test-pattern>` - vitest for modified/added test files only

## Notes

- If no specific package is identifiable, run from repo root
- For merchant-portal/core, cd into the package dir and run `pnpm lint`, `pnpm typecheck`, `pnpm test`
- Only run tests that were created or modified (match test file names from git diff)
- If no test files changed, skip test step
- Report failures clearly with file:line references
