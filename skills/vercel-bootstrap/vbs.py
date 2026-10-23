#!/usr/bin/env python3
import argparse
import json
import os
import re
import secrets
import subprocess
import sys
import tempfile
import time
import tomllib
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

PROJECTS_DIR = Path(__file__).resolve().parent / "projects"
TOKEN_SLOTS = (("deploy", "VERCEL_TOKEN", True), ("preview", "VERCEL_PREVIEW_TOKEN", False))
INTEGRATIONS = {"neon": "neon", "upstash": "upstash/upstash-kv"}
# free tiers cap compute and commands too low for agent traffic, so creates default to pay-as-you-go
DEFAULT_PLANS = {"neon": "launch_v3", "upstash": "paid"}
DEFAULT_METADATA = {"upstash": {"primaryRegion": "iad1"}}
# the env sync trace carries unmasked load-secrets output, so only these lines are ever printed
TRACE_LINES = re.compile(r"vercel env upsert|^missing:|not resolved by|vercel env POST|^failed |permission denied")

problems: list[str] = []


def step(name, state, detail=""):
    print(f"[{state}] {name}" + (f": {detail}" if detail else ""))
    if state in ("missing", "drift", "error"):
        problems.append(name)


def run(*cmd, stdin=None, check=True, env=None, cwd=None):
    # stdout is never echoed: several calls return secret values
    p = subprocess.run(
        cmd, input=stdin, capture_output=True, text=True, check=False, env={**os.environ, **(env or {})}, cwd=cwd
    )
    if check and p.returncode:
        sys.exit(f"{' '.join(cmd[:3])} exited {p.returncode}: {(p.stderr or p.stdout).strip()[-400:]}")
    return p


def vercel(team, path, method="GET", body=None) -> Any:
    args = ["vercel", "api", path, "--scope", team, "--raw", "-X", method]
    if body is not None:
        args += ["--input", "-"]
    return json.loads(run(*args, stdin=None if body is None else json.dumps(body)).stdout or "{}")


def glab(path, *args, check=True) -> Any:
    p = run("glab", "api", path, *args, check=check)
    return json.loads(p.stdout or "null") if p.returncode == 0 else None


def vault_read(path) -> dict | None:
    p = run("vault", "kv", "get", "-format=json", path, check=False)
    if p.returncode == 2:
        return None
    if p.returncode:
        sys.exit(f"vault kv get {path} exited {p.returncode}: {p.stderr.strip()[:300]}")
    return json.loads(p.stdout)["data"]["data"]


def vault_write(path, data, exists):
    run("vault", "kv", "patch" if exists else "put", path, "-", stdin=json.dumps(data))


