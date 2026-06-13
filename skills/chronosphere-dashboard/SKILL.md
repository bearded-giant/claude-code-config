---
name: chronosphere-dashboard
description: Create or refresh a Chronosphere dashboard for any service deployed behind Envoy Gateway (any k8s namespace). Clones the chat-orchestrator dashboard template (envoy req volume, p50/p95 latency, response-code breakdown, pod count) and optionally retains OTel app panels. Auto-fires when user says "create a chronosphere dashboard for X", "clone the orchestrator dashboard onto Y", "give me an envoy dashboard for service Z", "new chronosphere dashboard", or invokes /chronosphere-dashboard. Skip for services NOT routed via Envoy Gateway (no envoy_cluster_upstream_rq metrics).
---

# chronosphere-dashboard

Single chain. Register service in `apps.yaml`, generate YAML from template, push to Chronosphere via `chronoctl`. No re-confirmation between steps once user names the service and the params (or accepts defaults).

Toolkit lives at `~/dev/giant-tooling/chronosphere/`:

| File | Purpose |
|---|---|
| `template.yaml` | base snapshot (= chat-orchestrator dashboard) |
| `apps.yaml` | per-app registry |
| `gen_dashboard.py` | clone + substitute generator |
| `dump_panels_md.py` | dump panels (name + PromQL) from a dashboard YAML to markdown — `python3 dump_panels_md.py <slug>.yaml ~/Desktop/dashboard-<slug>.md` |
| `custom_panels/<slug>.py` | per-app panel injector (run after gen_dashboard) |

## Preconditions

- `chronoctl` on PATH and authenticated (`chronoctl dashboards list` succeeds).
- Service routes traffic via Envoy Gateway. Verify with `envoy_cluster_upstream_rq{envoy_cluster_name=~"httproute/.*<slug>.*"}` returning rows.
- `uv` available (used to invoke generator with PyYAML).
- Namespace is NOT hardcoded — the full `httproute/<ns>/<route>/rule/.+` lives entirely inside `httproute-regex`. Apps in `ai-tooling`, `prod`, or other namespaces all work as long as the regex is correct.

## Chain

### Step 1 — Gather params

Need:

| Param | Source |
|---|---|
| slug | kebab-case service name (e.g. `support-agent`) |
| name | display name (e.g. `Support Agent`) |
| httproute-regex | envoy cluster name regex |
| workload-regex | k8s workload name regex |
| otel-prefix | `null` if no OTel/prom metrics, else metric prefix (e.g. `support_agent`) |
| collection-slug | `recharge-chat` (default) or other Chronosphere collection |

DO NOT guess httproute-regex. Always run Step 1a discovery first — namespace and route shape vary unpredictably per service. Known patterns:

| App | Namespace | Pattern |
|---|---|---|
| chat-orchestrator | ai-tooling | multi-route (`-recharge`, `-harness-recharge`, ...) → `httproute/ai-tooling/chat-orchestrator-.+/.+` |
| chat-api | ai-tooling | single route → `httproute/ai-tooling/recharge-chat-api/rule/.+` |
| support-agent | ai-tooling | multi-route → `httproute/ai-tooling/support-agent-.+/.+` |
| analytics-agent | prod | single route → `httproute/prod/analytics-agent/rule/.+` |

Defaults:
- workload-regex: derive from `k8s_workload_name` discovery (Step 1a). Use `<slug>.*` (NOT `<slug>-.*`) — `-.*` requires a trailing dash and misses exact-match workloads. Real bug observed: `recharge-chat-api-.*` failed to match workload `recharge-chat-api` (no suffix).
- otel-prefix: confirm via Step 1a query. Default `null` if no metrics.
- collection-slug: ask user. Default `recharge-chat`.

#### Step 1a — Discover via Chronosphere MCP (REQUIRED)

Use the `mcp__plugin_kai_watchtower__chronosphere_query` tool. Three queries:

1. **Envoy cluster name:**
   ```
   group by (envoy_cluster_name) (envoy_cluster_upstream_rq{env="prod",envoy_cluster_name=~"httproute/.*<slug>.*"})
   ```
   Use returned cluster names to pin regex. Empty result → app not in envoy (skip skill).

2. **k8s workload name:**
   ```
   group by (k8s_workload_name) (k8s_pod_phase{env="prod",k8s_workload_name=~"<slug>.*"})
   ```

