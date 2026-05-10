# Session Protocol

> **Purpose**: define how WEB-MAIN session starts, plans, executes, and ends
> a unit of work. Auto-loaded by reference from `CLAUDE.md`. Applies to all
> collaborators (admin + Role A + Role B), not just Claude self.

---

## 1. Session = push unit

A **session** in make_web is one *push-worthy unit of work* (typically 1 PR).
Inside one session multiple `git commit`s accumulate locally on a `feature/*`
branch; **one `git push`** sweeps them as a single PR per Rule 6 in CLAUDE.md.
A push-worthy commit (per Rule 6) is what closes the session and triggers
`/review` + push.

```
session start ─► plan ─► commit ─► commit ─► … ─► /review ─► push (PR open) ─► merge ─► session end
                                                  ▲                                        │
                                                  │                                        ▼
                                                  └── fix loop (max 2) ────────  reporter pass
```

The session boundary matters because:
- `/review` runs once on `origin/develop..HEAD` covering ALL commits in scope
- Rule 7 cleanup (`cleanup-after-push.sh`) fires after the merge
- reporter consolidates `Report.md` + `Task.md` once per session, not per commit

---

## 2. Session start checklist

When WEB-MAIN session starts (user opens cmux WEB-MAIN tab + Claude Code
greeting + first user message), do this **before** any code edit:

1. **Branch state**: run `git status && git branch --show-current`. If on
   `main` or `develop`, abort code edits — operator must run
   `./tools/git-new-feature.sh <role> <topic>` first (HARD RULE).
2. **Sync develop**: `git fetch origin develop --quiet`. If feature branch is
   behind develop, ask operator before rebasing.
3. **Recent handoffs**: read the last ~10 lines of `.claude/Task.md § Handoffs`.
   Look for unresolved signals from prior session:
   - `REVIEW-FAIL: <sha>` — fix loop owed
   - `REVIEW-ABORTED: <sha>` — re-review owed
   - `BACK-BLOCKED: <reason>` / `FRONT-BLOCKED: <reason>` — escalation owed
   - **`SESSION-START-TODO: <action>`** — explicit pending action for this
     session's first move (e.g. "run `./tools/cmux_setup.sh`", "complete
     CODEOWNERS placeholder for new collaborator")
4. **Surface pending TODOs to operator**: if any of the above found, ask
   *first* whether to handle the pending item before the user's stated
   request. Do NOT silently start the user's request leaving the prior issue.
5. **Plan the session** per § 3 below before substantive edits.

---

## 3. Plan reporting (before substantive work)

Before writing code, editing files, or spawning sub-agents, present a plan
to the operator using the **standard table** below. Goal: operator sees
expected token cost, time, risk, and decision points up front.

### 3a. Standard plan template

```markdown
## 작업: <한 줄 한글 요약>

### 분담 + 추정

| Step | 터미널 | 에이전트 / 도구 | 동작 | 토큰 추정 |
|------|--------|----------------|------|----------|
| 1 | WEB-MAIN | direct OR agent name | … | ~XK |
| 2 | WEB-BACK | team-back (Codex) | … | ~YK codex-side |
| 3 | WEB-MAIN | reviewer + security 병렬 | … | ~ZK |
| ... | ... | ... | ... | ... |

**합계 추정**: ~AK Claude main + ~BK codex + ~CK review = **~totalK total / push**
**시간**: ~M-N분 (codex E + review F + CI G + 사람 결정 가변)
**Risk**: low / medium / high — 이유 (auth touch / migration / cross-cutting / etc.)

### 결정 필요 객관식 (있으면 한 번에 하나씩)
1. <질문 1>
   | 옵션 | 동작 | 추천 |
   |---|---|---|
   | A | … | ⭐ |
   | B | … | |

### 변동 요인
- /review FAIL → fix loop +1 cycle (~+30K)
- CI red → debug + re-push (~+20K)
- 큰 working tree dirty 시 stash 처리
```

### 3b. Korean summary rule

Plan reporting language: **한글 요약 + 영어 코드 식별자**. Korean for
narrative ("작업"/"분담"/"추정"), English for file paths, agent names,
commit messages, command snippets. Mirrors CLAUDE.md "Plan mode protocol"
language rule (2026-04-29 user request).

### 3c. Multiple-choice decisions

When user input needed mid-plan, use multiple-choice (3-4 options + 추천).
Wait for answer before proceeding to next decision. Never batch multiple
decisions in one turn (CLAUDE.md "Plan mode protocol" rule).

### 3d. When to skip the plan table

