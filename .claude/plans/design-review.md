# DESIGN-REVIEW-1 — mobile UI/UX design review + upgrade

## 한국어 요약
- 목표: 모바일(390px) 기준 디자인 점검 → 우선순위 리포트 → PR 묶음으로 개선.
- 도구: impeccable(주력, 자동 검사 + critique/audit/adapt) + emil skills(모바일·제스처·모션). ui-ux-pro-max·Vercel 가이드는 참고만.
- 설치: 스킬은 PC 전체(global), 자동 hook 끔, PRODUCT.md만 repo 커밋.
- 작업 위치: 별도 clone `2607-Archibe/make_web-design` (main checkout은 다른 세션 사용 중). dev 서버 5174는 공유, 재시작 안 함.
- 개선(코드 수정)은 makers 위임. TS 전환 #502는 2026-11-21 develop 머지 완료 → 충돌 차단 해제.

## Context
User request 2026-11-21: design-side (not code-side) frontend review focused on phones; adopt popular
Claude design skills (AI-slop check, layout/grid, design-system/token health, buttons, transitions, fonts)
and Instagram references (@ui_motion_prompts, @uxwoodytips). Tool choice by adoption (stars/downloads):
impeccable 114k★ / 1.37M npm/mo; emilkowalski/skills 58k★; ui-ux-pro-max 152k★ (reference only);
vercel web-design-guidelines (reference only). Parallel sessions: AWS server migration (backend/infra).

## Phase 0 — setup (DONE 2026-11-21)
- `npx impeccable install --providers=claude --global --no-hooks` → `~/.claude/skills/impeccable` + 5 agents.
  Live mode banned (spawns agents with bypassPermissions).
- `npx skills add emilkowalski/skills -g -a claude-code` → 19 skills in `~/.claude/skills/`.
- Clone + branch `feature/claude-design-review` off origin/develop e6c410b.
- `PRODUCT.md` draft (needs user confirmation per impeccable init).
- Note: `impeccable context` flags `design-md-dead-path` (DESIGN.md cites paths renamed by #502).

## Phase 1 — automated baseline (DONE 2026-11-21)
Tool: `web-testing/design_scan.py` (new): dev-login → Chromium 390x844 → per route
`impeccable detect --cdp` + axe-core WCAG2 A/AA → `web-testing/reports/design/<date>/<theme>/`.
Run: `MSYS_NO_PATHCONV=1 PYTHONIOENCODING=utf-8 python web-testing/design_scan.py --env ../make_web/backend/.env --theme light|dark`.

Baseline, 20 routes:
| Metric | light | dark |
|---|---|---|
| impeccable findings | 87 | 97 |
| — undersized/tiny text (10px) | 41 | 41 |
| — low-contrast | 38 | 48 |
| — slop tells (ai-color-palette, icon-tile-stack, kicker-above-heading) | 6 | 6 |
| — text-occlusion (/assessment), content-hidden-at-rest (/board) | 2 | 2 |
| axe violations (nodes) | 104 | 68 |

Contrast root causes are token-level: light `#8c959f` on white/#f6f8fa (2.9–3.0:1), `#f2f2f2` on `#a6a6a6`
(2.2:1, 16 nodes), `#757575` on #f9fafb (4.4:1); dark `--color-text-muted #768390` on #161b22 (4.46:1, 20),
`#636e7b` (3.3–3.6:1). `/people` alone has 21–22 findings.

Static code metrics (frontend/src, TS): type tokens = 5 (`--fs-title 24 / heading 20 / emphasis 16 /
body 14 / caption 12`) but inline `fontSize` 137 uses with 17 distinct values (9–48) + 124 CSS px
font-sizes; hex literals 115 in tsx/ts + 94 in module.css; rgba literals 161; `style={{` 599;
z-index literals 64; `100vh` 10 vs `dvh` 10; safe-area-inset 6; 17 files with inputs (iOS zoom risk if <16px).

## Phase 2 — judgment review (DONE 2026-11-22)
Result: 5 sonnet reviewers, 167 findings (P0 1 / P1 34 / P2 93 / P3 39) in
`web-testing/reports/design/2026-11-22/review-{A..E}-*.md` (gitignored, local). Flow recapture:
`web-testing/reports/flow/2026-11-22/` (59/63 ok; 22, 38, 39, 52 failed).

Narrow targets, per flow (A taste-start/search, B swipe+result, C profile/board, D social: people/messages/
notifications/competitions, E settings/account). Per flow:
1. impeccable `critique` (scored heuristics) + `audit` (a11y/perf/theming/responsive, P0–P3) + `adapt` (mobile).
2. emil `mobile-native` (whole app once), `gestures` + `review-animations` (swipe card, sheets, page transitions),
   `break-ui` (worst-case data on PersonCard, BoardCard, messages).
3. Component-semantics pass from @uxwoodytips (toast vs snackbar, modal vs bottom sheet, alert vs confirm,
   hamburger vs kebab, empty/offline states).
4. Motion references from @ui_motion_prompts (spring ω₀16 ζ0.62, 65ms stagger, 2-layer shadows).
5. Real-device check by user (iPhone Safari + Android Chrome) with a checklist.
Reviews are read-only; run as sub-agents or in-session, findings written to files, never sliced.

## Phase 3 — report (PUBLISHED 2026-11-22: https://claude.ai/artifact/5ys5xzZbC21gHmEx2uF1MT)
Built by `web-testing/reports/design/2026-11-22/build.py` + `template.html`. 14 root causes, 10 decisions (D1-D10), PR1-PR6+.
Decisions: D1 (2026-11-22) = keep swipe-only; no buttons, no drag stamp (B-01, B-02 dropped; identity).
NEXT: user answers D2-D10, then PR1 (tokens) via front-maker.
Artifact `[Archibe]-UI점검`: per-screen screenshot + findings P0–P3 + baseline metrics. User sets priorities.

## Phase 4 — fixes (PR batches, makers)
- PR1 tokens: contrast-safe muted/dim text tokens (both themes); 10px → caption floor; inline font sizes onto
  the 5-step ramp; hex/rgba → tokens (`typeset`, `extract`).
- PR2 shared components: button/sheet/toast/dialog states + correct component per job.
- PR3 mobile-native: safe-area, dvh, input ≥16px, tap highlight, touch-action.
- PR4+ per flow: `layout`, `polish`, motion.
- Each PR: rerun `design_scan.py` (before/after counts) + screenshots; front-validate.

## Phase 5 — keep it
`learn-taste` → rules into DESIGN.md; fix DESIGN.md dead paths; decide CI `impeccable detect --sarif` (team impact).

## Tracking / gates
GitHub epic issue DESIGN-REVIEW-1. Commit after checks; push/PR only on publish keyword.
