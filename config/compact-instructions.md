Write the summary so the next task in a sequence can continue without the user repeating anything:
1. Every file read or edited: absolute path plus one line on what was learned or changed there.
2. Findings with their evidence (file:line, command, measured number), each marked verified (ran it) or inferred.
3. Completed work: every commit made (sha, subject, repo, branch), pushes, MRs/PRs (`<repo>!N` and URL), doit items (`<list> #N` and state), artifacts and notes written.
4. Decisions, and the user's corrections and stated preferences, quoted when short.
5. Open state: the task in progress, the next step, and anything waiting on the user.
6. Identifiers verbatim: paths, branches, shas, ids, URLs, and the exact commands that worked.
Drop tool output that was read once and led nowhere.
