# Skio PR format

Consumed by `ship-it` Step 3 for GitHub repos in the orgs `skio-org` and
`RechargePayments`. Base-branch resolution, routing (active feature dir →
`.giantmem/` → repo root), write, and print are owned by ship-it Step 3 — this file
owns the FORMAT only. The shape is the one Skio engineers use on `skio-org/frost`.

## Building the description

1. **Branch context**: current branch, commits via `git log <base>..HEAD`, full diff via `git diff <base>..HEAD`. Read the diff for understanding.
2. **Why before what**: the reader is a Skio reviewer who did not see the ticket. Say what was wrong or missing and what they would miss without this change.
3. **Scope is behavior, in the places it lands**: one bullet per behavior change, naming the component, page, or module a reviewer would open. Renames and type changes that reach callers get their own bullet. Deleted modules name who absorbed their callers. Generated artifacts name the command that produced them.
4. **Blast radius is for the person on call**: which pages, services, or callers behave differently, what a user could notice, what is visual only versus functional.
5. **Verification is evidence, not claims**: the tests added or changed and what makes them fail, the exact commands with their counts, and any live run with its environment. Name what was NOT checked and why; Skio reviewers read this section first.

## Output structure

```markdown
## Why

<two or three sentences: the problem or ticket, and what a reader would miss without this change>

## Scope

- <behavior change, with the component or file it lands in>
- <rename or type change and the callers it reaches>
- <deleted module and who absorbed its callers>
- <generated artifact and the command that produced it>

## Blast Radius

<prose: pages, services, or callers that change behavior; what a user could notice; visual only vs functional>

## Verification

- <test file added or changed, and what breaks it before the fix>
- <exact command and its count, e.g. `pnpm test:unit --selectProjects dashboard`: 789 suites passed>
- <live run: environment, theme or resolution when UI, what was exercised, what could not be checked and why>
```

## Style

- Why and Blast Radius are prose. Scope and Verification are bullets.
- Normal capitalized sentences; this is a team-facing format, not caveman. Do NOT apply the bullet-format post-processing pass.
- Code identifiers in backticks, file paths where they point the reviewer somewhere, no `file:line`.
- No meta phrases ("This PR adds", "This change introduces"); start with the fact.
- No commit-by-commit history, no kai headers, no Jira section.
- Length: Why at most 3 sentences; Scope 3 to 8 bullets; Blast Radius at most 4 sentences; Verification 2 to 5 bullets.
- Title: the branch's primary commit subject. Keep a ticket prefix the branch already carries (`refactor(ENG-9769): migrate legacy badges onto the design system`); never invent one.

## Example output

```markdown
## Why

Milestone 2 restyles badges in `@frost/design-system`. Dashboard pages still on a legacy badge would miss it. This moves every legacy badge outside `src/components/ui/` onto the package and deletes the frozen fork.

## Scope

- Read-only labels are now `Badge` from the package. Legacy colors map to tones (`gray` to `neutral`, `green`/`red`/`yellow` to `success`/`error`/`warning`).
- Lifecycle statuses with a preset become `StatusBadge`: "Deleted" in `Flow/NodeEdit/ActionForm.tsx` and the product statuses in `ProductSelectionModal.tsx`.
- `SettingsPage/configTypes.ts` `badge.color` becomes `badge.tone: BadgeTone`.
- Deleted `src/components/ui/base/badges/` and its barrel exports; the two frozen callers use the package `Badge`.
- Generated: `biome-config/dashboard-legacy-ui-grandfathered.json` via `pnpm prune-legacy-ui-grandfather`.

## Blast Radius

Visual only, across A/B test, analytics, flow editor, surveys, and settings pages. Badges shrink to `sm` where the legacy default was `md`.

## Verification

- New `ConditionFormChips.test.tsx` covers chip removal for all three forms; all three fail when their `onRemove` filter is broken.
- `pnpm test:unit --selectProjects dashboard`: 789 suites passed. Dashboard typecheck and knip pass.
- Live run on the dev store at 1440x900, light and dark: chips remove by click and keyboard. Could not check the session status table (no data).
```
