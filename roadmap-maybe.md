# Roadmap -- Maybe

Ideas I've evaluated and parked. Build when there's a real itch, not before.

## /review-branch command

Reviews my current branch diff against the active feature's spec.md before committing. Fills the gap between "swarm finished" and "I commit."

What it would do:
1. Run `git diff main..HEAD` (or whatever the base branch is from facts.md)
2. Read the active feature's spec.md acceptance criteria
3. For each criterion, check if the diff addresses it
4. Flag drift: files changed outside plan scope, criteria not addressed, unexpected deletions
5. Flag deviations already noted by swarm-exec (read from qa_report.md if it exists)
6. Output a structured review to `features/{name}/reviews/branch_review.md`

Different from `/qa-report` which runs tests and checks exists/substantive/wired. This specifically reviews the diff shape -- what changed, was it in scope, did anything get missed.

When to build: when I find myself manually eyeballing `git diff` output for more than a few files and wishing I had a checklist.

## Items I evaluated and rejected

I considered these and intentionally skipped them. Documenting the reasoning so I don't re-evaluate later.

**More agents:** I have 10 agents, that's enough. Adding more creates model selection confusion for the orchestrator and burns context on descriptions that rarely match. If a new domain comes up repeatedly (3+ sessions), then I'll consider adding one.

**PostToolUse hook on test runs:** My test commands go through docker compose which already gives structured output. Adding a hook layer to parse pytest output and re-inject it is more complexity than value. Claude already reads the output.

**Auto-sync PostToolUse hook for preprod:** The conversational "sync to preprod" mode in CLAUDE.md works fine. Making it a hook means it's always-on or needs state management (env var, flag file). The current approach is simpler and I can turn it on/off with a sentence.

**More skills:** My 4 skills (c4-diagrams, mcp-builder, mdlive, splunk) cover templated output generation. Skills are for repeatable output shapes with reference material. If I find myself giving the same 3-paragraph prompt to generate something repeatedly, that's when a new skill earns its place.

**Dependency/import analyzer agent:** Nice in theory for Python projects, but the pyright-lsp plugin already catches import errors. A full import graph tool is something I'd use once per project, not per session. I'll just use `/swarm analyze` for that.
