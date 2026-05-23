---
name: secrets-sync
description: Diff + reconcile service-token / JWT secrets across stacks using a `secrets-matrix.md` artifact. Reads vault via `vault kv get`, monolith ejson via decrypt, then reports match/mismatch/missing per env and patches vault on confirm. Auto-fires when user says "sync secrets", "check token alignment", "vault sync", "diff secrets", "rotate token", or invokes /secrets-sync. Pairs with the secrets-matrix.md authoring artifact.
---

Token / key alignment across multi-repo stacks. Sources of truth scattered across monolith ejson, peer-repo configs, and Vault — this skill reconciles them against a single declarative artifact.

## When to use

- User maintains a `secrets-matrix.md` (or equivalent declarative artifact listing match-pairs).
- User asks "are stage tokens in sync?" / "did chat-orch get the new token?" / "vault sync".
- Pre-deploy: confirm an env has every secret the chart references.
- Post-rotation: confirm both ends of every match-pair flipped.

## Not for

- One-off `vault kv get` lookups (just run `vault kv get` directly).
- Initial secret generation (separate concern — see /vault-bootstrap if exists, otherwise ad-hoc).
- Secrets without a declared matrix (refuse; ask user to draft one first).

## Inputs

- **matrix path**: file describing match-pairs. Search order:
  1. `$ARGUMENTS` if a path was passed
  2. active feature: `.giantmem/features/*/secrets-matrix.md` (newest mtime if multiple)
  3. workspace root: `.giantmem/secrets-matrix.md`
  4. ask user
- **cluster filter**: optional — `--cluster stage`, `--cluster prod`, `--cluster all` (default). Matrix declares envs grouped into clusters (e.g. `C1 = stage-cluster`, `C2 = prod-cluster`). The skill iterates cluster-by-cluster, NOT env-by-env, because the source of truth is per-cluster.
- **mode**: `check` (default, read-only) or `patch` (apply fixes, prompts before each write).

## Cluster-mapping invariant (read first)

Most Recharge secrets resolve to **N values per secret, N = number of deploy clusters**, NOT one per env. The skill MUST read the matrix's `## Cluster boundaries` section first and treat every env inside a cluster as sharing one source value.

- A single vault path holds the value for an entire cluster (e.g. `ai-tools/stage/chat-api` is read by dev, ephemeral, prestage, and stage).
- N ejson files inside the same cluster carry the **same plaintext** — rotating means patching all of them in lockstep, not generating different values.
- preprod / UAT envs commonly map to the **prod** cluster despite the name; always trust the matrix's cluster table, never infer from env name.

If the matrix has no `## Cluster boundaries` section, refuse and ask the user to add one — without it the skill cannot tell whether 6 ejson files should hold 6 distinct values or 1 shared value.

## Vault path discovery

**Never assume a vault subpath.** Top-level vault mount is always `secret/`, but the subpath varies per team/app: `secret/ai-tools/{env}/...`, `secret/{env}/<app>/...`, `secret/<team>/{env}/...`, etc. The matrix declares explicit full paths per holder per cluster. If a holder's path is unset / `TBD` / not declared:

1. Stop processing that holder.
2. Prompt the user: `Vault path for <holder> in cluster <C1|C2>?`
3. Validate the path with `vault kv get -format=json <path>` before continuing (just to confirm the mount exists — empty/missing key is OK).
4. Offer to patch the matrix with the confirmed path so future runs skip the prompt.

Never silently default to a guessed subpath (e.g. `secret/ai-tools/<cluster>/<service>`). The naming convention varies per team — `ai-tools` is one of many sub-namespaces under the `secret/` mount.

## Steps

1. **Load matrix.** Parse `## Cluster boundaries` AND `## Match pairs`. Each pair row → `(pair_id, secret_id, holders[], cluster_scoped)`. Each cluster row → `(cluster_id, vault_path_per_holder, envs_in_cluster)`. Reject if either section missing.

2. **Resolve holders per cluster.** For each `(pair_id, cluster_id)`:
   - For ejson holders (`MN.ejson.*`): the matrix's cluster table lists which ejson files map to the cluster. Decrypt each with `ejson decrypt <path>`; index via jq using the holder's dotted path. All files in the cluster should yield the **same** value — flag intra-cluster drift as a `CLUSTER-DRIFT` status (one cluster, multiple distinct ejson values = bug).
   - For vault holders (`ref+vault://...#/KEY` or `CA._FOO` etc.): resolve to a `vault kv get -format=json <cluster-vault-path>` call; pick the field after `#/`.
   - For literal env-file holders (`.env`): note as "local-only", skip in deployed sync.
   - For peer-repo holders with `TBD` markers: report unresolved, skip.

3. **Diff per pair × cluster.** Output table:

   ```
   pair  cluster  MN-side          CA-side    CO-side    status
   M1    C1       ✓ (12c…) ×6      ✓ (12c…)   —          OK
   M1    C2       ✓ (98e…) ×3 ✗1   ✗ MISSING  —          CLUSTER-DRIFT + NEEDS-PATCH
   M2    C1       —                ✓ (44b…)   ✗ MISSING  NEEDS-PATCH
   M3    C2       ✓                ✓ (kid:…)  ? unknown  TBD
   ```

   - `×N` shows how many ejson files in the cluster carry that value; `✗N` shows how many diverge.
   - Show first 4 chars + ellipsis only — never the full secret in chat output.
   - Status: `OK` / `MISMATCH` (cross-holder) / `CLUSTER-DRIFT` (intra-holder, multiple ejson files disagree) / `NEEDS-PATCH` / `TBD` / `ERROR`.

