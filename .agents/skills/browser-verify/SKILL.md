---
name: browser-verify
description: Use when verifying runtime behavior in the local web app with the Codex in-app browser. Default replacement for the old app-test agent gate; runs in the main session, not as a sub-agent.
---

# browser-verify — Codex direct runtime verification

Use this skill after frontend/backend runtime changes, before publish, or when the
user asks to test the app. The main Codex session drives the in-app browser
directly; do not dispatch a browser-test agent by default.

## Modes

Pick the lightest mode that proves the changed surface.

- **SKIP** — pure docs/policy/config with no runtime surface.
- **SMOKE** — app boots, target page loads, no blank screen, no obvious console/network failures.
- **FEATURE-SCOPED** — SMOKE + concrete checklist for the changed feature.
- **FULL-SWIPE** — recommendation/swipe path regression: dev login, search, card load,
  swipe lifecycle, phase/progress behavior, results, error recovery, drift check.

Use FULL-SWIPE when changes touch:
- `backend/apps/recommendation/`
- `backend/config/settings.py` `RECOMMENDATION`
- session lifecycle, swipe APIs, card hydration, results flow
- `frontend/src/pages/SwipePage.jsx`, `LLMSearchPage.jsx`, or shared swipe state

## Preflight

1. Capture drift baseline:
   ```bash
   git fetch origin develop --quiet
   git rev-parse --short HEAD
   git rev-parse --short origin/develop
   ```
2. Check local servers:
   - frontend: `http://localhost:5174/`
   - backend: `http://localhost:8001/api/v1/auth/dev-login/`
3. If backend migrations changed, verify no unapplied migration:
   ```bash
   cd backend && python3 manage.py showmigrations 2>&1 | grep -E '\[ \]'
   ```
4. Open the in-app browser at the target URL.
5. Capture a console/network baseline. Any non-auth 4xx/5xx or console error on
   the changed surface is a failure unless already documented as pre-existing.

## Feature-Scoped Checklist

Write the checklist in chat before testing. Include:
- target URL(s)
- user action(s)
- expected visible state
- expected API call(s), when relevant
- failure states to inspect

Then test exactly that checklist with the in-app browser. Use screenshots only
when they help confirm layout, visual state, or failure evidence.

## FULL-SWIPE Checklist

1. Dev login succeeds and authenticated state is visible.
2. AI search creates/opens a session.
3. First card renders with real `canonical_bld_id`-backed data.
4. At least several like/dislike actions update cards without duplicates or blank state.
5. Progress/phase UI changes match `docs/algorithm.md` semantics.
6. Results page opens and shows expected recommendation data.
7. Error recovery path is sane when a request fails or times out.
8. No unexpected console errors or non-auth 4xx/5xx network responses.
9. End drift check: compare current `origin/develop` to preflight baseline.

## Failure Rules

- Blank app, stuck loading, missing critical data, uncaught console error, or
  non-auth 4xx/5xx on the changed path = FAIL.
- Unapplied migration = FAIL until migrated and backend restarted.
- `origin/develop` moved during verification = ABORTED drift, not code failure.
- Local dev server not running = report as NOT RUN, not PASS.

## Report Format

```text
BROWSER-VERIFY: PASS | FAIL | SKIPPED | NOT RUN | ABORTED
Mode: SMOKE | FEATURE-SCOPED | FULL-SWIPE
Target: <url(s)>
Checked:
- <short facts>
Issues:
- <none or exact issue>
Drift: clean | moved | not checked
```

