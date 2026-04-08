---
description: Review an MR and draft a casual Slack/MR response from a Principal Engineer perspective
---

# Review MR

Review a merge request and produce a ready-to-send response for Slack or MR comment.

## Inputs

The user will provide some combination of:
- MR link or number (use `gl` CLI to fetch diff and details)
- Context: a Slack message, question, or review ask explaining what they want reviewed
- Optional: external docs links (fetch and review)
- Optional: screenshots of UI/figma
- Optional: specific files to reference (read them)

$ARGUMENTS may contain the MR number or URL directly.

## Steps

1. **Fetch the MR** — get the full diff and description via `gl`
2. **Understand the ask** — what is the user's colleague actually asking? architecture validation? pattern check? code quality? all of the above?
3. **Search for existing patterns** — find comparable patterns in the codebase. this is critical context for "is this approach sound?" questions
4. **Fetch external docs** if linked — understand the constraints of external APIs/services involved
5. **Read referenced files** if mentioned
6. **Form an opinion** — as a Principal Engineer reviewing for a team:
   - Is the overall approach sound?
   - Are there existing patterns this should follow or diverge from?
   - What are the concrete issues to fix before merge?
   - What's fine as-is and doesn't need overthinking?

## Output

Draft a message the user can copy-paste into Slack or an MR comment. The user will edit it themselves before sending.

### Tone and format

Match these real examples exactly — this is the target output:

**Example 1** (endpoint review — approach validation + action items):

```
ok looked at the MR and related things.

the approach is solid. fetch all + redis cache + server-side ?search= is the right call here.
shopify's productTags query has no filtering support so there's no way around grabbing everything, and tags are tiny strings so even a few thousand is nothing. custom pagination would be over doing it for IMO.

few things before merge:
bump page size from 250 to 5,000 — shopify supports it and it cuts way down on round trips / gql cost … just less to deal with
add a hard cap on total tags (~10k) with a warning log, just as a safety valve for stores way out of band of "normal"
add some error handling around the shopify gql calls. right now if it fails mid-pagination the whole request 500s with no context

a total nit: the mutation variable name in the gql method should be query since it's not a mutation. make sense?

so yeah. no need for custom pagination, no need for background cache warming. 1hr TTL + force_refresh is fine.
```

**Example 2** (POC review — deeper technical finding explained clearly):

```
ok looked at the MR and the surrounding code.

overall approach is solid. delegate access tokens stored through the existing store integration infrastructure, GQL mutation is clean, test coverage is good for a POC.

there's a cache race condition possible in `provision_shopify_store_front_token`.

you check dogpile, get "not found", then create the access record manually. that's good.

but dogpile still has the stale miss cached. so when `set_or_create_secret_by_integration_type` calls `find_or_create_integration_access`, it hits cache then gets "not found" again...and creates a duplicate.

if you add `self.delete_integration_access_from_cache("shopify_store_front", store_id)` after the flush it would solve.

I bet tests won't catch it since dogpile is probably a passthrough in test, but prod would I'm sure.

small thing: the `gql_result["delegateAccessTokenCreate"]["delegateAccessToken"]["accessToken"]` chain will throw a raw `KeyError` if shopify returns something unexpected. `_make_request` handles `userErrors` but doesn't guarantee the inner response shape. a try/except with a clearer message would save debugging time later.

nit: shopify calls it "Storefront" (one word) in their docs. `shopify_storefront` would match their terminology better than `shopify_store_front` but it's a preference thing, easy to grep-rename later if it matters.

tests are the right three cases — create, update, and gql-failure-no-db-write. no notes there.
```

Key qualities of these examples:
- lowercase everything
- casual, like talking to a colleague — "so yeah", "just less to deal with", "make sense?"
- opens with verdict, not preamble
- actionable items are plain text lines, not markdown bullet points
- nits are clearly separated and labeled as nits
- closes by explicitly saying what does NOT need more work
- no emoji, no headers, no markdown formatting beyond backticks for names
- short paragraphs with breathing room between them
- has opinions, doesn't hedge

### Anti-patterns

- don't write a formal code review with file-by-file comments
- don't use markdown bullet points (`-`) for the action items — just plain text lines
- don't repeat back what the person said
- don't hedge ("i think maybe possibly...") — have an opinion
- don't suggest things that are clearly overengineering for the use case
- don't organize with headers, sections, or numbered phases
- don't use title case or sentence case — all lowercase
