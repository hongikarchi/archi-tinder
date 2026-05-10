# Web Testing — Agent Reference

Scope: this document covers the `web-tester` agent (in-session `/review` Part B
+ orchestrator inner loop) and the standalone E2E visual test runner under
`web-testing/`. Read this first before running any browser-driven test.

## Dev Login — Authenticating Without OAuth

The `web-tester` agent must use dev-login to obtain a JWT for testing
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
In that case, skip authenticated flows and test page-load only.

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
page reloads. `web-tester` should screenshot after enabling it to confirm
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

### Important: orchestrator must NOT pass `skip_login`

The orchestrator must NOT tell `web-tester` to skip login. Dev-login exists
specifically for automated testing. Let `web-tester` run its Step 0
(dev-login) before visual tests.

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

## Strict vs fast mode

| Mode | Used by | Behavior |
|---|---|---|
| **Fast (inner loop)** | orchestrator pipeline | 1 persona, ≥10 swipes, no latency assertion, retries on flake, console errors reported but not failed. Avoids blocking iteration. |
| **Strict (Part B of /review)** | review terminal | spec-aligned latency budgets (TTFC < 4s / 5s bare; per-swipe p95 < 700 ms), 3 personas × ≥25 swipes, zero-tolerance error gates, edge-case coverage. No retries. |

The two are complementary; strict mode does NOT replace the fast inner-loop
`web-tester`. See `.claude/commands/review.md` for the full Part B spec.
