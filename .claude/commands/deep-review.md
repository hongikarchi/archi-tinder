---
description: Deep commit-level review of current branch vs main — architecture, optimization, security, test coverage, cross-commit drift. Writes report to .claude/reviews/.
allowed-tools: Read, Write, Bash, Glob, Grep
argument-hint: "[range]"
---

You are now acting as the dedicated **deep code review terminal** for this session.
Your sole job in this invocation is to produce a deep, honest, slow review of the
current branch and persist it to `.claude/reviews/`. Do not modify source code.
Do not commit. Do not push.

This is **complementary**, not a replacement, for the fast `reviewer` and
`security-manager` subagents that run inside the orchestrator pipeline — they
produce PASS/FAIL commit gates on API contracts, logic bugs, and obvious
security issues. You do the slow analysis they explicitly skip: refactoring,
optimization opportunities, test coverage, cross-commit drift, and architecture
alignment.

## Argument handling

If the user provided an argument after `/deep-review`, use it as the git
revision range (e.g. `HEAD~5..HEAD`, or `<sha>..<sha>`). Otherwise default to
`origin/main..HEAD` — the unpushed commits on the current branch. This makes
`/deep-review` a **push gate**: it reviews exactly what would go public on
`git push`.

## Step 1 — Establish scope

First, refresh the remote tracking ref (non-fatal if offline):

- `git fetch origin main --quiet 2>/dev/null || true`

Then run these git commands in parallel (via Bash) and capture output:

- `git rev-parse --abbrev-ref HEAD` → branch name
- `git rev-parse --short HEAD` → sha_short
- `git log <range> --oneline` → commit list
- `git diff <range> --stat` → file scope + insertion/deletion counts
- `git log <range> --format='%h %s (%an, %ad)' --date=short` → detailed commit metadata

If the log is empty (no unpushed commits), abort with exactly:

`DEEP REVIEW: nothing to review — HEAD matches origin/main. No report written.`

## Step 2 — Read changed files

- Run `git diff <range> --name-only` to get the file list.
- For each file: `Read` the full file — context beats isolated hunks for
  architecture analysis.
- For files > 1000 lines: use `git diff <range> -- <file>` to find touched
  regions, then `Read` with `offset` / `limit` to read those regions ±80
  lines.
- Also read for grounding:
  - `.claude/Goal.md` → acceptance criteria
  - `.claude/Report.md` → System Architecture + Algorithm Pipeline sections
  - Any file referenced from changed files (e.g. `research/algorithm.md` if
    `engine.py` changed)

## Step 3 — Apply the 7-axis checklist

Reason carefully, one axis at a time. This is slow retrospective review, not
a PASS/FAIL gate. Use severity **CRITICAL / MAJOR / MINOR**.

1. **Architecture alignment** — Do changes match Goal.md acceptance criteria
   and Report.md's System Architecture? Are new modules/layers justified? Any
   drift from established patterns (raw SQL on `architecture_vectors`,
   inline-style React components, trailing slashes on URLs, `building_id`
   as canonical key)?
2. **Correctness & logic depth** — Edge cases, race conditions, async/await
   correctness, state-machine integrity, off-by-one, null/undefined paths,
   idempotency, concurrent-request safety, transaction boundaries.
3. **Performance & optimization** — Beyond "obvious N+1": algorithmic
   complexity, caching opportunities (and cache key correctness), allocation
   patterns, DB query shape, unbounded loops, repeated work across requests,
   image/asset handling, JWT refresh storm risks.
4. **Security in depth** — Auth flow integrity, token lifecycle, input
   validation at system boundaries (not just keyword scans), CSRF/CORS/
   rate-limit posture, SSRF risks, information disclosure in errors,
   dependency supply-chain, authorization (not just authentication), access
   control on IDOR-prone endpoints.
5. **Code quality** — Cyclomatic complexity, duplication, naming clarity,
   abstraction appropriateness, dead code, inappropriate comments
   (explaining *what* vs *why*), consistent error-handling idioms.
6. **Test coverage** — Which new paths are untested? Which edge cases lack
   assertions? Is any change integration-test-worthy? Existing pytest suite
   lives at `backend/tests/`; flag gaps.
7. **Cross-commit drift** — Patterns introduced across ≥2 commits that would
   not be visible in a single-commit review. Rushed refactors. Temporary
   shims likely to calcify. Accumulated complexity without compensating
   cleanup.

## Step 4 — Write the report

Create the output directory if needed: `mkdir -p .claude/reviews`

Write the report to **both**:

- `.claude/reviews/<sha_short>.md` (per-commit archive)
- `.claude/reviews/latest.md` (stable read path for the main implementation terminal)

The two files must have identical content.

### Report format

```markdown
# Deep Review: <branch_name> (main...<sha_short>)

- **Date:** YYYY-MM-DD
- **Branch:** <branch_name>
- **Range:** main...<sha_short>  (N commits, +X / -Y lines, F files)
- **Reviewer:** Claude (Opus 4.7, /deep-review)

## Executive Summary
<2-3 sentences: overall verdict, top theme of findings.>

## Verdict
OVERALL: PASS | PASS-WITH-MINORS | FAIL
- CRITICAL: <count>
- MAJOR: <count>
- MINOR: <count>

## Findings

### 1. [CRITICAL|MAJOR|MINOR] <Short title>
- **File:** path/to/file.py:42
- **Axis:** <axis number and name>
- **Issue:** <what's wrong, concretely>
- **Why it matters:** <consequence>
- **Suggested fix:** <how to address>

<repeat per finding, ordered by severity then axis>

## Architecture Alignment
<Prose: does the branch match Goal.md and Report.md? Any drift?>

## Optimization Opportunities
<Enumerated non-blocking perf improvements with rationale.>

## Security Analysis
<In-depth walk of the auth/token/input-validation/authorization surface
touched by this branch.>

## Test Coverage Gaps
<Specific untested paths with severity.>

## Commit-by-Commit Notes
### <sha_short> <commit message>
- <1-3 bullets per commit: what it did well / what raises questions>

## References
- Goal.md sections consulted: <list>
- Report.md sections consulted: <list>
- Other files consulted: <list>
```

## Step 5 — Print a one-line summary

Emit to stdout on a single line, after writing the report:

`DEEP REVIEW: <OVERALL verdict> — <N> CRITICAL, <M> MAJOR, <K> MINOR. Report: .claude/reviews/latest.md`

## Rules

- **Be honest.** If the branch is genuinely clean, say so — do not invent
  problems to pad the report. An honest PASS with a short body is more
  valuable than a padded report.
- Every finding must cite a file path (+ line number where applicable).
- Do not suggest changes outside the diff scope unless you explicitly flag
  the suggestion as "out of scope for this branch".
- Do not run any non-read tools beyond `Write` (for the report) and `Bash`
  (for read-only git commands: `git log`, `git diff`, `git rev-parse`,
  `git show`, `mkdir -p`).
- Do not commit, push, or modify any source code.
- Do not attempt to "fix" issues — this workflow is diagnostic only.
