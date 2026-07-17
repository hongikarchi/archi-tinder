# Main Service Web Test Plan

Target release: `main@5b57320` (`deploy: batch #175->#217 - profile IA + auth login + avatar + ALGO-QCARD + Discovery v3.1/v3.2`)

Scope: production-like web testing against the deployed main service. This plan describes what has been implemented, how users should exercise it, and what counts as pass/fail. It is written for manual QA and for a future Playwright runner update.

## Test Setup

Use the deployed frontend URL for `main` and the production API configured by `VITE_API_BASE_URL`.

Production does not expose `/api/v1/auth/dev-login/` because that endpoint is DEBUG-only. Test auth must use one of:

- Guest onboarding from `/login`
- Handle/password registration and login
- Google OAuth, only if `VITE_GOOGLE_CLIENT_ID` is configured

Create disposable QA accounts only. Use handles such as `qa_main_YYYYMMDD_HHMM`. Avoid real personal data. After tests, delete created boards where the UI allows it.

Global fail gates:

- Blank page, uncaught exception, or app crash at any route.
- Unexpected 401/403/404/500 during a normal happy path.
- Any card, board, profile, report, or settings save appears successful in UI but does not persist after refresh.
- Private boards visible to non-owners.
- Discovery or Taste flow cannot progress because deck becomes permanently empty, stuck, or duplicated.
- Main mobile viewport (`390x844`) or desktop viewport (`1440x900`) has overlapping unreadable UI.

Global warning gates:

- Initial cold Discovery, AI search, or session creation takes more than 30s but recovers.
- Swipe response regularly feels above 1.5s after warm-up.
- Image skeletons remain longer than 8s while API already returned usable image URLs.
- Non-critical LLM image/report generation fails but text report/results remain usable.

## Implemented Features

### 1. Auth And Onboarding

Implemented:

- Swipe-style `/login` onboarding.
- New guest profile creation with display name, objective role, optional job role/affiliation, consent.
- Returning user flow with Google OAuth where configured.
- Handle/password register and login.
- Guest-to-verified promotion via Google from verify gate.
- JWT storage, refresh, logout, and session-expired handling.

Primary scenario:

1. Open deployed app.
2. Confirm unauthenticated user lands on `/login`.
3. Right-swipe first card for new user path.
4. Enter display name, choose role/objective, continue.
5. Consent and right-swipe final consent card.
6. Confirm app lands on `/discovery`.
7. Logout from profile/header.
8. Register handle/password account, logout, then login with same credentials.

Success:

- Guest creation returns authenticated app state without dev-login.
- Access/refresh tokens exist in browser storage after auth.
- User profile name/role survives refresh.
- Logout clears session and returns to `/login`.
- Handle/password account can log in again.

Failure:

- Guest can be created without consent.
- Login screen gets stuck after swipe animation.
- Auth succeeds but `/discovery` redirects back to `/login`.
- Token refresh loop causes repeated logout or console/network errors.

### 2. Discovery Feed

Implemented:

- `/discovery` swipe deck with 10-card chunks.
- Right swipe records Discovery like; left swipe records pass.
- User taste state labels: cold, single, multi.
- Prefetch at low deck count, sessionStorage deck cache, seen-card shake on reappearance.
- 10-like trigger card that can promote Discovery draft into Taste analysis.
- 50-like hard cap forcing Taste handoff.
- Discovery likes stored in profile-level liked building list.

Primary scenario:

1. Start from `/discovery`.
2. Swipe at least 12 cards using both mouse/touch gestures and arrow keys.
3. Like at least 10 cards.
4. Confirm progress reaches `10/10` then trigger card appears.
5. Left-swipe trigger card once, verify Discovery continues.
6. Continue until another trigger or hard cap path is reachable.
7. Right-swipe trigger card to promote to Taste.

Success:

- First card image and metadata render.
- Right swipe increments progress; left swipe does not.
- `/api/v1/discovery/feedback/` succeeds for likes and passes.
- Trigger card appears after 10 likes, not before.
- Left-swipe trigger dismisses it without losing deck.
- Right-swipe trigger calls `/api/v1/discovery/promote-to-taste/` and navigates to `/swipe`.
- No duplicate top card appears immediately after a swipe.

