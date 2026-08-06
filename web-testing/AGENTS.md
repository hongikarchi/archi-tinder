# Web Testing — Agent Reference

Scope: this document covers (1) the standalone E2E visual test runner under
`web-testing/` and (2) the shared dev-login procedure used by both the runner
and the in-session `app-test` agent. The full `app-test` agent contract (modes,
gates, latency budgets, drift check, verdict shape) lives in
`.claude/agents/app-test.md` — that file is the source of truth for the agent;
the procedure in §"Dev Login" below is the only piece duplicated here for
convenience. Read this first before running any browser-driven test.

> **Naming note**: the agent was renamed from `web-tester` → `app-test` on
> 2026-04-28. Any historical reference to `web-tester` in this doc means the
> current `app-test` agent.

## Dev Login — Authenticating Without OAuth

The `app-test` agent must use dev-login to obtain a JWT for testing
authenticated flows. Google OAuth is not available in automated/headless
contexts, so dev-login is the only path.

**Endpoint:** `POST http://localhost:8001/api/v1/auth/dev-login/`
**Request body:** `{"secret": "<value of DEV_LOGIN_SECRET from backend/.env>"}`
**Availability:** DEBUG=True only. The URL itself is unroutable when
DEBUG=False.
**Rate limit:** 5 requests/minute (DevLoginThrottle).

**Response (200):**
```json
{
  "access": "<jwt_access_token>",
  "refresh": "<jwt_refresh_token>",
  "user": {
    "user_id": 1,
    "display_name": "Test User",
    "avatar_url": null,
    "providers": []
  }
}
```

If `DEV_LOGIN_SECRET` is not set in `backend/.env`, the endpoint returns 404.

**`app-test` agent — hard FAIL on 404** (per `.claude/agents/app-test.md`
preflight, dev-login step): deep verification cannot proceed without auth, so
the agent returns `APP-TEST: FAIL` (`dev-login unavailable`). There is no
"skip authenticated flows" fallback for the agent.

**Standalone runner** (`web-testing/run.py`) — also requires
`DEV_LOGIN_SECRET`; the runner exits with a clear error if the secret is
missing (no silent skip).

### Injecting tokens into the browser

After a successful dev-login curl, inject tokens via `browser_evaluate`:
```js
localStorage.setItem('archithon_access', '<access_token>')
localStorage.setItem('archithon_refresh', '<refresh_token>')
sessionStorage.setItem('archithon_user', '<user.user_id from response>')
```
Then reload the page. The app reads these keys on mount to restore auth state.

**localStorage keys:**
- `archithon_access` — JWT access token (1hr expiry)
- `archithon_refresh` — JWT refresh token (30d expiry)

**sessionStorage keys:**
- `archithon_user` — user ID (integer, from `response.user.user_id`)

### Debug overlay

Enable richer test diagnostics by setting debug mode before reload:
```js
localStorage.setItem('__debugMode', 'true')
```
This activates `DebugOverlay.jsx`, a fixed panel showing JWT expiry, last
API call (method/URL/status/latency), current session ID, swipe progress,
user ID. The overlay is read-only (`pointerEvents: 'none'`) and survives
page reloads. `app-test` should screenshot after enabling it to confirm
login state.

### Django admin

- **URL:** `http://localhost:8001/admin/`
- **Credentials:** username `admin`, password `admin1234` (set by `make setup`)
- **Availability:** DEBUG=True only.

Useful for inspecting user accounts, projects, and social accounts during
testing.

## Authenticated flows the agent should test

Once logged in via dev-login:

1. **Home / LLM Search** — AI search input visible, type query, submit.
2. **Swipe page** — session creation works, cards load, swipe gestures function.
3. **Favorites page** — project folders render, liked buildings display.
4. **Persona report** — "Generate Persona Report" button visible when likes exist.
5. **API connectivity** — no 401 errors on authenticated endpoints.

