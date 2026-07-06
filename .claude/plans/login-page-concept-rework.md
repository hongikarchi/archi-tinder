# Login Page Concept Rework (LOGIN-REWORK-1)

**Date:** 2026-07-07
**Branch:** feature/claude-login-rework
**Scope:** frontend-only (LoginPage.jsx + cardLanguage.js + i18n locales.js + index.css). No backend changes.

## User-reported issues (7) + diagnosis

1. **ID duplicate-check "feels buggy"** — Backend check-handle API is CORRECT (verified live: existing `dev_test` → taken, new ID → available, DB uniqueness via `validate_handle_value` line 174-178). The problem is FRONTEND UX: user must press a separate 중복확인 button and see "사용 가능" before Continue enables; Korean IME composition mid-state + the extra manual step read as a bug. → Rework to debounced auto-check on typing (no separate button), inline availability state, clearer feedback.

2. **First screen should induce swiping** — `IntroOverlay` modal (`INTRO_SHOW_ONCE=false`) covers the swipe card + typing every entry. → **DECISION: fold the modal into the first card.** Remove the separate `IntroOverlay`. First `choice` card itself teaches swipe (typing question + animated L/R hints/arrows), acting as the tutorial.

3. **Text hierarchy / font off** — Wordmark `ARCHIBE` only 12px (cardLanguage.js line 60), question text uses MONO font not in DESIGN.md (self-introduced, violates §2.5a single-font). → **DECISION: implement first, eyeball on local dev (:5175), micro-tune.** Direction: enlarge wordmark to logo-grade (20-28px, strong letter-spacing), move question/label text off MONO toward base IBM Plex Sans KR; MONO may survive only as intentional business-card meta-label accent (@id, JOINED) — decide visually.

4. **Typing feel gone** — `useTypedLine` hook exists (24ms interval) and works, but IntroOverlay hid it. Fixing issue 2 restores visibility. Ensure each step's question types out on entry, cursor blink retained.

5. **Remove unnecessary copy** — Kill "명함에 새길 이름이에요" (credentials.title-ish) and dead eyebrows like "새 계정" / "첫 카드" that add noise. Keep only copy that tells the user what to do.

6. **Cards should feel "waiting behind", not re-rendered** — Currently only decorative faux-depth cards (LoginPage line 507-526). → **DECISION: real deck pre-render + step-history pop back-nav.** Build an actual card deck (choice→credentials→profile→consent as stacked cards, next card pre-rendered behind). Swipe flies the front card off, back card surfaces. Back = step-history stack pop (previous card returns to top).

7. **Dev login broken** — FALSE ALARM. Endpoint returns 200 + tokens (verified live). Failed only because backend died on first `python manage.py` (global python, no Django; venv is at `backend/.venv`). Now running via `.venv/Scripts/python.exe`. No code change needed.

## Overarching goal
A login page that focuses the user: immediately clear what to do, and telegraphs the site's swipe-to-discover-taste concept + business-card UI/UX. Concept-faithful.

## Confirmed decisions
- **Issue 6:** real deck pre-render + step-history stack for back-nav.
- **Issue 3:** implement then eyeball-tune font/hierarchy (logo bigger, MONO trimmed).
- **Issue 2:** fold Intro modal into the first card (remove separate `IntroOverlay`).

## Delegation
Frontend rework → `orchestrate` skill (front-maker). Session owns decisions + review + publish gate. STOP at commit; publish only on explicit trigger.