Failure:

- Progress count gets stuck despite successful feedback API.
- Trigger card repeats endlessly after left dismiss.
- Promote starts a Taste session with missing/undefined building ID.
- Deck empties while API still has cards.

### 3. New Project And AI Search

Implemented:

- `/new` project setup with name, area range, and visibility.
- `/search` conversational AI query parsing.
- Preset query chips.
- Multi-turn clarification support.
- Structured filters, filter priority, visual description, image focus, and result preview strip.
- Existing project chat persistence for update mode.

Primary scenario:

1. From tab bar or Discovery empty CTA, open `/new`.
2. Enter project name.
3. Set visibility to `public`, then back to `private`.
4. Adjust area range, reset it.
5. Continue to `/search`.
6. Submit: `Modern museum in Japan with concrete and calm atmosphere`.
7. If clarification appears, answer naturally.
8. Confirm result strip and filter chips appear.
9. Click `Start swiping`.

Success:

- Cannot continue from `/new` without project name.
- `/api/v1/parse-query/` returns either clarification or final results.
- Final search state includes building previews and `Start swiping - N`.
- Starting creates `/api/v1/analysis/sessions/` and navigates to `/swipe`.
- Project visibility setting persists after session/project creation.

Failure:

- AI message says results found but result strip is empty.
- Search state disappears on refresh before starting.
- Korean/CJK query is falsely rejected by byte limit.
- Start button appears with zero usable results.

### 4. Taste Swipe Session

Implemented:

- `/swipe` Taste analysis deck.
- Session creation and refresh-resume.
- Optimistic card swap using `next_image`, `prefetch_image`, `prefetch_image_2`.
- Client buffer IDs to prevent duplicate cards.
- Swipe latency telemetry.
- Like/dislike writes with idempotency key.
- First left-swipe confirmation tutorial.
- Confidence/progress bar and finish floor after target swipes.
- Keep exploring after completion when backend allows.
- In-session question cards: right = option A, left = option B, buttons as fallback.

Primary scenario:

1. Enter `/swipe` from Discovery promotion or AI search.
2. Dismiss tutorial if shown.
3. Swipe 15-25 cards with mixed likes/dislikes.
4. On first left swipe, confirm skip tutorial, then test cancel path in another run.
5. When question card appears, choose A once and B once in separate runs.
6. Refresh during active session and confirm same or valid next card resumes.
7. Continue until `Finish & View Report` or completed state appears.

Success:

- Every swipe sends `/api/v1/analysis/sessions/{id}/swipes/`.
- Like/dislike counts and phase/progress update.
- No same card repeats from client prefetch queue.
- Question card blocks normal card swipes until answered.
- A/B answer posts `/question-responses/`; when backend flushes, stale prefetch cards disappear.
- Refresh resumes current session without creating duplicate project/session.
- Finish button is disabled while swipe request is pending.

Failure:

- Card disappears permanently after swipe.
- Swipe API succeeds but UI keeps previous card.
- Question card options invert user intent versus text.
- Finish button opens report before last swipe write settles.
- Refresh restarts taste from zero without explicit new-session action.

### 5. Results, Bookmarks, And Report

Implemented:

- `/result/:sessionId` persona report header.
- Liked building carousel.
- Top-K recommendation grid, lazy-loaded up to 50.
- Bookmark toggle on result cards.
- Building detail navigation with bookmark state reconciliation.
- Backend report generation on completion.

Primary scenario:

1. Complete Taste flow.
2. Open persona report.
3. Verify persona type, one-liner, liked buildings, top recommendations.
4. Bookmark rank 1 and rank 8.
5. Open bookmarked building detail, toggle bookmark there, go back.
6. Save report/board and return to `/user/me`.

Success:

