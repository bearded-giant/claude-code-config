# SPL Query Patterns Reference

Common patterns for generating Splunk queries. Organized by visualization type and use case.

## Event Name Extraction

When events share a common prefix (e.g., `redis_session_manager session_created`, `redis_session_manager session_miss`), extract the event name with rex once and filter with `where`:

```
| rex field=message "prefix (?<event_name>\w+)"
| where event_name IN ("event_a", "event_b")
```

For single-event panels, skip rex and use direct string match in the base search -- it's faster:

```
index IN (...) "prefix event_name"
```

## Timechart Patterns

### Simple count over time

```
index IN (...) "event_string"
  | timechart span=15m count as metric_name
```

### Count split by a field

```
index IN (...) "event_string"
  | timechart span=15m count by field_name
```

### Multiple event types in one chart

```
index IN (...) "common_prefix"
  | rex field=message "common_prefix (?<event>\w+)"
  | where event IN ("event_a", "event_b")
  | timechart span=15m count by event
```

### Computed metric over time

```
index IN (...) "common_prefix"
  | rex field=message "common_prefix (?<event>\w+)"
  | where event IN ("event_a", "event_b")
  | timechart span=1h
    sum(eval(if(event="event_a",1,0))) as count_a,
    sum(eval(if(event="event_b",1,0))) as count_b
  | eval ratio=round(count_a/count_b, 2)
```

### Unique users over time

```
index IN (...) "event_string"
  | timechart span=1h dc(user_id) as unique_users
```

## Stats Patterns

### Count by one dimension

```
index IN (...) "event_string"
  | stats count as metric_name by dimension_field
  | sort -metric_name
```

### Count by two dimensions (cross-tab)

```
index IN (...) "event_string"
  | stats count as metric_name by field_a, field_b
  | sort -metric_name
```

### Count with unique users

```
index IN (...) "event_string"
  | stats count as total, dc(user_id) as unique_users by dimension_field
  | sort -total
```

### Top N by count

```
index IN (...) "event_string"
  | stats count as total, dc(user_id) as unique_users by entity_field
  | sort -total
  | head 20
```

### Multi-event summary (dashboard overview)

```
index IN (...) "common_prefix"
  | rex field=message "common_prefix (?<event>\w+)"
  | stats count as total,
    sum(eval(if(event="event_a",1,0))) as event_a_count,
    sum(eval(if(event="event_b",1,0))) as event_b_count,
    sum(eval(if(event="event_c",1,0))) as event_c_count
```

### Conditional sum on a numeric field

When a numeric field is a top-level Splunk extra (not in the message string):

```
  | stats sum(eval(if(event="target_event" AND numeric_field>0, numeric_field, 0))) as total_value
```

Do NOT use rex to extract numeric fields that are already top-level Splunk fields.

### Computed percentage

```
  | stats
    sum(eval(if(event="success",1,0))) as successes,
    sum(eval(if(event="failure",1,0))) as failures
  | eval success_rate_pct=round(successes/(successes+failures)*100, 1)
```

## Single Value Patterns

### Simple count

```
index IN (...) "event_string"
  | stats count as metric_name
```

### Distinct count

```
index IN (...) "event_string"
  | stats dc(user_id) as unique_users
```

## Investigation Patterns

### Timeline for a specific entity

```
index IN (...) "common_prefix" user_id=XXXXX store_id=XXXXX
  | sort _time
  | table _time, message, field_a, field_b, field_c
```

### Compare two time windows

```
index IN (...) "event_string" earliest=-2h latest=-1h
  | stats count as previous_hour
  | appendcols [search index IN (...) "event_string" earliest=-1h latest=now | stats count as current_hour]
  | eval change_pct=round((current_hour-previous_hour)/previous_hour*100, 1)
```

## Span Selection Guide

| Expected volume | Recommended span | Use case |
|---|---|---|
| >5000/hr | span=5m | High-traffic events, real-time monitoring |
| 1000-5000/hr | span=15m | Standard production events |
| 100-1000/hr | span=30m or span=1h | Medium-traffic events |
| <100/hr | span=1h or span=4h | Low-volume events, error tracking |
| <10/hr | span=4h or span=1d | Rare events, daily trends |

## Common Gotchas

1. **Fields in eval must be quoted**: `if(event="value",1,0)` not `if(event=value,1,0)`
2. **Rex on the wrong field**: structured logging extras are top-level fields, not inside `message`. Only use rex for extracting from the message text itself.
3. **dc() is expensive**: use sparingly on high-cardinality fields. Fine for user_id, avoid on session_id in high-volume searches.
4. **head vs limit**: `| head 20` is post-processing. For search-time limits, use `| streamstats count | where count <= 20` (but head is usually sufficient).
5. **Backslash escaping in Dashboard JSON**: rex patterns like `\w+` become `\\w+` in JSON strings. Double-escape all backslashes.
6. **No inline comments in SPL**: unlike SQL, SPL does not support `--` or `/* */` comments.
7. **eval if() returns null on no match**: `if(condition, value)` without an else returns null. Always provide the else: `if(condition, 1, 0)`.
