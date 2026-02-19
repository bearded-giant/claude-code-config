# Dashboard Studio JSON Schema Reference

Splunk Dashboard Studio uses JSON definitions. This is the structural reference for generating valid, importable dashboards.

## Top-Level Structure

```json
{
    "title": "string",
    "description": "string",
    "inputs": { ... },
    "defaults": { ... },
    "dataSources": { ... },
    "visualizations": { ... },
    "layout": { ... }
}
```

## Defaults

Use `defaults` to apply shared queryParameters (like time tokens) to all data sources, avoiding repetition in each individual data source.

```json
"defaults": {
    "dataSources": {
        "ds.search": {
            "options": {
                "queryParameters": {
                    "earliest": "$global_time.earliest$",
                    "latest": "$global_time.latest$"
                }
            }
        }
    }
}
```

When `defaults` is set, individual data sources do NOT need `queryParameters` -- they inherit from defaults.

## Inputs

Time range picker wired to all data sources via token.

```json
"inputs": {
    "input_global_time": {
        "type": "input.timerange",
        "options": {
            "token": "global_time",
            "defaultValue": "-4h@m,now"
        },
        "title": "Time Range"
    }
}
```

Common defaults: `-1h@m,now`, `-4h@m,now`, `-24h@h,now`, `-7d@d,now`

Dropdown filter example (for filtering by a field value):

```json
"input_auth_filter": {
    "type": "input.dropdown",
    "options": {
        "token": "auth_filter",
        "defaultValue": "*",
        "items": [
            {"label": "All", "value": "*"},
            {"label": "Shopify", "value": "shopify"},
            {"label": "Auth0", "value": "auth0"}
        ]
    },
    "title": "Auth Method"
}
```

Use `$token_name$` in queries to reference input values. For time: `$global_time.earliest$` and `$global_time.latest$`.

## Data Sources

Each data source is a search that feeds one or more visualizations. When `defaults` handles queryParameters, data sources only need `query`.

```json
"dataSources": {
    "ds_unique_id": {
        "type": "ds.search",
        "options": {
            "query": "index IN (...) \"search terms\" | ..."
        },
        "name": "Human-readable search name"
    }
}
```

### Naming convention

Use `ds_{tab}_{panel}` format: `ds_1_1`, `ds_1_2`, `ds_2_1`, etc. For variant queries on the same panel (e.g., table + chart), use a letter suffix: `ds_2_8`, `ds_2_8b`.

### Escaping

Backslashes in SPL (rex patterns) must be double-escaped in JSON:
- SPL: `rex field=message "prefix (?<event>\w+)"`
- JSON: `"rex field=message \"prefix (?<event>\\w+)\""`

## Visualizations

Each visualization is a panel on the dashboard.

```json
"visualizations": {
    "viz_unique_id": {
        "type": "splunk.line",
        "title": "Panel Title -- describe what it shows",
        "dataSources": {
            "primary": "ds_unique_id"
        },
        "options": {}
    }
}
```

### Naming convention

Use `viz_{tab}_{panel}` matching the data source: `viz_1_1`, `viz_1_2`, etc.

### Visualization types and when to use them

| Type | Use for | SPL output shape |
|---|---|---|
| `splunk.line` | Trends over time | `timechart span=Xm count [by field]` |
| `splunk.area` | Stacked trends (cumulative) | `timechart span=Xm count by field` |
| `splunk.column` | Comparisons between categories | `stats count by field` (few categories) |
| `splunk.bar` | Horizontal comparisons | `stats count by field` (many categories or long labels) |
| `splunk.pie` | Proportional distribution | `stats count by field` (2-6 categories max) |
| `splunk.table` | Detailed breakdowns, cross-tabs | `stats ... by field1, field2` or multi-column output |
| `splunk.singlevalue` | Key health indicators | `stats count as metric_name` (single row, single column) |
| `splunk.markdown` | Dashboard notes, section headers | Static text, no data source needed |

### Single value panel options

```json
"options": {
    "majorColor": "#53a051",
    "sparklineDisplay": "off",
    "trendDisplay": "percent",
    "unit": "events",
    "unitPosition": "after"
}
```

### Table panel options

