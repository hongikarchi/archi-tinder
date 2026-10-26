# Persona report redesign — execution plan

**Issue:** #445 (FULL-REPORT-UI-1) · **Branch:** `feature/claude-persona-report-redesign` · **Design record:** `docs/decisions/2026-10-22-persona-report-redesign.md` · **Mock (source of truth for look & behaviour):** `C:\Users\yello\archi-tinder-mock\persona-report-all.html` (outside the repo; `python -m http.server 5199` in that folder)

> **한국어 요약** — 확정된 시연(진입 5개 × 상황)을 코드로 옮기는 실행 계획. 핵심은 ① 리포트 페이지를
> 하나의 공용 컴포넌트로 통합(`/board/:id/report` 유지, 저장 후 도착 화면도 동일), ② 결과 카드 3장,
> ③ 로딩 문구 구분(만드는/불러오는), ④ 이미지 재생성(소유자 모든 화면) + 리포트 재생성(맨 아래 링크).
> 디자인 기준 밖의 값은 `DESIGN.md` §11에 예외로 기록되어 있고 승인은 후속. 이 계획은 **publish 승인을
> 포함하지 않는다** (커밋까지만, push는 사용자 트리거 필요).

## Rules for the workers

- Read `DESIGN.md` first (§2.2 scale, §3.5/§3.5a motion, §8.8 loading, §8.9 error/empty, §8.10 modal, §8.11 toast, §11 pending exceptions).
- The **mock decides** look, copy and behaviour. Where this plan and the mock disagree, the mock wins; flag it in the PR.
- Values listed in `DESIGN.md` §11 E1–E10 are **intentionally off-scale**. Implement them as in the mock, keep them in one place (CSS Module / a small constants module) so they can be promoted to tokens later, and do **not** "fix" them to the scale.
- All user-facing strings through `i18n/locales.js` (ko + en). Copy is listed below.
- Frontend: tokens + co-located CSS Modules + inline layout; no new styling libs. Reuse existing `EmptyState`, `Skeleton`, `Modal`, `PageBackButton`, `PageTopControls`, `photoCardShell` where they fit — check first, do not duplicate.
- Backend: raw SQL / `canonical_bld_id` / `is_publishable` rules in `AGENTS.md` still apply. No migration is expected.

## Work packages (delegate via `orchestrate` → `feature` workflow)

### WP1 — Shared report page (FE) — **do first**
Merge `components/PersonaReport.jsx` + `pages/BoardReportPage.jsx` into one report-page component used by:
(a) `/board/:boardId/report` (route unchanged), (b) the post-save landing after the result cards / re-entry banner.

Sections, top → bottom: meta row · persona (label, name 24px, one-liner 14px semibold, image 240px, description 13px) · pattern analysis ("왜 이런 결과가 나왔나요", paragraph 13px, tags 11px) · taste analysis (`TasteSpectrum` restyled; legacy notice + "재생성하기 ↓" link when `isLegacyAxisScores`) · liked buildings (118px cards, horizontal scroll) · recommendations (rank 1 large 4:3 card, rest 118px cards horizontal) · footer.
Footer: **owner** → underlined text link "리포트 재생성" (no border/background/icon); **viewer** → "더 볼 게 없어요". Viewers see liked buildings **and recommendations** (decision 2).
Owner-only: image refresh button (top-right of image, 30px circle). Viewer: none.
Reveal-on-scroll motion per `DESIGN.md` §3.5a (+ `prefers-reduced-motion`).

States (all inside the same page): loading skeleton (label per WP1 table), generation failure, no report, board not found / private, image generating / failed (neutral box + outline "다시 시도", owner only) / none (gradient face with persona name).

### WP2 — Image & report regeneration (FE, small BE check)
- Image refresh → confirm dialog → `generateReportImage(id, {regenerate:true})` via the existing `reportImageJobs` store. While generating: skeleton in the image slot, refresh still visible; tapping it again → toast "재생성 중입니다." Failure: small text "재생성에 실패하였습니다." next to the refresh button, **previous image kept**. Server returns 202 `in_progress` for duplicates (waits ≤25 s) — map it to the same "in progress" state.
- Report link → confirm dialog → `generateReport(id, {regenerate:true})`. Success: replace report text (+ `axis_scores`), toast "리포트를 재생성했어요", keep scroll position. Failure: small text under the link. **Image is not touched** (server only writes `final_report`/`axis_scores`).
- Image refresh must be present for the owner on: result card 1, the post-save landing, the report page. Never for viewers.

### WP3 — Result cards (FE)
`ResultsPage` → 3 horizontally swipeable cards, same box as the Swipe card area (20px side margin, 560px tall, scroll-snap, peek of next card, dots, mouse drag). Card 1 persona (name, one-liner, description, image + refresh), card 2 pattern + taste analysis, card 3 closing (thumbnail, "분석이 끝났어요", persona name, copy, "저장하고 프로필로"). Liked buildings / recommendations are **not** shown here.
Failure card ("리포트를 불러오지 못했어요" · 다시 시도) and zero-likes card ("나의 건축 페르소나" · **탐색 시작하기**) use the same card box.
Saving: existing `SaveBoardModal` → navigate to the shared report page.