4. **In `check` mode**: stop here. Print summary `<n> OK / <m> mismatch / <k> needs-patch / <t> tbd`.

5. **In `patch` mode**: for each `NEEDS-PATCH` row, prompt:
   > Patch `<vault-path>#/<key>` from `<source holder>` in env `<env>`? [y/N/skip]
   - `y` → `vault kv patch <mount>/<path> <key>=@<tmpfile>` (write value via tmpfile so the secret never appears in shell history). `chmod 600` the tmpfile, delete on success.
   - For `MISMATCH`, additionally show which value would be overwritten and which would survive (treat the matrix's first-listed holder per pair as the source of truth unless user overrides with `--source-of-truth <holder>`).
   - Never `vault kv put` (destructive). Always `patch` to preserve sibling fields.
   - Never write to ejson or peer repos from this skill — only output a follow-up checklist with the exact commits/files the user needs to update by hand.

6. **Output a follow-up checklist** for anything outside vault:
   - Monolith ejson edits needed (file + key + new value placeholder)
   - chat-orchestrator config edits needed
   - JWT rotation steps if `S3`/`S4` drift detected

## Conventions

- **Source of truth**: first holder listed for a pair in the matrix table.
- **Never echo full secrets.** Truncate to first 4 chars + `…` in user-visible output. Full values only flow via tmpfiles into `vault kv patch`.
- **`vault kv patch` not `put`.** Patch preserves other fields under the same path; put destroys them.
- **Don't `cat` secrets to log files.** No `set -x` around vault calls.
- **`ejson decrypt` requires private key** at `/opt/ejson/keys/<pubkey>` (monolith convention). If decrypt fails: report error and skip that row, don't try to read the encrypted ciphertext.

## Refusals

- Refuse to patch any path containing `prod` or `production` without an explicit `--confirm-prod` flag in the same invocation.
- Refuse to write a value whose source holder reads back as empty / null / placeholder text (`TBD`, `<set-me>`, etc.).
- Refuse to run if matrix has uncommitted edits older than 10 minutes — likely mid-edit; ask user to commit or stash first.
- Refuse to load a matrix that lacks a `## Cluster boundaries` section. The cluster mapping is the source of truth for which ejson files share a value; running env-by-env without it generates N distinct values for what should be N-mapped-to-1.

## Output template

```
matrix: .giantmem/features/bootstrap/secrets-matrix.md
clusters: C1 (stage), C2 (prod)
mode: check

pair  cluster  holders                                   status
M1    C1       MN.ejson ×6 ↔ CA.vault                    OK (all 7a3f…)
M1    C2       MN.ejson ×3 ✗1 ↔ CA.vault                 CLUSTER-DRIFT (preprod ejson holds 11bb…; the other 3 hold 98e1…)
M2    C1       CO.vault ↔ CA.vault                       NEEDS-PATCH (CA missing)
M2    C2       CO.vault ↔ CA.vault                       MISMATCH (CO=44b1… CA=02ee…)
M3    C1       MN.cfg ↔ CA.vault ↔ CO.cfg                TBD (CO holder unresolved)

summary: 1 OK / 1 MISMATCH / 1 NEEDS-PATCH / 1 CLUSTER-DRIFT / 1 TBD

follow-up checklist:
- M1 C2: human decision — which value wins? then patch the 1 drifting ejson file AND vault if needed
- M2 C1: run `/secrets-sync --cluster stage patch` to push CA vault value
- M2 C2: matrix says CO (chat-orchestrator) is source of truth; align CA vault
- M3 C1: chat-orchestrator JWT verify config holder undefined in matrix — extend the matrix `TBD` section first
```

## Quickstart

```bash
# default: check active feature's matrix across both clusters
/secrets-sync

# check a single cluster
/secrets-sync --cluster stage

# patch missing vault entries (prompts each)
/secrets-sync --cluster stage patch

# patch prod-cluster (requires explicit flag — covers preprod + prod)
/secrets-sync --cluster prod patch --confirm-prod
```

## Implementation notes

- Vault auth: assumes `vault token lookup` succeeds already. If not, instruct the user to run `vault login -method=oidc` (Recharge convention) — do not handle credentials inline.
- For monolith ejson: `cd $MONOLITH_REPO && ejson decrypt config/<env>.ejson | jq -r '<dotted.path>'`. Auto-detect monolith repo via `~/dev/python/cc-wt/*/customcheckout/__init__.py` glob or `$MONOLITH_REPO` env var.
- For peer repos (e.g. chat-orchestrator): require a `peer_repo:` field per holder in the matrix if its config needs reading. v1: report as `TBD` and let user fill matrix.
- Cache vault reads for the session — same path read N times shouldn't re-hit the server.