def token_works(token, team_id, project_id):
    req = urllib.request.Request(
        f"https://api.vercel.com/v9/projects/{project_id}?teamId={team_id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    try:
        with urllib.request.urlopen(req, timeout=20):
            return True
    except urllib.error.HTTPError:
        return False


def mint_token(team, project_id, name):
    return vercel(team, "/v3/user/tokens", "POST", {"name": name, "projectId": project_id})["bearerToken"]


def gitlab_var_set(gitlab, var, value, protected):
    flags = ["-R", gitlab, "--masked"] + (["--protected"] if protected else [])
    p = run("glab", "variable", "set", var, *flags, stdin=value, check=False)
    if p.returncode and "already" in (p.stderr + p.stdout).lower():
        p = run("glab", "variable", "update", var, *flags, stdin=value, check=False)
    if p.returncode:
        sys.exit(f"glab variable {var} exited {p.returncode}: {p.stderr.strip()[-300:]}")


def bypass_secret(proj):
    return next(
        (k for k, v in (proj.get("protectionBypass") or {}).items() if v.get("scope") == "automation-bypass"), None
    )


def link_env(proj):
    return {"VERCEL_ORG_ID": proj["accountId"], "VERCEL_PROJECT_ID": proj["id"]}


def ensure_project(cfg, apply):
    team, name = cfg["team"], cfg["project"]
    if run("vercel", "api", f"/v9/projects/{name}", "--scope", team, "--raw", check=False).returncode:
        step("vercel project", "fixed" if apply else "missing", name)
        if not apply:
            return None
        run("vercel", "project", "add", name, "--scope", team)
    proj = vercel(team, f"/v9/projects/{name}")

    want = {"framework": cfg.get("framework"), "nodeVersion": cfg.get("node"), "autoExposeSystemEnvs": True}
    drift = {k: v for k, v in want.items() if v is not None and proj.get(k) != v}
    if cfg.get("fluid", True) and not (proj.get("resourceConfig") or {}).get("fluid"):
        drift["resourceConfig"] = {"fluid": True}
    if drift and apply:
        proj = vercel(team, f"/v9/projects/{proj['id']}", "PATCH", drift)
    step("vercel settings", "fixed" if drift and apply else "drift" if drift else "ok", ", ".join(drift) or proj["id"])

    has_bypass = bool(bypass_secret(proj))
    if not has_bypass and apply:
        vercel(team, f"/v1/projects/{proj['id']}/protection-bypass", "PATCH", {"generate": {"note": "ci and scripts"}})
        proj = vercel(team, f"/v9/projects/{proj['id']}")
    step("automation bypass", "ok" if has_bypass else "fixed" if apply else "missing")

    if cfg.get("domains"):
        have = {d["name"] for d in vercel(team, f"/v9/projects/{proj['id']}/domains").get("domains", [])}
        missing = [d for d in cfg["domains"] if d not in have]
        for name in missing if apply else []:
            vercel(team, f"/v10/projects/{proj['id']}/domains", "POST", {"name": name})
        step(
            "domains",
            "fixed" if missing and apply else "missing" if missing else "ok",
            ", ".join(missing or cfg["domains"]),
        )
    return proj


def ensure_ci_file(proj, apply):
    ci = Path(".gitlab-ci.yml")
    if not ci.exists() or "VERCEL_PROJECT_ID:" not in ci.read_text():
        return
    text = ci.read_text()
    new = re.sub(r'(VERCEL_PROJECT_ID: )"?[^"\n]*"?', rf'\g<1>"{proj["id"]}"', text, count=1)
    if new != text and apply:
        ci.write_text(new)
    step(".gitlab-ci.yml VERCEL_PROJECT_ID", "ok" if new == text else "fixed" if apply else "drift", proj["id"])


def ensure_release_tag(cfg, apply):
    pattern, gl = cfg.get("release_tag", "*.*.*"), urllib.parse.quote(cfg["gitlab"], safe="")
    if any(t["name"] == pattern for t in glab(f"projects/{gl}/protected_tags")):
        step(f"protected tag {pattern}", "ok")
        return
    if apply:
        glab(f"projects/{gl}/protected_tags", "-X", "POST", "-f", f"name={pattern}", "-f", "create_access_level=40")
    step(
        f"protected tag {pattern}",
        "fixed" if apply else "missing",
        "a protected VERCEL_TOKEN reaches only protected tags",
    )


def ensure_tokens(cfg, proj, have, apply):
    gl = urllib.parse.quote(cfg["gitlab"], safe="")
    keys = cfg.get("tokens", {"deploy": "vercel_token", "preview": "vercel_preview_token"})
    want = {}
    for slot, var, protected in TOKEN_SLOTS:
        key = keys.get(slot)
        if not key:
            continue
        ci = glab(f"projects/{gl}/variables/{var}", check=False)
        ci_value = ci["value"] if ci and token_works(ci["value"], proj["accountId"], proj["id"]) else None
        vault_value = have.get(key) if have.get(key) and token_works(have[key], proj["accountId"], proj["id"]) else None
        if ci and (ci["protected"] != protected or not ci["masked"]):
            step(f"gitlab {var} flags", "drift", f"want protected={protected} masked=true")
        if ci_value:
            if have.get(key) != ci_value:
                want[key] = ci_value
            step(
                f"token {slot}",
                "fixed" if key in want and apply else "drift" if key in want else "ok",
                f"{var}, vault {key}",
            )
            continue
        if not apply:
            step(
                f"token {slot}",
                "missing",
                f"{var} {'dead' if ci else 'unset'}; apply copies a live vault {key} or mints one",
            )
            continue
        value = vault_value or mint_token(cfg["team"], proj["id"], f"{cfg['project']}-{slot}-gitlab")
        gitlab_var_set(cfg["gitlab"], var, value, protected)
        if have.get(key) != value:
            want[key] = value
        step(f"token {slot}", "fixed", f"{var} from {'vault' if vault_value else 'a new project-scoped token'}")
    return want


def ensure_vault(cfg, proj, apply):
    vc = cfg.get("vault")
    if not vc:
        return False
    path = vc["path"]
    current = vault_read(path)
    have = current or {}
    want = ensure_tokens(cfg, proj, have, apply) if proj and cfg.get("gitlab") else {}

    for key in vc.get("generate", []):
        if key not in have:
            want[key] = secrets.token_hex(32)
    for src, keys in vc.get("copy", {}).items():
        source = None
        for spec in keys:
            src_key, _, dst_key = spec.partition(":")
            dst_key = dst_key or src_key
            if dst_key in have:
                continue
            source = source if source is not None else (vault_read(src) or {})
            if src_key in source:
                want[dst_key] = source[src_key]
            else:
                step(f"vault {dst_key}", "error", f"{src_key} not in {src}")
    if proj and vc.get("bypass") and vc["bypass"] not in have and bypass_secret(proj):
        want[vc["bypass"]] = bypass_secret(proj)

    if not want:
        step(f"vault {path}", "ok", f"{len(have)} keys")
        return False
    if apply:
        vault_write(path, want, current is not None)
    step(f"vault {path}", "fixed" if apply else "missing", ", ".join(sorted(want)))
    return apply


def ensure_store(cfg, proj, store, apply):
    kind, name = store["kind"], store["name"]
    envs = store.get("environments", ["production", "preview"])
    found = next((s for s in vercel(cfg["team"], "/v1/storage/stores").get("stores", []) if s["name"] == name), None)
    connected = found and any(p.get("name") == proj["name"] for p in found.get("projectsMetadata") or [])
    label = f"{kind} {name}"
    if connected:
        step(label, "ok")
        return False
    if not apply:
        step(label, "missing", "connect" if found else "create + connect")
        return False

    env_flags = [f for e in envs for f in ("-e", e)]
    prefix = ["--prefix", store["prefix"]] if store.get("prefix") else []
    with tempfile.TemporaryDirectory() as tmp:
        if found:
            run(
                "vercel",
                "integration-resource",
                "connect",
                name,
                proj["name"],
                *env_flags,
                *prefix,
                "--yes",
                "--scope",
                cfg["team"],
            )
        elif kind == "blob":
            access = store.get("access", "private")
            run(
                "vercel",
                "blob",
                "create-store",
                name,
                "-a",
                access,
                *env_flags,
                "--yes",
                "--scope",
                cfg["team"],
                env=link_env(proj),
                cwd=tmp,
            )
        else:
            metadata = {**DEFAULT_METADATA.get(kind, {}), **store.get("metadata", {})}
            meta = [f for k, v in metadata.items() for f in ("-m", f"{k}={v}")]
            plan = ["--plan", store.get("plan") or DEFAULT_PLANS[kind]]
            run(
                "vercel",
                "integration",
                "add",
                INTEGRATIONS[kind],
                "--name",
                name,
                *plan,
                *meta,
                *env_flags,
                *prefix,
                "--no-env-pull",
                "--scope",
                cfg["team"],
                env=link_env(proj),
                cwd=tmp,
            )
    step(label, "fixed", "connected" if found else "created + connected")
    return True


def env_sync(cfg, apply, force):
    job_name = cfg.get("env_sync_job")
    if not job_name:
        return
    gl = urllib.parse.quote(cfg["gitlab"], safe="")
    pipeline = glab(f"projects/{gl}/pipelines?ref=main&per_page=1")
    if not pipeline:
        step(job_name, "missing", "no pipeline on main")
        return
    jobs = glab(f"projects/{gl}/pipelines/{pipeline[0]['id']}/jobs?per_page=100")
    job = next((j for j in jobs if j["name"] == job_name), None)
    if not job:
        step(job_name, "missing", f"not in pipeline {pipeline[0]['id']}")
        return
    # every main pipeline starts with the sync manual, so judge by the latest run of it anywhere
    ran = glab(f"projects/{gl}/jobs?per_page=100&scope[]=success&scope[]=failed&scope[]=canceled")
    last = next((j for j in ran if j["name"] == job_name), None)
    if last and last["status"] == "success" and not force:
        step(job_name, "ok", f"job {last['id']}")
        return
    if not apply:
        step(job_name, "missing", f"job {job['id']} {job['status']}")
        return
    job = glab(f"projects/{gl}/jobs/{job['id']}/{'play' if job['status'] == 'manual' else 'retry'}", "-X", "POST")
    for _ in range(72):
        if job["status"] in ("success", "failed", "canceled"):
            break
        time.sleep(5)
        job = glab(f"projects/{gl}/jobs/{job['id']}")
    for line in run("glab", "api", f"projects/{gl}/jobs/{job['id']}/trace").stdout.splitlines():
        line = re.sub(r"^\S+Z \S+ ", "", line.strip())
        if TRACE_LINES.search(line):
            print(f"    {line[:200]}")
    step(
        job_name,
        "fixed" if job["status"] == "success" else "error",
        f"job {job['id']} {job['status']} {job['web_url']}",
    )


def load_config(ref):
    path = Path(ref) if Path(ref).suffix == ".toml" else PROJECTS_DIR / f"{ref}.toml"
    if not path.exists():
        sys.exit(f"no config at {path}; copy {PROJECTS_DIR / 'example.toml'}")
    cfg = tomllib.loads(path.read_text())
    cfg.setdefault("team", "rechargeapps")
    return cfg


def cmd_plan(args):
    cfg = load_config(args.config)
    proj = ensure_project(cfg, args.apply)
    if proj:
        ensure_ci_file(proj, args.apply)
    if cfg.get("gitlab"):
        ensure_release_tag(cfg, args.apply)
    changed = ensure_vault(cfg, proj, args.apply)
    for store in cfg.get("stores", []) if proj else []:
        changed = ensure_store(cfg, proj, store, args.apply) or changed
    if cfg.get("gitlab"):
        env_sync(cfg, args.apply, changed)
    if problems:
        sys.exit(f"{len(problems)} not ready: {', '.join(problems)}" + ("" if args.apply else "; rerun with apply"))


def parse_pairs(pairs):
    data, sources = {}, {}
    for pair in pairs:
        key, sep, value = pair.partition("=")
        if not sep:
            sys.exit(f"want KEY=VALUE, got {key}")
        if value == "@gen":
            data[key] = secrets.token_hex(32)
        elif value == "@stdin":
            data[key] = sys.stdin.read().rstrip("\n")
        elif value.startswith("@vault:"):
            src, _, src_key = value[len("@vault:") :].rpartition(":")
            if src not in sources:
                sources[src] = vault_read(src) or {}
            if src_key not in sources[src]:
                sys.exit(f"{src_key} not in {src}")
            data[key] = sources[src][src_key]
        else:
            data[key] = value
    return data


def cmd_vault(args):
    if args.action == "keys":
        print("\n".join(sorted(vault_read(args.path) or {})) or f"{args.path}: no value")
        return
    if args.action == "copy":
        source = vault_read(args.path) or {}
        specs = args.pairs or sorted(source)
        data = {}
        for spec in specs:
            src_key, _, dst_key = spec.partition(":")
            if src_key not in source:
                sys.exit(f"{src_key} not in {args.path}")
            data[dst_key or src_key] = source[src_key]
        dest = args.dest
    else:
        data, dest = parse_pairs(args.pairs), args.path
    if not data:
        sys.exit("nothing to write")
    exists = vault_read(dest) is not None
    if args.action == "put" and exists and not args.force:
        sys.exit(f"{dest} exists; put replaces every key, use patch or --force")
    vault_write(dest, data, exists and args.action != "put")
    print(f"{dest}: wrote {', '.join(sorted(data))}")


def cmd_token(args):
    proj = vercel(args.team, f"/v9/projects/{args.project}")
    value = mint_token(args.team, proj["id"], args.name or f"{args.project}-{secrets.token_hex(3)}")
    if args.gitlab_var:
        gitlab, _, var = args.gitlab_var.rpartition(":")
        gitlab_var_set(gitlab, var, value, args.protected)
    if args.vault:
        path, _, key = args.vault.rpartition(":")
        vault_write(path, {key: value}, vault_read(path) is not None)
    if not (args.gitlab_var or args.vault):
        sys.exit("give --gitlab-var and/or --vault; the token is shown only once and this tool never prints it")
    print(f"minted project-scoped token for {args.project} -> {', '.join(filter(None, [args.gitlab_var, args.vault]))}")


def cmd_store(args):
    cfg = {"team": args.team, "project": args.project}
    proj = vercel(args.team, f"/v9/projects/{args.project}")
    store = {"kind": args.kind, "name": args.name, "environments": args.env or ["production", "preview"]}
    store.update({k: v for k, v in (("prefix", args.prefix), ("plan", args.plan), ("access", args.access)) if v})
    store["metadata"] = dict(m.split("=", 1) for m in args.meta or [])
    ensure_store(cfg, proj, store, True)


def main():
    ap = argparse.ArgumentParser(prog="vbs", description="bootstrap Vercel projects deployed from GitLab CI")
    sub = ap.add_subparsers(dest="cmd", required=True)

    for name in ("check", "apply"):
        p = sub.add_parser(name, help=f"{name} everything a project config declares")
        p.add_argument("config", help="project name under projects/, or a path to a .toml")
        p.set_defaults(func=cmd_plan, apply=name == "apply")

    v = sub.add_parser("vault", help="keys | put | patch | copy")
    v.add_argument("action", choices=("keys", "put", "patch", "copy"))
    v.add_argument("path")
    v.add_argument("dest", nargs="?", help="copy: destination path")
    v.add_argument(
        "pairs",
        nargs="*",
        help="put/patch: KEY=VALUE, VALUE may be @gen, @stdin, @vault:PATH:KEY; copy: KEY or SRC:DST",
    )
    v.add_argument("--force", action="store_true", help="put over an existing path")
    v.set_defaults(func=cmd_vault)

    t = sub.add_parser("token", help="mint a project-scoped Vercel token into GitLab and/or vault")
    t.add_argument("project")
    t.add_argument("--team", default="rechargeapps")
    t.add_argument("--name")
    t.add_argument("--gitlab-var", help="GROUP/REPO:VAR")
    t.add_argument("--protected", action="store_true")
    t.add_argument("--vault", help="PATH:KEY")
    t.set_defaults(func=cmd_token)

    s = sub.add_parser("store", help="create or connect a neon | upstash | blob store")
    s.add_argument("kind", choices=("neon", "upstash", "blob"))
    s.add_argument("name")
    s.add_argument("--project", required=True)
    s.add_argument("--team", default="rechargeapps")
    s.add_argument("-e", "--env", action="append", choices=("production", "preview", "development"))
    s.add_argument("--prefix")
    s.add_argument("--plan")
    s.add_argument("--access", choices=("private", "public"))
    s.add_argument("-m", "--meta", action="append", help="KEY=VALUE integration metadata")
    s.set_defaults(func=cmd_store)

    args = ap.parse_args()
    if args.cmd == "vault" and args.action == "copy" and not args.dest:
        ap.error("vault copy needs SRC DEST")
    if args.cmd == "vault" and args.action != "copy" and args.dest:
        args.pairs.insert(0, args.dest)
    args.func(args)


if __name__ == "__main__":
    main()