- `/api/v1/analysis/sessions/{id}/result/` returns liked and predicted images.
- Top cards show image, title, rank, metadata.
- Bookmark star updates optimistically and persists after refresh.
- Detail page bookmark changes reconcile back to result grid.
- Report page remains usable if persona image generation is slow or fails.

Failure:

- Results route says invalid session for a session just completed.
- Bookmarked state differs between result grid, building detail, and board.
- Saved IDs are duplicated after repeated toggles.

### 6. User Profile, Boards, And Liked Buildings

Implemented:

- `/user/me` and `/user/:userId`.
- Profile hero, avatar upload, display name/handle/role/affiliation/bio/external links.
- Board grid with pagination.
- Board public/private visibility.
- Owner-only board edit, delete, bulk visibility, bulk delete.
- Follow/unfollow user, followers/following lists.
- Liked Projects page from Discovery right swipes.
- Saved Studios tab from architect follows.

Primary scenario:

1. Open `/user/me`.
2. Confirm profile hero and board count.
3. Open `Liked Projects`; verify Discovery likes appear.
4. Return, open settings profile edit, update role/affiliation/bio, save.
5. Upload avatar if test environment allows safe small image.
6. Create or use at least two boards, toggle public/private, then refresh.
7. Enter select mode, bulk-toggle visibility, then bulk-delete a disposable board.

Success:

- Profile fields persist after refresh and relogin.
- Discovery liked buildings appear in `/liked-projects`.
- Board visibility updates optimistically and persists.
- Bulk action affects selected boards only.
- Failed board action shows inline error and reverts UI.
- Non-owner profile shows follow/share, not owner edit controls.

Failure:

- Private board appears on another user's profile.
- Board delete removes wrong board after pagination.
- Avatar upload succeeds locally but image URL is broken after refresh.
- Follow count changes without server persistence.

### 7. Board Detail And Board Report

Implemented:

- `/board/:boardId` detail with owner/visibility gates.
- Board name edit.
- Board reaction (`Love this`) for non-owner public boards.
- Building tiles and saved-building tiles.
- Recommended architects section.
- `/board/:boardId/report` persona report page.
- Radar chart and spectrum bars for axis scores: form, materiality, scale, energy, tradition.
- Persona image generation/regeneration.

Primary scenario:

1. Open a board from `/user/me`.
2. Rename board, refresh, verify name persists.
3. Open board report if report exists.
4. Verify radar chart and spectrum bars render.
5. Generate or regenerate persona image.
6. In a second account, open public board URL and react/unreact.
7. Flip board private, verify second account can no longer open or react.

Success:

- Owner can edit board name and saved building set.
- Non-owner can view public board and react.
- Private board returns blocked/not found behavior for non-owner.
- Board report shows persona text, dominant tags, radar, spectrum, image area.
- Axis score visualization uses stored `axis_scores` or safe zero defaults.

Failure:

- `disliked_ids` appears anywhere in board API/UI.
- Non-owner can mutate board name/visibility.
- Radar chart fails when some axis score is missing.
- React count goes negative or double-increments on repeated clicks.

### 8. Building Detail And Save-To-Board

Implemented:

- `/buildings/:buildingId` detail from result, board, liked, and architect surfaces.
- Metadata cards, source link, visual description, atmosphere.
- Gallery split by photos/drawings when metadata exists.
- Bookmark when opened from recommendation result.
- Save-to-board modal and new board creation from detail.
- Guest verify gate when board limit requires promotion.

Primary scenario:

1. Open building detail from result grid.
2. Verify title, architect, country/city/year/program/style/material metadata.
3. Switch gallery filters: All, Photos, Drawings.
4. Click source link in new tab if present.
5. Save to an existing board.
6. Create a new board from save modal, save building, then find board in profile.

Success:

- Invalid building ID shows error state, not crash.
- Valid building loads through `/api/v1/images/batch/`.
- Gallery filter buttons disable empty categories.
- Save modal lists boards and creates new private board.
- Saved building appears in chosen board after refresh.

Failure:

- Detail page cannot load a building that appeared in result/Discovery.
- Save-to-board silently fails.
- Modal creates board but does not save selected building.

