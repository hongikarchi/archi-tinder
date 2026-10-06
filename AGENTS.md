# Make Web (archi-tinder) — shared instructions for every worker

This file is the **single shared rulebook** for humans, Claude Code and Codex.
Codex reads it directly. Claude Code loads it through `CLAUDE.md` (`@AGENTS.md`),
which adds Claude-only workflow detail. Rules here win over any other doc; if two
docs disagree, fix the other one.

Path-scoped conventions live next to the code they govern: `backend/AGENTS.md`,
`frontend/AGENTS.md`, `web-testing/AGENTS.md`. Procedures live in `docs/runbooks/`.

## What this repo is

React frontend + Django backend. The building corpus comes from a sibling repo
(Make DB) via a read-only PostgreSQL database. The running code is the source of
truth for architecture and API surface — derive it by reading the code.

| Need | Read |
|---|---|
| Branch / PR / roles / file ownership | `CONTRIBUTING.md` |
| Local setup (Windows + macOS), deploy to production | `docs/runbooks/local-setup.md`, `docs/runbooks/deploy.md` |
| Visual design system (MUST before any UI work) | `DESIGN.md` |
| Recommendation algorithm theory | `docs/algorithm.md` |
| Building DB schema + Make-DB ownership rules | `docs/database-schema.md` |
| Design decision records | `docs/plans/` |
| Backlog + done log | `Task.md` (moving to GitHub Issues) |

## Product identity

Core promise: 10–15 swipes → "Aha!" — the app has captured the user's taste.
> "이 앱이 내 미묘한 취향을 벌써 눈치챘네?"

Two pillars: 물리적 직관성 (physical intuitiveness) + 마법 같은 반응성 (magical
responsiveness). Theory in `docs/algorithm.md`.

## Branch model — HARD RULES

GitHub Flow with a `develop` integration branch.

- `main` — production (Railway + Vercel auto-deploy). PR-only, force-push blocked.
- `develop` — integration. PR + status check. Sole-admin CODEOWNERS makes Code
  Owner review self-unsatisfiable → admin squash-merge (`gh pr merge --admin`).
- `feature/<role>-<topic>` — work branches. Roles: `algo-` (A, algorithm),
  `sns-` (B, profiles/boards/social), `admin-` (C, everything else),
  `claude-` (Claude Code), `codex-` (Codex).

1. **Never commit on `main` or `develop`.** Always a `feature/*` branch.
2. **Run `git status` before any edit.** On `main`/`develop`:
   `tools/git-sync-develop.sh && git checkout -b feature/<role>-<topic>`
   (not `git pull` — the script survives the post-deploy develop force-reset).
3. **Never `git push origin main|develop`.** Pushes go from `feature/*`; `develop`
   via PR; `main` via a separate develop→main PR.