> **Authoritative procedure**: the `app-test` agent runs its own dev-login
> Step (B1d) as part of FULL or FEATURE-SCOPED mode — see
> `.claude/agents/app-test.md`. The `skip_login` flag from the old `web-tester`
> contract is **removed** as of the 2026-04-28 rename; the orchestrator does
> not pass any auth-skip flag and the agent has no auth-skip branch.

---

## E2E Visual Test Runner (`web-testing/`)

Standalone Playwright-based runner. Generates persona-driven test scenarios,
runs them against local dev servers, captures screenshots/timing/errors at
every step, and serves a local dashboard for visual review.

### Layout

```
web-testing/
├── research/persona.py      # PersonaProfile dataclass + template/LLM generation
├── research/scenarios.py    # TestScenario + keyword-overlap swipe decisions
├── runner/runner.py         # Playwright E2E orchestration (sync API)
├── runner/collector.py      # StepRecord, ApiCallRecord, ErrorRecord, Collector
├── runner/reporter.py       # report.json with summary + bottleneck classification
├── runner/feedback.py       # feedback.json with endpoint→source file mapping
├── dashboard/               # Static HTML/JS/CSS dashboard (no build step)
├── reports/                 # Output dir (gitignored)
├── run.py                   # CLI entry point
└── requirements.txt         # playwright, google-generativeai
```

### Running

```bash
# Install deps (one-time)
pip install -r web-testing/requirements.txt
python -m playwright install chromium

# Single persona, template mode
python web-testing/run.py

# 3 personas with LLM-generated profiles
python web-testing/run.py --personas 3 --mode llm

# Dashboard only
python web-testing/run.py --dashboard-only

# Auto-fix mode (structured feedback to stdout)
python web-testing/run.py --auto-fix
```

### Prerequisites

- Frontend dev server on `http://localhost:5174`
- Backend dev server on `http://localhost:8001`
- `DEV_LOGIN_SECRET` set in `backend/.env`

### Output

- `web-testing/reports/{run_id}/report.json` — full test report
- `web-testing/reports/{run_id}/feedback.json` — orchestrator-consumable feedback
- `web-testing/reports/{run_id}/screenshots/` — step screenshots
- `web-testing/dashboard/data/latest/` — symlinked latest report for dashboard

## `app-test` modes — FULL vs FEATURE-SCOPED (2026-05-22)

`app-test` runs in one of two modes. The caller (orchestrator or the
`git-publish` skill via the pre-push gate) chooses the mode; the default is
FULL.

| Mode | When to run | Behavior |
|---|---|---|
| **FULL** (default) | Recommendation / swipe path touched — `backend/apps/recommendation/**`, RECOMMENDATION dict in `backend/config/settings.py`, session lifecycle, `SwipePage.jsx` / `LLMSearchPage.jsx`, swipe / session logic in `App.jsx`. Always required pre-deploy (Mode 3). | 3 personas × 25 swipes × 3-run TTFC p50, spec-aligned latency budgets (Brutalist / Sustainable Korean TTFC < 4s; Bare Query < 5s; per-swipe outer < 1500 ms / backend < 1000 ms), edge-case coverage (refresh-resume, action card, network failure), zero-tolerance console/network error gates. No retries on flake. |
| **FEATURE-SCOPED** | Changes that do not touch the recommendation / swipe path — e.g. profile, theme/font, boards, social, accounts, settings UI. | Preflight (dev-login, migrations, console baseline) + caller-supplied feature checklist + light regression smoke (1 AI search, ~5 swipes, no latency gate). The dispatch MUST include a feature-verification checklist or the agent fails the run. |

Both modes end with an `origin/develop` drift check. The legacy
"fast inner-loop / strict /review" split is **superseded** by these two modes
as of 2026-05-22 — see `.claude/agents/app-test.md` for the full contract.
There is no `/review` slash command — per CLAUDE.md `## Workflow — one
session + sub-agents + skills`, the repo has no slash commands; reviews run
via the `code-review` agent and pre-push verification via this `app-test`
agent.