For genuinely trivial single-action requests ("how do I...", "show me
file X", "what does Y mean") — no plan table needed. Direct answer.
The threshold: if the request will result in any `Edit`, `Write`, or
multi-step `Bash` action, plan first.

---

## 4. Inside the session (commit accumulation)

- Each logical change = 1 commit via `./tools/git-stage-and-commit.sh
  "<conventional commit subject>" "<body>"`.
- Bundle trivial commits per Rule 6 (don't push after every commit).
- If a commit is >50 LOC OR touches production code, walk reviewer/security
  agents OR rely on Codex team's self-review (per CLAUDE.md hybrid pre-commit
  policy).
- If a commit is trivial (<50 LOC, pure docs/policy/tooling, no production
  code), reviewer + security agents are skipped (Rule 2).

---

## 5. Pre-push gate (`/review`)

Run **once** at session end, before `git push`, covering all accumulated
commits in `origin/develop..HEAD`:

```
WEB-REVIEW tab → "리뷰해줘" or `/review`
   ↓
verdict written to .claude/reviews/<sha>.md + latest.md
handoff line in Task.md § Handoffs:
   REVIEW-PASSED / REVIEW-FAIL / REVIEW-ABORTED
```

- **PASS / PASS-WITH-MINORS** → push + open PR + merge
- **FAIL** → fix loop in WEB-MAIN (max 2 cycles), re-commit, re-/review
- **ABORTED** → drift detected (HEAD advanced or origin/main moved); rebase
  + re-/review

---

## 6. Push + PR cycle

### 6a. Internal PR (own work)

After REVIEW-PASSED:

```
WEB-GIT tab (or WEB-MAIN if WEB-GIT not active) →
  ./tools/git-push-pr.sh                       # push + gh pr create --base develop
  ./tools/git-poll-merge.sh <PR#>              # CI green poll
  (admin self-approves on GitHub UI)
  gh pr merge <PR#> --squash --delete-branch   # squash merge
  git checkout develop && git pull             # sync
  # local feature branch deletion: see git-publisher.md Mode 1 step 7
  #   (use -D after gh pr view --json state == MERGED)
```

### 6b. External PR (Role A / Role B collaborator)

WEB-GIT polls `gh pr list --base develop --state open`, checks out via
`gh pr checkout <N>`, emits `PR-READY-FOR-REVIEW: #<N>`. Admin manually
triggers `/review` in WEB-REVIEW (hybrid policy per 2026-05-09 decision).
WEB-GIT then approves + merges OR posts FAIL comment with summary +
collapsible details. Full flow in `.claude/agents/git-publisher.md` Mode 2.

### 6c. Deploy PR (develop → main)

When develop has accumulated several vetted features, admin says
"deploy PR 열어줘" → WEB-GIT runs `gh pr create --base main --head develop`.
Admin self-approves + squash merges. Railway auto-deploys. Full flow in
`.claude/agents/git-publisher.md` Mode 3.

---

## 7. Session end checklist

After PR merged into develop:

1. **reporter pass** (once per session, not per commit):
   - Updates `.claude/Report.md` Last Updated section
   - Trims `.claude/Task.md § Handoffs` to ≤30 entries (archives older
     to `.claude/handoffs-archive/<YYYY-MM>.md`)
   - Narrow `docs/algorithm.md` sync if RECOMMENDATION dict changed
   - Appends `REPORTER-DONE: <sha>` handoff line
2. **Rule 7 cleanup**:
   - `./tools/cleanup-after-push.sh` — sends `/clear` to WEB-BACK / WEB-FRONT
     / WEB-REVIEW / WEB-GIT (init prompts re-sent for codex teams + WEB-GIT)
   - WEB-MAIN: run `/compact` manually (Claude can't self-/clear)
3. **Pending TODOs for next session**:
   - If anything explicit needs to fire on next session start, append a
     `SESSION-START-TODO: <action>` line to `Task.md § Handoffs`. The next
     session's start checklist (§ 2 above) will surface it.

---

## 8. When NOT to push (bundle locally)

Per Rule 6 in CLAUDE.md, accumulate locally without push if the commits are:

- Pure docs / policy (CLAUDE.md, agent files, AGENTS.md, etc.)
- Tooling self-use (`tools/*.sh`, `hooks/*`, `.github/*` minor)
- Sub-MINOR follow-ups (typo, dead code branch, comment polish)
- Handoff-only entries (Task.md handoff line additions)
- Reporter pass output (Report.md sync, Task.md trim)

Push when a *push-worthy* commit lands (milestone / production code /
migration / risky-zone touch / explicit "지금 push" / session-end).

---

## 9. Token budget orientation (rough)

| Phase | Typical tokens |
|---|---|
| Session start (read CLAUDE.md + Task.md + git status + plan) | ~10K |
| Per back-maker / front-maker run (Claude side) | ~15-30K |
| Per Codex team dispatch (claude poll only, codex side excluded) | ~3-8K |
| reviewer + security pair | ~15K |
| web-tester (inner-loop fast variant) | ~10-15K |
| `/review` Part A only (no UI paths) | ~25-35K |
| `/review` Part A + Part B (UI paths) | ~50-80K |
| git-manager (slim) | ~2K |
| git-publisher per push/merge cycle | ~3-5K |
| reporter pass | ~12-15K |
| Rule 7 cleanup | ~1K |

A typical feature PR (1 logical change, 1 review cycle, no fix loop) lands
around **~80-120K Claude tokens main + ~30K codex + ~30-50K review**.

Use these as plan-table sanity checks. If a plan totals far higher
(>250K), question whether to split into multiple sessions / PRs.