```json
"options": {
    "count": 20,
    "dataOverlayMode": "none",
    "drilldown": "row",
    "rowNumbers": false
}
```

## Layout

The layout has three parts: `options` (dashboard-level), `tabs` (tab definitions), and `layoutDefinitions` (per-tab structure with panel positioning).

### With tabs

`tabs` is an **object** with `items` (array of tab descriptors) and `options`. Each tab references a `layoutId` that maps to a key in `layoutDefinitions`. Each layout definition has its own `type`, `options`, and `structure`.

```json
"layout": {
    "options": {
        "submitButton": false,
        "submitOnDashboardLoad": true
    },
    "globalInputs": ["input_global_time"],
    "tabs": {
        "items": [
            { "layoutId": "tab_overview", "label": "Overview" },
            { "layoutId": "tab_details", "label": "Details" }
        ],
        "options": {
            "barPosition": "top",
            "showTabBar": true
        }
    },
    "layoutDefinitions": {
        "tab_overview": {
            "type": "grid",
            "options": {
                "display": "auto",
                "width": 1440,
                "height": 960,
                "gutterSize": 8
            },
            "structure": [
                {
                    "item": "viz_1_1",
                    "type": "block",
                    "position": { "x": 0, "y": 0, "w": 1440, "h": 300 }
                }
            ]
        },
        "tab_details": {
            "type": "grid",
            "options": {
                "display": "auto",
                "width": 1440,
                "height": 960,
                "gutterSize": 8
            },
            "structure": [
                {
                    "item": "viz_2_1",
                    "type": "block",
                    "position": { "x": 0, "y": 0, "w": 1440, "h": 300 }
                }
            ]
        }
    }
}
```

### Without tabs (single layout)

When there are no tabs, use a single layout definition with a default layoutId.

```json
"layout": {
    "options": {
        "submitButton": false,
        "submitOnDashboardLoad": true
    },
    "globalInputs": ["input_global_time"],
    "layoutDefinitions": {
        "default": {
            "type": "grid",
            "options": {
                "display": "auto",
                "width": 1440,
                "height": 960,
                "gutterSize": 8
            },
            "structure": [
                {
                    "item": "viz_1_1",
                    "type": "block",
                    "position": { "x": 0, "y": 0, "w": 1440, "h": 300 }
                }
            ]
        }
    }
}
```

### Key rules

- `layout` must NOT have a top-level `type` property
- `layout` must have `layoutDefinitions`
- `tabs` is an **object** (not an array) with `items` and `options`
- Each `layoutDefinitions` entry is keyed by the `layoutId` from `tabs.items`
- Tab-level settings (width, height, backgroundColor, gutterSize) go in each layout definition's `options`, not in `layout.options`
- Dashboard-level settings (submitButton, submitOnDashboardLoad) go in `layout.options`

### Positioning guide

| Layout | x | w |
|---|---|---|
| Full width | 0 | 1440 |
| Left half | 0 | 720 |
| Right half | 720 | 720 |
| Left third | 0 | 480 |
| Middle third | 480 | 480 |
| Right third | 960 | 480 |

Heights:
- Single value panels: h=120 to h=150
- Charts (line, area, column, bar): h=250 to h=350
- Tables: h=250 to h=400
- Markdown notes: h=80 to h=120

Y-positioning: stack panels vertically with 10px gaps. E.g., first row at y=0 with h=300, second row at y=310, third at y=620.

### Global inputs placement

`"globalInputs"` lists input IDs that appear at the top of every tab. The time picker should always be global.

Tab-specific inputs can be added to a tab's structure as input blocks:

```json
{
    "item": "input_auth_filter",
    "type": "input",
    "position": { "x": 0, "y": 0, "w": 300, "h": 50 }
}
```

## Compatibility

- Tabs require Splunk Cloud or Enterprise 9.x+
- If tabs are not supported, fall back to a single `structure` array (no `tabs` key) or split into separate dashboards
- The `splunk.singlevalue` type replaced `splunk.singlevalueradial` in newer versions
- Dashboard Studio is also called "Dashboards (Classic)" vs "Dashboard Studio" in some Splunk versions -- Studio is the JSON one
