---
description: "Recharge planning method -- outcomes-first planning for data analysis and migration projects"
argument-hint: "[optional project name or brief description]"
---

# Recharge Planning

Structured planning method for data analysis, migration, and enrichment projects. Outcomes-first, verify-small, slice-for-speed.

This is a guided, conversation-driven workflow. The user may not know exactly what they need yet -- that's the point. Walk them through it. Each phase requires user confirmation before proceeding.

If `$ARGUMENTS` contains a project name or description, use it as context. If empty, start by asking what the project is about.

## Phase 1: What's the Project?

If the user didn't provide context in the arguments, ask:

> What's the project? Give me the broad picture -- what are we trying to produce or figure out?

Let them describe it loosely. Don't force structure yet. Listen for:
- What entity/thing they're analyzing (beta flags, vendors, stores, etc.)
- What they want to know about each one (fields, attributes, assessments)
- Where results need to end up

Reflect back a short summary of what you heard before moving on.

## Phase 2: Outcomes as Fields

Help the user define outcomes as **concrete data fields**, not tasks.

If they describe things loosely (like the beta flag example: "figure out the purpose", "who owns it", "is it risky"), translate those into structured output fields grouped by category.

Guide with:

> It sounds like for each {entity}, you want to know these things. Let me organize what I'm hearing into output fields:
>
> **{CATEGORY_1}**
> | Field | Description | Example Value |
> |-------|-------------|---------------|
> | {field} | {what it captures} | {concrete example} |
>
> **{CATEGORY_2}**
> | Field | Description | Example Value |
> |-------|-------------|---------------|
> | {field} | {what it captures} | {concrete example} |

The categories should come from what the user described -- don't invent categories they didn't mention. Use their language for category names.

Ask: **Does this capture what you want? Any fields missing or wrong?**

If the user adds more, incorporate and re-present. Loop until they confirm.

## Phase 3: Data Sources

For each field, identify where the data comes from. Be specific -- not "the database" but which table, which column, which API, which git command.

Present as an extension of the field table:

> Now let's figure out where each of these comes from:
>
> **{CATEGORY}**
> | Field | Source | Method |
> |-------|--------|--------|
> | {field} | {specific table/file/API/tool} | {how to extract it} |

For each field, flag if the source is:
- **Clear** -- we know exactly where it is and how to get it
- **Needs discovery** -- we think we know but need to verify
- **Ambiguous** -- not obvious where this lives

Ask: **For the "needs discovery" and "ambiguous" ones -- any ideas on where to look, or should we defer those?**

Recommend deferring ambiguous sources from the first pass.

## Phase 4: Destination Mapping

The user must specify where results land -- database columns, spreadsheet fields, output schema.

Ask: **Where do these results go? What's the destination schema?**

Present the full pipeline:

| Field | Source | Method | Destination Column |
|-------|--------|--------|--------------------|
| {field} | {source} | {method} | {column} |

Every field must map to a destination. If there's no destination, it's either out of scope or the destination needs to be created first.

## Phase 5: Difficulty Assessment

For each field in the mapping, rate on four axes:

| Field | Difficulty | Speed | Risk | Value |
|-------|-----------|-------|------|-------|
| {field} | easy/hard | fast/slow | low/high | low/high |

Explain ratings briefly for any non-obvious ones. For example:
> "owner" is **easy/fast** -- git log on first commit, straightforward.
> "purpose" is **hard/slow** -- requires reading code + commit messages + flag name and making a judgment call.
> "risk level" is **hard/high-risk** -- subjective assessment, different people would rate differently.

**Recommend against including in first pass** any fields that are:
- hard + slow
- hard + high risk
- low value regardless of difficulty

Ask: **Agree with these ratings? Anything I'm over- or under-estimating?**

## Phase 6: Hypothesis Verification

Before building the full plan, verify the approach works on a small sample (3-5 cases).

1. State the proposed approach for each field:
   > Here's how I'd get each data point for a single {entity}: {approach per field}. Sound right?

2. After confirmation, run it on 3-5 real examples.

3. Present results in the destination schema format and ask:
   > Here's what I got for {n} test cases. Does this look right? Anything off?

Do not proceed until the sample checks out. If something's wrong, adjust the approach and re-verify.

## Phase 7: Acceleration

After the sample validates, look for ways to cut the total work down:

1. **Skip cases** -- find entities that can be eliminated upfront (no usage, already deprecated, already documented, etc.). Quantify how many this removes.

2. **Reuse intermediate outputs** -- if getting one field produces data useful for another field, capture it. Call these out:
   > When we git log for "owner", we also get the commit date and message. Capture those -- they feed into "when added" and "purpose" fields for free.

3. **Fast slices** -- group entities by how easy they are to process. Batch the easy ones first.

Present:
> Of {total} {entities}:
> - {n} can be skipped ({reason})
> - {n} are fast-path ({reason})
> - {n} require full analysis
>
> Recommend: eliminate the skip cases first, batch the fast-path, then work through full analysis.

## Phase 8: Micro Pieces

Break the remaining work into the smallest verifiable pieces. Each piece should:

1. Be independently completable and verifiable
2. Reuse outputs from prior pieces where possible
3. Produce results that map to destination columns

Present as a numbered sequence:

```
1. {piece} -> produces: {fields} -> verify: {how to check}
2. {piece} (reuses: {what from #1}) -> produces: {fields} -> verify: {how to check}
3. {piece} -> produces: {fields} -> verify: {how to check}
```

Ask: **Does this breakdown make sense? Any pieces too big or missing?**

## Rules

- Guide the user. They may not have a clear picture yet -- that's expected. Help them find it.
- Translate loose descriptions into structured fields. Use the user's language, not jargon.
- Every output field must map to a destination column. No orphan outputs.
- Always rate difficulty before committing to a plan. The user should know the cost of each field.
- Verify small before going big. 3-5 sample cases before full execution.
- Capture and reuse intermediate outputs. If a git log gives you 3 fields worth of data, don't throw 2 away.
- Break big into micro. If a piece can't be verified in a few minutes, it's too big.
- Never skip the outcomes conversation. If the user jumps to "just do it", pull them back to defining what "it" produces.
- When the user describes something subjective or judgment-based (like "risk level" or "purpose"), flag it as hard/slow and recommend concrete proxies where possible (like "is it in service_director" instead of "is it risky").

$ARGUMENTS
