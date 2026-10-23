---
name: vercel-bootstrap
description: Bootstrap and maintain Vercel projects that deploy from GitLab CI (prod on release tag, previews on MRs/branches) with one idempotent CLI, `vbs.py`. Creates or fixes the Vercel project (framework, Node, Fluid, system envs, automation bypass), mints project-scoped deploy/preview tokens into GitLab CI variables and vault (re-mints dead ones), protects the release tag, fills a vault path (generated secrets, keys copied from other paths, the bypass secret), creates or connects Neon / Upstash Redis / Blob stores, keeps `.gitlab-ci.yml` VERCEL_PROJECT_ID in step, and plays the env-sync job. Also vault keys/put/patch/copy and one-off token mint / store add. Auto-fires when the user says "bootstrap a vercel project", "new vercel project", "set up vercel for <repo>", "add redis / postgres / neon / blob to <project>", "mint a vercel token", "copy creds from vault X to Y", "vault put/patch", "vercel console steps", or invokes /vercel-bootstrap.
---

One CLI replaces the console checklist. Never hand the user Vercel / GitLab / vault console steps that `vbs.py` covers; run it.

```
VBS=~/.claude/skills/vercel-bootstrap/vbs.py
```

Needs `vercel` (logged in, team scope rechargeapps), `glab`, `vault` (token with write on the target path). Python 3.11+. Never prints a secret value; values move CLI to CLI over stdin.

## Project bootstrap

1. Config: `projects/<vercel project>.toml` next to this file (copy `projects/example.toml`). Keys: `project`, `gitlab`, `framework`, `node`, `domains`, `env_sync_job`, `[tokens]`, `[vault]` (`path`, `generate`, `bypass`, `[vault.copy]`), `[[stores]]`.
2. Run from the repo root (so `.gitlab-ci.yml` VERCEL_PROJECT_ID gets checked):
   ```
   python3 $VBS check <project>    # read-only, exit 1 lists what is not ready
   python3 $VBS apply <project>    # creates / fixes, then plays or retries the env-sync job on main
   ```
3. Commit the `.gitlab-ci.yml` change apply makes, and the new `projects/<name>.toml` in claude-code-config.

What apply does, in order: project + settings + bypass; `.gitlab-ci.yml` id; protected tag `*.*.*` (create: maintainers); tokens (CI var probed live against the project: live CI value is copied to vault, else a live vault value goes to CI, else a new project-scoped token is minted via `POST /v3/user/tokens` into both); vault keys (generated keys written once, never rotated); stores (existing name connected, missing one created); env sync (only when something changed or the last run did not pass; prints only the sync's summary lines).

## One-off commands

```
python3 $VBS vault keys secret/ai-tools/prod/x
python3 $VBS vault patch secret/ai-tools/prod/x cron_secret=@gen token=@vault:secret/ai-tools/prod/y:service_token
echo -n "$V" | python3 $VBS vault patch secret/ai-tools/prod/x api_key=@stdin
python3 $VBS vault put secret/ai-tools/prod/new a=@gen          # refuses an existing path without --force
python3 $VBS vault copy secret/ai-tools/prod/y secret/ai-tools/prod/x service_token semantic_engine_token:engine_token
python3 $VBS token <project> --gitlab-var ai-tooling/<repo>:VERCEL_TOKEN --protected --vault secret/ai-tools/prod/<p>:vercel_token
python3 $VBS store upstash redis-<p> --project <p> [--plan paid] [-m primaryRegion=iad1]
python3 $VBS store neon neon-<p> --project <p> [--plan launch_v3] [--prefix X_]
python3 $VBS store blob blob-<p> --project <p> --access private
```

`vault copy` with no keys copies every key. `@gen` = 32-byte hex. Store creates default to pay-as-you-go (Neon `launch_v3`, Upstash `paid` in `iad1`); free tiers cap compute and commands too low for agent traffic. Blob has no plan.

Deleting a Blob store is blocked for agents (`dangerous_operation_requires_user`): the user runs `vercel blob delete-store <id> --scope rechargeapps` in a terminal. Vault metadata delete needs a policy the user's token lacks; `vault kv delete -versions=...` soft-deletes data.

## New repo CI

Copy the deploy pattern from a working repo, don't write it fresh:

| stack | reference repo | files |
|---|---|---|
| Next.js / TS | `ai-tooling/agent-hub` | `.gitlab-ci.yml` jobs `vercel-env-sync`, `.vercel`, `vercel-deploy`, `vercel-preview`, `vercel-preview-main`, `db-migrate`; `ci/vercel_env_sync.sh`, `ci/vercel_alias.js`, `ci/vercel_env_get.js` |
| Python / FastAPI | `ai-tooling/investigator-v2` | same job names; `ci/vercel_env_sync.sh` |

Change: project name, `rc-vault:` refs to the new vault path, the key lists in `vercel_env_sync.sh`, the preview alias. `VERCEL_ORG_ID` is the team id; `VERCEL_PROJECT_ID` is filled by apply. Project-scoped tokens can't run `vercel link` or `vercel alias set`, hence the ids and `vercel_alias.js`.

## Facts

- GitLab CI `load-secrets` reads `secret/ai-tools/prod/*` for ai-tooling projects with no extra vault policy (proven on investigator-v2 and agent-hub). A 403 in the env-sync trace from `vercel env POST` is a dead Vercel token, not vault.
- `vercel integration add` / `vercel blob create-store` connect to the linked project; vbs links through `VERCEL_ORG_ID` + `VERCEL_PROJECT_ID` in a temp dir, so it never writes `.vercel/` into the repo.
- `*.vercel.app` names are global across all Vercel accounts: `agent-hub.vercel.app` and `agent-hub-preview.vercel.app` belonged to someone else, so the project got a random production domain and the CI alias failed with `alias_in_use`. Use `rc-<project>` names in `domains` and for the preview alias, and claim the preview alias once with `vercel alias set <deployment> rc-<project>-preview.vercel.app --scope rechargeapps` before CI moves it.
- Neon/Upstash default env names have no prefix (`DATABASE_URL`, `KV_REST_API_URL`); set `prefix` when one store serves several apps with different names.