### WP4 — Entry points (FE)
- `SwipePage`: "Finish & View Report →" fixed at the bottom, same width/alignment as the `TabBar` (derive the real width — the mock's 200px is an assumption), 44px pill. Shows the "만드는 중" skeleton card while the report is generated.
- `App.jsx` re-entry banner → card style (thumbnail · "이전에 완성된 리포트가 있어요" · persona name · [삭제] text button · [저장하고 프로필로]); save → `SaveBoardModal` → shared report page; delete → toast "리포트를 삭제했어요".
- `BoardDetailPage`: cover card (persona image, scrim, name 24px, meta), one-liner, primary pill "페르소나 리포트 보기" (text only, no icon); owner: edit + share circle buttons; viewer: "♥ 좋아요" pill. No report → no report button.

### WP5 — Backend check (BE)
Verify the board-detail payload used by the report page includes: `final_report`, `axis_scores`, `report_image` (+ mime), liked buildings, recommended buildings, owner info, and a way to tell "report exists" (for "불러오는/만드는" copy). Extend only what is missing; add tests. Confirm image regeneration failure keeps the stored image (already true in `ProjectReportImageView`) and add a regression test if absent.

### WP6 — Docs, tests
- `DESIGN.md` already updated (§3.5a, §9 row, §11 E1–E10) — keep in sync if values change.
- Update `web-testing` selectors touched by the new structure.
- `docs/design-preview/pages/persona-report.html` is **out of scope**.

## Copy (ko / en)

| Key idea | ko | en |
|---|---|---|
| loading (fetch) | 리포트를 불러오는 중이에요 | Loading the report |
| loading (generate) | 리포트를 만드는 중이에요 | Creating your report |
| image generating | 이미지 생성 중 | Generating image |
| image regen confirm | 이미지를 재생성하시겠습니까? / 현재 이미지가 새 이미지로 바뀌어요. | Regenerate the image? / The current image will be replaced. |
| image regen busy / fail | 재생성 중입니다. / 재생성에 실패하였습니다. | Regenerating now. / Regeneration failed. |
| report regen confirm | 리포트를 재생성하시겠습니까? / 분석 문구가 새로 만들어져요. 이미지는 그대로 유지돼요. (legacy: …취향 분석도 최신 방식으로 바뀌어요…) | Regenerate the report? / The analysis text will be rewritten. The image stays as it is. |
| report regen link / busy / done | 리포트 재생성 / 재생성 중 / 리포트를 재생성했어요 | Regenerate report / Regenerating / Report regenerated |
| legacy link | 재생성하기 ↓ | Regenerate ↓ |
| zero likes CTA | 탐색 시작하기 | Start exploring |
| result load failed | 리포트를 불러오지 못했어요 / 잠시 후 다시 시도해 주세요. | Couldn't load the report / Please try again in a moment. |
| board unavailable | 볼 수 없는 보드예요 / 삭제되었거나 비공개로 바뀐 보드일 수 있어요. | This board isn't available / It may have been deleted or made private. |
| re-entry banner | 이전에 완성된 리포트가 있어요 · 저장 전 / 저장하고 프로필로 / 삭제 | You have a completed report · Not saved yet / Save and go to profile / Delete |
| "why" label | 왜 이런 결과가 나왔나요 | Why this result |
Existing keys (`persona.*`, `results.*`, `board.*`) are reused where the text is unchanged; the legacy sentence stays as is ("…최신 분석…").

## Acceptance checks (per entry point — mirror the mock's sequences)

1. **스와이프 종료:** Finish → "만드는 중" → 3 cards → save sheet → report page; failure → retry; zero likes → "탐색 시작하기".
2. **재진입:** banner card → save → report page; delete → toast.
3. **내 프로필 → 보드 → 리포트:** "불러오는 중" → page; image refresh (confirm / busy toast / failure keeps image); report link; image failure → retry.
4. **발견 → 타인:** page with recommendations, **no** refresh / regenerate controls; private-after-the-fact → "볼 수 없는 보드예요".
5. **공유 링크:** fetch → page; owner without report → "불러오는" then "만드는" → page; generation failure → retry; no report; not found.
6. Legacy `axis_scores`: notice + "재생성하기 ↓" scrolls to and highlights the report link; after regeneration the notice disappears.
7. `prefers-reduced-motion`: everything visible immediately. ko/en parity. Light + dark theme.
8. `./tools/front-validate.sh` (eslint + build), `make test-local`, then `app-test` (FULL mode — swipe path changes) and the `origin/develop` drift check.

## Sequencing

One issue, two reviewable PRs (both `Closes`/`Refs #445`):
1. **PR A — report page core:** WP1 + WP2 + WP5 + board detail (WP4 last bullet).
2. **PR B — result cards & entries:** WP3 + the first two WP4 bullets.
Each PR: build+review via the `feature` workflow → `commitReady` → `git-commit` → `app-test`. **Stop after the commit**; push/PR need the user's trigger words (`AGENTS.md` § Working and publishing).
