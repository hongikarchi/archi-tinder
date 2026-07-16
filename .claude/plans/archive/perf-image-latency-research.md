# Frontend + Image-Rendering Latency — Research Initiative (research-only, NO production code)

> 한글 요약 블록 + 영문 코드 식별자. 산출물 = research report(`docs/research/image-latency/`). **코드 작성 안 함.**

## 한글 요약

- **문제(user):** front→back→front→이미지요청→웹렌더 왕복이 너무 느림. 알고리즘(백엔드 연산)은 타인 담당 → **우리는 프론트 + 이미지 렌더 부분만**.
- **user 가설:** (1) 이미지 해상도 과도, (2) PNG/JPEG→WebP면 빨라질 것.
- **핵심 reframe (코드맵으로 확인):** swipe 카드 이미지 = **외부 소스 CDN URL 그대로 사용**(Divisare/Dezeen/Archdaily…). R2 합성 **폐기됨**. srcset·`<picture>`·resize·transcode·Vercel image-opt **전무**. → **우리가 바이트를 제어 안 함.** format/해상도 바꾸려면 **이미지 프록시/트랜스코드/CDN 레이어 (재)도입** 필요 = "프론트만" 경계 넘고 + 과거 R2-폐기 결정 되돌림. persona report 이미지는 **이미 WebP@q82**.
- **원칙:** 측정 먼저(추측 X) → 측정 impact로 이슈 랭킹 → 이슈별 1차출처(논문/스펙/타사) 리서치. 프록시 도입 여부는 **측정 후** 데이터기반 결정.

## Method (공식문서 검증 완료 2026-06-15)

- **`/deep-research <q>`** — Claude Code **내장 워크플로**(workflows.md): 웹 fan-out→fetch+교차검증→claim vote→인용 리포트. 솔루션 리서치(웹) 엔진. 레포 못 봄.
- **dynamic workflows = ultracode** — JS 멀티에이전트 fan-out, 레포 인지. 측정/분석 + 우리 아키텍처 맞춤 리서치.
- **`/goal <cond>`** — 완료조건까지 세션 자율 구동(goal.md). user가 입력해야 함. 평가자(Haiku)는 대화 surface분만 판정.
- **결정:** `/goal`(자율 구동축) + 이슈별 deep-research(리서치 엔진) 결합. 측정은 로컬 Playwright(레포 인지, repo-blind한 deep-research 미사용).
- Anthropic **Research 제품**(claude.ai 웹전용, 유료) ≠ CLI `/deep-research` 내장 워크플로 — 별개.

## Decisions (RESOLVED)

1. **측정 소스 → 로컬 self-serve 먼저** (user 2026-06-15). Playwright로 로컬 swipe 돌려 이미지 특성·decode·waterfall 실측. prod telemetry(geo, load_ms)는 승인 게이트 + 로컬 실트래픽 없음 → 후속·보류. 싱가포르 geo는 잠정(코드주석 "1.7–2.6s").
2. **리서치 구동 → /goal(축) + deep-research(엔진) 결합** (user 2026-06-15, "시간 무관 완성까지").

## Phase 0 — MEASURE (로컬 Playwright, repo-aware)

대상 = swipe/discovery 카드 이미지(주 불만 표면) + persona report 이미지(부차).
per-image 캡처(>=20 카드): `content-type`/format, `naturalWidth/Height`, 렌더 표시크기(CARD_WIDTH×HEIGHT), 전송 bytes(`PerformanceResourceTiming.encodedBodySize`/`transferSize`/`decodedBodySize`), decode ms(`img.decode()` / Element Timing), load_ms, CDN host, cache(`transferSize==0`).
파생 지표: **over-fetch ratio**(natural px ÷ displayed px) ← 가설1 직접검증, **format 분포**(png/jpeg/webp/avif) ← 가설2, bytes 분포, decode 분포, CDN host별 load 분포.
또한: 동시/순차 로딩, instant-swap vs blocking-preload 비율, skeleton/spinner 거동.
**측정 코드 = throwaway 계측 하니스**(backend/·frontend/ 미수정, 미커밋). 생산코드 아님.

## Phase 1 — RANK
측정 impact로 이슈 정렬. 측정 전까진 이슈 리스트 = 잠정.
후보 이슈축: over-fetch(해상도 과도) · format(코덱) · CDN geo/RTT · decode/render · 프리로드/순서 · 캐싱.

## Phase 2 — RESEARCH (이슈별, 1차출처)
이슈별 deep-research 패턴(교차검증+인용). 조사축:
- **Codec**: WebP vs AVIF vs JPEG XL (스펙·디코드비용·브라우저 지원·바이트절감 벤치).
- **Responsive delivery**: `srcset`/`sizes`/`<picture>`, DPR, `fetchpriority`, `<link rel=preload>`, lazy/eager.
- **이미지 프록시/CDN/트랜스코드**: 온더플라이 리사이즈·포맷협상 아키텍처(타사 방식), 핫링크/저작권/비용, **R2 폐기 사유**(추측 금지 — 코드/PR/이력 + 필요시 user 확인).
- **HTTP**: 캐싱(RFC 9111), conditional, CDN edge.
- **Decode/render**: 메인스레드 decode, `decoding=async`, `content-visibility`, 레이아웃.
산출: 이슈별 ≥2 독립 1차출처 인용.

## Phase 3 — SYNTHESIZE
측정+리서치 → 권장 플랜(코드 X). 프론트만으로 가능 vs 프록시 필요를 측정 데이터로 가름.

## Deliverable
`docs/research/image-latency/` (report + measurements JSON). 코드 변경 0.

## Hard constraints
- 생산코드(backend/·frontend/) 미수정. 측정 하니스는 throwaway.
- prod DB read = 게이트. Phase 0 로컬만.
- 알고리즘/엔진(engine·embeddings·rerank…) 외부소유 — 안 건드림.