3. **OTel/prom metrics:**
   ```
   group by (__name__) ({__name__=~"<slug_underscore>_.*",env="prod"})
   ```
   Empty → `otel-prefix: null`. Non-empty + matches expected schema → set prefix.

### Step 2 — Add to registry

Append to `~/dev/giant-tooling/chronosphere/apps.yaml`:

```yaml
  <slug>:
    name: <Display Name>
    # optional: deployed dashboard slug if it differs from the registry key
    # (chat-orchestrator registry entry → dashboard slug is `orchestrator`)
    # slug: <deployed-slug>
    httproute-regex: <regex from step 1>
    workload-regex: <slug>.*       # use `.*` (matches empty suffix), NOT `-.*`
    otel-prefix: <null or prefix>
    collection-slug: <collection>
```

If slug already exists, update in place. Do not duplicate.

### Step 3 — Generate YAML

```bash
cd ~/dev/giant-tooling/chronosphere
uv run --with pyyaml python3 gen_dashboard.py --from-registry <slug>
```

Output lands in CWD as `<slug>.yaml`. Generator prints which OTel panels were stripped.

### Step 3b — Custom OTel panels (optional)

If the app emits OTel/prom metrics that DON'T match the template's orchestrator schema (`*_api_request_duration_ms_bucket`, `*_audit_outbound_written_total`, `*_slack_dispatch_duration_ms_bucket`) → DO NOT set `otel-prefix` (panels would render empty). Instead, build a custom-panel injector script at `~/dev/giant-tooling/chronosphere/custom_panels/<slug>.py` modeled on `support-agent.py`. The script reads the generated YAML, mutates `dashboard_json` to add app-specific panels, writes back.

Workflow:
1. `python3 custom_panels/<slug>.py` after `gen_dashboard.py`
2. Then `chronoctl dashboards update -f <slug>.yaml`

Pattern preserved in `custom_panels/support-agent.py` — copy + edit metric names/labels.

### Step 3c — Post-merge regen for HTTP request metrics

If the target service just merged a `feat/http-request-metrics` MR (or equivalent — adds `<service>.api.request.{duration_ms,count}` via statsd / OTel / DataDog), regen its dashboard once the new metric appears in Chronosphere. Adds 2 panels to `custom_panels/<slug>.py`:

1. **req/min by status_class** — `sum by (status_class) (rate(<metric_prefix>_api_request_count{env="$env"}[$__rate_interval])) * 60`
2. **request latency p95 by route** — `histogram_quantile(0.95, sum by (le, route) (rate(<metric_prefix>_api_request_duration_ms_milliseconds_bucket{env="$env"}[$__rate_interval])))`

Metric-name shape depends on facade. **Critical naming gotcha**: OTel→Prom translator adds `_milliseconds` suffix to histograms with `ms` unit hint AND does NOT add `_total` to counters. DataDog/statsd path does the opposite. Get this wrong → panel shows "No data" even though metric exists. Always verify by querying the actual metric name first.

| Facade | Counter name | Histogram bucket name |
|---|---|---|
| OTel statsd-adapter (chat-orchestrator, support-agent — both use `orchestrator/metrics.py` / `app/metrics.py` shape) | `<prefix>_api_request_count` (no `_total`) | `<prefix>_api_request_duration_ms_milliseconds_bucket` |
| OTel prom-shaped wrappers (analytics-agent — `app/metrics.py` `_Counter`/`_Histogram` classes) | `http_requests_total{service_name="<svc>"}` — disambiguate via service_name label | `http_request_duration_seconds_bucket{service_name="<svc>"}` |
| DataDog statsd direct (chat-api — `from datadog import statsd`) | `chat_api_api_request_count` | `chat_api_api_request_duration_ms_milliseconds_bucket` (DD agent emits in OTel-compatible shape on this stack) |
| Flask `flask.request` via DD statsd (customcheckout monolith) | `flask_request` (legacy untagged timing only — no count metric) | `flask_request` |

Verify metric exists via `mcp__plugin_kai_watchtower__chronosphere_query` before adding panel — empty result = MR not deployed yet OR metric name wrong, skip regen and re-check.

### Step 4 — Apply

First check existence:

```bash
chronoctl dashboards list 2>&1 | grep "slug: <slug>$"
```