4. **Never `--force`, `--force-with-lease`, `--no-verify`, `rebase -i`,
   `reset --hard` on shared branches.** Single carve-out: the post-deploy
   force-reset of `origin/develop` to `origin/main` (Bug #5), only in the
   deploy window, only per `docs/runbooks/deploy.md` §4.
5. **PRs target `develop`.** `develop → main` is a deploy, needs a deploy keyword.
6. **Once per clone:** `./tools/install-hooks.sh` (migration-numbering pre-push hook).
7. **Concurrent workers share carefully.** A separate clone per worker is
   recommended, not required (user ruling 2026-09-26, Task.md DEPLOY-BLOCKER-1 ⑤).
   In a shared checkout: one branch per active session; **never switch branches,
   stash, or reset while another session is active there** (check `git status`
   and the reflog at session start); preserve other workers' changes; prefer
   `git worktree`-free isolation — worktrees share one `.git` and a 2026-05-31
   incident moved another checkout's HEAD. Sub-agent worktree isolation inside
   one Claude session is unrelated and fine.

If `git status` at session start shows `main`/`develop` with uncommitted changes,
save the work on a new `feature/*` branch first. Never stage on a protected branch.

## Working and publishing

- Implement on a feature branch; review the diff and run the checks that match
  the change (`tools/back-validate.sh`, `tools/front-validate.sh`, `make test-local`)
  before committing. Never commit secrets (`.env*`, keys, tokens).
- Commit messages: conventional-commit prefix (`feat|fix|refactor|chore|docs|test|security|perf(scope): …`),
  terse body, trailer kept exact. Korean subject text is fine.
- **Publish gate.** After a commit the default is STOP. Push / PR open / merge need
  an explicit trigger in the user's latest message — one of
  `push`, `푸시`, `올려`, `open PR`, `PR 만들어`, `PR 올려`, `merge` — or an approved plan
  file that authorizes publishing. **Deploying `develop → main` needs a deploy
  keyword specifically**: `deploy`, `배포`, `배포해`, `ship`, `release`. Plain
  `push`/`merge` never authorizes a base=main PR. This is the only list; other docs
  link here.
- Forbidden regardless of trigger: direct pushes to `develop`/`main`;
  `gh pr create --base main` except the deploy PR `--head develop`; force /
  no-verify / history rewrite on shared branches (HARD RULE 4).
- A hook blocks the forbidden git commands at the tool layer for Claude
  (`.claude/hooks/git-guard.py`) and Codex (`.codex/hooks.json` + `.codex/rules/`).
  Fail-open; GitHub branch protection is the server-side backstop.
- Audit trail: record shipped work (Task.md `## Done` today; GitHub Issues after the
  tracking migration) in the same PR as the work. Claude does this with the
  `reporter-inline` skill; Codex does it directly.

## Data rules

- Building references use `canonical_bld_id` (TEXT PK, e.g. `'bld_000344'`) —
  never `name`, `slug`, or any language-dependent field.
- `canonical_v2_buildings` is owned by Make DB: read-only raw SQL via the
  `'buildings'` connection; never ORM, never migrate (`config/db_router.py` blocks it).
- Every building query gates on `is_publishable = true` (~6–7% of rows are not
  publishable; semantics in `docs/database-schema.md`). `engine._build_filter_sql`
  already emits it; raw SQL elsewhere must add it.
- Embeddings are pre-computed; SentenceTransformers is not a dependency.
- `docs/algorithm.md` holds **design intent** (admin / algorithm collaborator via
  PR). Parameter values live only in `backend/config/settings.py` RECOMMENDATION;
  `docs/algorithm-hyperparameters.md` is **generated** from it by
  `make hyperparams` (`tools/gen-hyperparams.py`, CI fails when stale) — never edit
  it by hand; document a key by commenting it in `settings.py`. Implementation
  work may only append dated `_(Updated YYYY-MM-DD <sha>: …)_` one-liners to
  `docs/algorithm.md` and bump its "Last verified" line.

## Product Constitution

Highest-level tiebreaker when two valid choices conflict.

**Out of scope without explicit user re-authorization:** romance/dating (P2 is
aesthetic-taste matching), real-estate transactions, materials marketplace,
contractor matching, blueprint/CAD marketplace, design-as-a-service, markets
outside Korea (English UI is supported; corpus + community are Korea-first),
industries outside architecture (interior, landscape, furniture).

**Decision principles, in order:**
1. **Out-of-scope check first** — crossing a boundary → stop and ask.
2. **Persona priority** — P2 (Person→Person) > P1 (Firm→Jobseeker) > P3
   (Firm→Client) > P4 (Individual/gateway). Reordered 2026-09-17 by user decision
   (`docs/plans/2026-09-17-competition-team-design.md` §1).
3. **Foundation correctness > feature breadth.**
4. **Honest matching > engagement metrics** — never trade taste quality for
   session length or swipe count.
5. **External-dependency restraint** — extend Gemini / OpenAI / HuggingFace /
   Cloudflare R2 / Neon / Railway / Vercel before adding a service; new ones need
   user approval.
6. **Two sources of truth for the algorithm** — design intent and phase semantics:
   `docs/algorithm.md`; parameter values: `backend/config/settings.py`
   RECOMMENDATION (the doc's table is synced from code, never the reverse).
7. **Korea-first** — when localization decisions conflict, Korean UX wins.

Working principle: problem definition → written plan → architecture before
tactical code → foundational correctness over polish.

## Audit trail locations

| Category | Location | Writer |
|---|---|---|
| Backlog + done log | `Task.md` (→ GitHub Issues + Project, staged migration) | the session, same PR as the work |
| Algorithm reference (design intent) | `docs/algorithm.md` | admin / algorithm collaborator via PR; sessions append dated notes |
| Hyperparameter table (generated) | `docs/algorithm-hyperparameters.md` via `tools/gen-hyperparams.py` | never hand-edited |
| Execution plans (branches, delegation, PR sequence) | `.claude/plans/*.md` (Claude), archived on ship per its README | the session |
| Design decision records (what/why, Korean) | `docs/plans/*.md` | admin + session via PR |
| Operator runbooks | `docs/runbooks/*.md` | admin via PR |
| Research outputs | `docs/research/` | the session |
| Project dashboard (generated) | `project/dashboard.html` + `project/state.js` via `tools/gen-state.js` | never hand-edited |

## Structure

```
frontend/     React 18 + Vite            → frontend/AGENTS.md
backend/      Django 5.2 LTS + DRF + pgvector + LLM providers + social auth → backend/AGENTS.md
web-testing/  Playwright E2E runner + dashboard → web-testing/AGENTS.md
tools/        make targets + git/validation scripts
docs/         runbooks, decision records, research, reference
```

Production: Railway (API, Singapore) + Vercel (frontend) + Neon Postgres
(`user_data` app DB + `archi_data` buildings DB) + Cloudflare R2 + Redis.
Google login = auth-code flow (`VITE_GOOGLE_CLIENT_ID` + `GOOGLE_CLIENT_SECRET`).

## Conventions summary

- **Frontend**: consult `DESIGN.md` before any UI change; styling = `tokens.css`
  variables + co-located CSS Modules + inline style for layout; no Tailwind /
  MUI / styled-components; existing inline styles are load-bearing. Detail:
  `frontend/AGENTS.md`.
- **Backend**: Django 5.2 / Python 3.12; trailing slashes on every URL; psycopg 3
  pool; two `DATABASES` aliases; runtime DB role has no DDL (migrations are an
  operator step via `make migrate-local` / `make migrate-prod`). Detail:
  `backend/AGENTS.md`.
- **Both OSes**: Windows and macOS are supported. Run commands through `make`
  (`make dev`, `make backend`, `make frontend`, `make test-local`); never hand-type
  `python3` (a Store stub on Windows).
- **Language**: internal reasoning, docs, commits and PR text in English; replies
  to the user and user-facing copy in Korean unless asked otherwise.