### 9. Architect And Firm Profiles

Implemented:

- `/architects/:architectId` profile.
- Follow/unfollow architect.
- Website/contact/share actions when data exists.
- Architect building grid.
- `/office/:officeId` firm profile for Office detail compatibility.
- User Saved Studios tab derives from followed architects.

Primary scenario:

1. Open architect from board recommendations or direct known `arch_XXXXXX`.
2. Follow architect.
3. Open `/user/me`, switch to Studios tab, verify architect appears.
4. Return to architect, unfollow, verify Studios tab updates.
5. Open website/contact only if buttons are visible.

Success:

- Architect profile loads name, stats, description, building grid.
- Follow state persists after refresh.
- Saved Studios contains followed architect.
- Building cards navigate to valid building detail.

Failure:

- Follow count changes but follow state resets after refresh.
- Website/contact opens unsafe or malformed URL/email.
- Architect building IDs are not `canonical_bld_id`.

### 10. Settings And Account

Implemented:

- `/settings` root list.
- Profile edit screen.
- Account screen: handle, password, Google email link/verification.
- Notifications screen.
- Appearance screen: theme, font, language.
- Server persistence for theme/font/language.

Primary scenario:

1. Open `/settings`.
2. Change theme to each option: GitHub Light, GitHub Dark, Ayu Light, SynthWave '84.
3. Toggle font.
4. Toggle language Korean/English.
5. Save a unique handle.
6. Change password for handle/password account, logout, login with new password.
7. Visit notifications screen and toggle available controls.

Success:

- Appearance changes apply immediately.
- Theme/font/language persist after refresh and relogin.
- Handle validation rejects invalid handles and accepts unique valid handle.
- Password change swaps tokens; next refresh does not log user out.

Failure:

- Appearance save works in UI but reverts after refresh.
- Password change succeeds but current session becomes invalid immediately.
- Invalid handle persists.

## Cross-Scenario Regression Checks

Run these after core flows:

- Mobile viewport `390x844`: login, Discovery, Swipe, Profile, Board detail, Settings.
- Desktop viewport `1440x900`: profile grid, board detail, building detail, results grid.
- Hard refresh on: `/discovery`, `/swipe`, `/result/:sessionId`, `/user/me`, `/board/:id`, `/settings/appearance`.
- Browser back/forward from building detail to result and board detail.
- Expired/cleared token path: remove access token, reload, verify refresh or logout behavior.
- Network slow path: throttle to Slow 3G for Discovery and Swipe initial load; skeletons must remain coherent.

## Performance Budgets

Use these as web-test warnings, not automatic hard fails unless repeated.

- App shell first meaningful render: under 3s warm, under 8s cold.
- Discovery first card: under 8s warm, under 30s cold.
- AI parse query: under 60s hard timeout; warning above 15s.
- Session create first Taste card: under 30s hard timeout; warning above 10s.
- Swipe API: target p50 under 500ms and p95 under 1500ms after warm-up.
- Result fetch: under 8s.
- Persona image generation: non-blocking; text report remains usable if image fails.

## Current Automation Gap

Existing `web-testing/runner.py` is still local-dev oriented:

- hard-coded `FRONTEND_URL = http://localhost:5174`
- hard-coded `BACKEND_URL = http://localhost:8001`
- requires DEBUG-only `/api/v1/auth/dev-login/`

For deployed main testing, update or wrap the runner before relying on it:

- accept `FRONTEND_URL` and `API_BASE_URL` from environment;
- create/login a test user through UI or handle/password API, not dev-login;
- add scenarios for Discovery promotion, question cards, profile/board settings, board report axis charts, and architect follows;
- keep screenshots, network calls, console errors, and route URLs per step.

Recommended minimum production smoke:

1. Guest onboarding -> Discovery -> 10 likes -> promote -> 12 Taste swipes -> result.
2. Handle/password register -> new project -> AI search -> swipe -> bookmark -> board detail/report.
3. Profile/settings -> edit profile -> theme/font/language -> public board -> second-account reaction/follow.