- No match → `chronoctl dashboards create -f <slug>.yaml`
- Match → `chronoctl dashboards update -f <slug>.yaml`

Report URL: `https://recharge.chronosphere.io/dashboards/<slug>`

### Step 5 — Verify (optional)

Sanity check that envoy cluster has traffic:

```bash
chronoctl query instant 'sum(increase(envoy_cluster_upstream_rq_total{envoy_cluster_name=~"<httproute-regex>"}[24h]))'
```

Zero result → app not receiving traffic. Flag to user. Check FE routing / monolith proxy / k8s wiring.

## Gotchas

- **OTel histogram suffix**: OTel→Prom adds `_milliseconds` to histograms with `ms` unit. Query `<name>_duration_ms_milliseconds_bucket`, NOT `<name>_duration_ms_bucket`. Real bug observed: orchestrator template's `apiRequestP95LatencyByRoute` panel was empty for months because it queried the wrong suffix.
- **OTel counter has no `_total`**: OTel-emitted counters appear as `<name>_count` (or just `<name>`), NOT `<name>_total`. Real bug observed: orchestrator template queried `chat_orchestrator_audit_outbound_written_total` but actual metric is `chat_orchestrator_audit_outbound_written`.
- **OTel adapter shape is misleading**: `from app.metrics import statsd` (or `orchestrator.metrics`) LOOKS like DataDog statsd but is actually the OTel OTLP adapter. Confirm by reading the metrics module before assuming DD-style metric names.
- **Workload regex `-.*` trap**: requires trailing dash. Use `<slug>.*` for safety (matches both empty and dash-suffixed workloads).
- **Envoy ingress misses internal traffic**: most service-to-service calls hit k8s svc DNS, bypassing HTTPRoute / Envoy Gateway. App-emitted pod metrics are the truth signal; envoy panels alone will under-report.
- Probes (`/healthz`, `/readyz`) bypass envoy — naturally excluded from `envoy_cluster_upstream_rq*` counts.
- Namespace is NOT hardcoded — lives inside `httproute-regex`. Confirm full cluster name via discovery (Step 1a) before assuming.
- nginx_ingress / CloudArmour panels not relevant under Envoy Gateway — template already excludes them.
- `--from-registry` needs PyYAML. `uv run --with pyyaml python3` is the canonical invocation.
- Single-quote YAML escape: `'` → `''` inside `dashboard_json:`. Generator handles round-trip.
- Registry key vs deployed slug: chat-orchestrator's registry entry has `slug: orchestrator` to match the deployed dashboard. Generator falls back to registry key if `slug:` absent.

## Known apps (as of 2026-06-12)

| Registry key | Deployed slug | OTel | Custom panels | Notes |
|---|---|---|---|---|
| `chat-orchestrator` | `orchestrator` | yes (`chat_orchestrator_` via OTel adapter) | template defaults + `apiRequestRateByStatusClass` | template source. registry has `slug: orchestrator` override |
| `support-agent` | `support-agent` | yes (custom — OTel adapter) | `custom_panels/support-agent.py` (5 panels: chat duration p95, outcome rate, iterations + HTTP req/min + HTTP p95 by route) | HTTP panels populate post MR !508 deploy |
| `analytics-agent` | `analytics-agent` | yes (custom — prom-shaped OTel wrappers) | `custom_panels/analytics-agent.py` (8 panels: analyze by skill/status, LLM rate + p95, SQL rate + p95, HTTP req/min + p95) | HTTP panels populate post MR !130 deploy. analyze/LLM/SQL panels populate immediately. namespace=`prod` (NOT `ai-tooling`) |
| `chat-api` | `chat-api` | no (DataDog statsd direct) | `custom_panels/chat-api.py` (2 panels: HTTP req/min + p95) | service not live yet — panels populate post MR !3 deploy AND traffic cutover |

Source: `~/dev/giant-tooling/chronosphere/apps.yaml`.

### custom_panels/ reference scripts

| Script | Pattern | Key idiom |
|---|---|---|
| `support-agent.py` | inline dict literals per panel | original — verbose but explicit |
| `chat-api.py` | inline dict literals, only HTTP panels | smallest example, 2 panels |
| `analytics-agent.py` | `_ts_panel()` helper factory + PANELS dict | DRY for 8 panels |

Pick based on panel count. ≤3 panels: copy chat-api.py. ≥5: copy analytics-agent.py.
