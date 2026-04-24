# archi-tinder — Search Flow Requirements Spec

**Status**: Living document — reflects the requirements elicitation dialog between user (product owner) and research terminal. Referenced by both research and main-implementation terminals.
**Version**: 1.0
**Last updated**: 2026-04-25
**Source**: Multi-session dialog from 2026-04-22 onward, tracked at `/Users/kms_laptop/.claude/plans/reflective-weaving-seahorse.md` (Requirements Spec section + Spec Audit & Reconciliation section).

### Versioning & Update Propagation

- **Version field (X.Y)** — X bumps for breaking changes (contradicts implemented decisions); Y bumps for additions / clarifications / non-contradicting extensions.
- **Changelog** at bottom of this document tracks each version bump.
- **Update signal**: research terminal appends `SPEC-UPDATED: vX.Y → vX.Z — <sections> — <summary>` to `.claude/Task.md ## Handoffs` section on each version bump. Main terminal reads Handoffs at session start to discover updates.
- **Main terminal re-read policy**: incremental. On SPEC-UPDATED signal, read only the affected sections (not the whole spec). Full re-read is NOT required per task.

---

## Context — Why This Document Exists

The original 12-topic algorithm research was completed in `research/search/01..12-*.md`, but it optimized *within* the pre-existing pipeline shape. The user re-oriented:

> "내가 원하는 거가 너무 두루뭉술해서 좀 더 정교화된 알고리즘의 설계가 필요해서 그런 걸 수도 있고."

The required preceding step was **requirements elicitation** — pin down who the user is, what they want, and what the system's shape should be, *before* algorithm optimization. This document is the result of that elicitation. Any subsequent algorithm / code work should treat this spec as the source of truth and re-evaluate earlier research against it.

The 2026-04-25 audit pass further reconciled internal contradictions and filled gaps. See the Spec Audit & Reconciliation section in the plan file for the full audit trail.

---

## 1. Target User & Task (Dimension A)

| Attribute | Value | Implication |
|---|---|---|
| Primary user | 건축가 / 설계 실무자 | 시간 압박, 실용성 중심, 건축 어휘 숙지 |
| Primary task | **Recommendation (taste set 발견)** | 한 건물 특정 아님, curation 아님, 순수 collection 아님 |
| Usage context | 프로젝트용 reference ↔ 평소 탐색 (혼재) | 알고리즘 내부 state는 한 가지지만 input 다양성 감당 필요 |
| Constraint rigidity at session start | **Loose** (단일 filter도 불확실) | Chat phase가 load-bearing — 형식이 아니라 실질 disambiguation 수행 |

### Why this combination is non-trivial
- Architect + Recommendation + loose-input = **"hard 제약 속 soft taste 수렴"**. 현재 pipeline shape이 대체로 이 모양이지만, loose-input 처리 경로가 degraded(random fallback)에 머물러 있음.

---

## 2. Success Definition (Dimension B)

**Primary success signal**: **Top-10 bookmark rate** — 한 session 에서 사용자가 top-10 결과 중 ⭐ 저장 버튼을 누른 개수를 10 으로 나눈 intra-session 평균.

**Secondary signal**: **Exploration depth bookmarks** — rank 11-50 위에서의 ⭐ bookmark 는 별도 로깅 (primary metric 에는 포함 안 됨). "탐색 깊이" 와 "뜻밖의 발견율" 분석용.

**Primary session output**: **Top-K 건축물 리스트**. K=10 primary (metric 분모 고정), 상위 50 까지 lazy-scroll 로 확장 가능 (Section 8 참조). Persona report 는 부차적 산출물 (header accent).

### Operationalizable Objective Function

```
Maximize:   E[ bookmarks_on_top10 / 10 ]   (per session, intra-session average)

Subject to:
  - total_swipes ≤ 10   (soft target, user-driven end)
  - total_swipes ≤ 15   (auto-stop cap; user "더 swipe" 로 동일 session 내 연장 가능 — Section 5.6)
  - per-swipe latency < 500ms
  - time-to-first-card < 3-4s
```

### Unlocked by this metric
- Previously deferred research topics (05 bandits, 07 CF, 12 LambdaMART) had "no labelled data" 가 blocker. 이제 label 이 **명확히 정의됨** (top-10 ⭐ bookmark). **Session logging instrumentation 이 prerequisite** — Section 6 에 이벤트 수준 명세, 실제 스키마는 main terminal 이 구현.

---

## 3. Chat Phase / Preamble (Dimension C)

**Core UX principle**: **Chat phase = language only. No building images.** Images belong exclusively to the swipe phase. Two-modality separation (verbal articulation / visual pointing) is load-bearing — hybridizing them erodes the swipe phase's "first visual impression" moment and biases the language exploration prematurely.

### Specification

| Attribute | Value |
|---|---|
| Dialog goal | **Abstract taste probe (verbal A vs B)** — 예: "따뜻한 재료감 vs 차가운 기하성" |
| Probe axis source | **LLM autonomy** — 매 invocation마다 가장 애매한 축 dynamic 선택 |
| Exit form | **Text summary + user confirm** — "이해했어요: [풍부한 문단]. 맞을까요?" 형태. Seed card preview 없음. |
| Turn count | **0-2 turns** — LLM이 input이 precise하다고 판단하면 0 turn (skip probe) 도 허용 |
| Output artifact | `{ filters, filter_priority, raw_query, visual_description }` — 4-field. `raw_query` 는 사용자 NL 입력 원문 verbatim (Topic 01 hybrid retrieval 의 BM25 채널 재료). `visual_description` 은 HyDE V_initial 재료. |

### Signal Flow
Chat phase produces a refined **query**, not user state. `pref_vector` warm-start은 image signal 부재로 구조적으로 불가능.

- `visual_description` → HuggingFace Inference API (동일 MiniLM 모델) → **V_initial** → pool 재랭킹에 사용
- `raw_query` → tsvector 기반 BM25 채널 (Topic 01 hybrid retrieval) 재료
- `filters + filter_priority` → SQL WHERE + weighted CASE WHEN 점수

이상은 user state 와는 별개의 query-side 신호.

### Flow Diagram
```
User NL
  ↓
[Gemini 1] parse + decide: probe needed vs already precise
  ↓ (probe needed)
"A vs B?" abstract verbal question (turn 1)
  ↓
[optionally] second probe turn (if still uncertain, max 1 more)
  ↓
[Gemini final] rich paraphrase + confirmation prompt
  ↓
User confirms / refines
  ↓
→ Swipe Phase
   (with filters + filter_priority + raw_query + visual_description)
```

### Design Dependency (Critical)
- LLM prompt quality의 load-bearing. 좋은 "probe 축 선정자"여야 함 — 애매함 탐지 + 건축 어휘 구사 + 자연스러운 질문 프레이밍. 구현 단계에서 few-shot 예시 큐레이션이 핵심 자산.

---

## 4. Swipe Phase (Dimension D)

### Numeric Targets — CONFIRMED

| Attribute | Value |
|---|---|
| Swipe count | **soft target 10, auto-stop cap 15** (user "더 swipe" 로 동일 session 내 연장 가능 — Section 5.6) |
| Per-swipe latency | **< 500ms** (instant feel) |
| Time-to-first-card latency (NL submit → 첫 card) | **< 3-4s** |
| Top-K 노출 | **Initial K=10 primary + 상위 50 까지 lazy-scroll** (rank 11 이후는 divider 로 구분, Section 8). Primary metric 분모는 10 고정. |
| End state trigger | **User agency first** — 8-10 구간에서 "더 볼래요 / 끝낼래요" prompt, 15 도달 시 auto-stop. Convergence 감지는 optional aux signal. |

### Information-Theoretic Constraint

- 10 swipes × 1 bit = 10 bits (raw). Target building specification 는 대략 ~11.76 bits 요구 → raw swipe signal alone is marginal.
- Margin 을 닫기 위한 수단:
  - **Strong preamble prior**: V_initial 이 pool 내 starting neighborhood 를 10-30 buildings 로 narrow 시 대략 **+7-8 bits 추정 (hypothesis — 구현 후 instrumentation 으로 실측 필요)**
  - **Per-swipe information density supplements** (A-1 Love: 1 → 1.5 bits; B-1 tags: occasional extra signal)

### UX Supplements — Confirmed

| Code | Name | Status | Details |
|---|---|---|---|
| **A-1** | 3-4단계 강도 표현 | ✅ 옵션 1 채택 (gesture 세부 pending) | Tinder mental model + 위쪽 swipe = Love. 오른쪽=Like (intensity 1.0), 위쪽=Love (intensity 1.8), 왼쪽=Dislike (−1.0). Dislike 단계 분할 없음. Backend `SwipeView.post()` 에 `intensity` 파라미터, `update_preference_vector()` 에 weight 반영. Love/Like 둘 다 `liked_ids` 에 `{id, intensity}` 구조로 영속 저장 (Section 8). |
| **B-1** | 간헐적 "왜?" 태그 prompt | ✅ 전략 A 채택 (frequency/UI pending) | 카드의 metadata 필드(`style`, `material`, `atmosphere`, `tags`, `color_tone`, `material_visual`)에서 3개 태그 추출. LLM 동적 호출 없음. Like/Dislike 맥락에 따라 문구만 변경. |
| **C-1** | Confidence progress bar | ✅ 통합안 1 채택 | Bar + 한 줄 해석만. Phase 이름 UI에서 제거. `confidence = 1 − min(1, avg(last 3 Δv)/ε_init)`. 해석 텍스트는 pref_vector/centroid dominant attrs에서 1-line 추출. **Semantic**: "시스템이 사용자 taste 에 얼마나 좁게 수렴했는지" 를 보여주는 informational cue — 사용자가 '끝낼래요' 를 누를 시점을 스스로 판단할 수 있게 함 (end-state 가 user-agency-first 라는 점과 직접 연결). |
| **C-3** | 초기 좋은 첫 카드 | ✅ **Better 채택 (층1+2+3)** | 층1 HyDE V_initial (HF Inference API). 층2 Pool 재랭킹 (V_initial cosine). 층3 Top-10 재랭킹 결과 중 `farthest_point_from_pool()` (기존 함수 재사용) 로 첫 3-5장 선발 → 적합도 + 다양성 확보. |

### UX Supplements — Rejected

| Code | Name | User reason |
|---|---|---|
| **A-2** | 2AFC (2 cards 나란히 제시) | 프로그램 근간(Tinder 1-card 모델)이 달라짐 |
| **B-2** | Mid-session text input | UX 별로 |
| **C-2** | Mid-session preview (Go/Stop 카드) | UX 별로 + B-1 와 UI 충돌 우려 |

---

## 5. Failure Modes & Fallback Behaviors

**Overarching philosophy (사용자 지시)**: 최소 개입, silent fallback, flow 중단 최소화. 단, **normal-flow 안에서의 자동 교정은 silent (5.1)**, **degraded experience 는 사용자가 이유를 알아야 하므로 optional notice (5.2~5.4)** 라는 구분은 유지.

### 5.1 Pool Mismatch (연속 Dislike)

| Aspect | Value |
|---|---|
| Detection trigger | **5 consecutive dislikes** (현재 코드 10 → 5 로 변경) |
| Action | **Silent fallback** (rescue within normal flow): `engine.py:602-634` `get_dislike_fallback()` 현 로직 유지 (dislike centroid 반대 방향에서 카드 뽑기) |
| Secondary failure (fallback 후에도 dislike 지속) | **같은 fallback 반복** (별도 escalation 없음) |
| Implementation change | `config/settings.py` `max_consecutive_dislikes: 10 → 5` |
| Rationale for silent | 알고리즘이 스스로 교정하는 normal behavior → 사용자에게 설명 불필요 |

### 5.2 Low-Likes Session End

| Aspect | Value |
|---|---|
| Rule | **V_initial 기반으로 K=10개 채움**, likes 수와 무관 |
| Implication | **HyDE V_initial은 "첫 카드 품질" + "low-signal fallback" 두 역할 모두 수행 → critical infrastructure** |
| Edge case | Likes=0 세션도 top-10 제공 (preamble visual_description 기반). UI 에 optional notice ("스와이프 데이터가 부족해 초기 방향 기준으로 보여드려요") |
| Rationale for notice | Degraded output (user signal 부재 → 추천 질이 낮아질 수 있음) → 사용자가 이유를 알아야 함 |

### 5.3 Small Pool (Filter 매칭 부족)

| Aspect | Value |
|---|---|
| Rule | **3-tier filter relaxation 연장** (현재 `create_bounded_pool()` 3-tier 로직 그대로 유지) |
| Tiers | Tier 1 full filter → Tier 2 geo/numeric 제거 → Tier 3 random |
| `filter_relaxed` flag | UI 에 optional 표시 ("조건을 조금 완화했어요") |
| Rationale for notice | 사용자 조건이 결과에 완전히 반영되지 않았음을 알려야 함 |

### 5.4 External API Failure (Gemini parse, HF embedding)

| Aspect | Value |
|---|---|
| Rule | **전부 graceful degradation** — 세션 진행 계속 |
| Gemini parse fails | 기존 `_retry_gemini_call` 로직 유지. 최종 실패 시 empty filter + raw query 만 보존, session 시작 |
| HF Inference V_initial fails | V_initial 없이 pool 생성 (filter-only), 첫 카드도 pool 내 random-in-tier. 사용자에게 small notice |
| UX surface | "일부 기능이 제한적이에요" 식의 명시적 알림 optional; flow 자체는 멈추지 않음 |
| Rationale for notice | 기능 제한이 있다는 사실을 사용자가 알아야 만족도 관리 가능 |

### 5.5 Session Resume (사용자 이탈 후 복귀)

| Aspect | Value |
|---|---|
| Rule | **자동 resume** — 이전 상태 그대로 이어서 |
| Mechanism | 기존 `SessionStateView` 재사용 (`backend/apps/recommendation/views.py:241-376`) |
| User prompt | 없음 — silent resume. 사용자가 "새로 시작"을 원하면 별도 UI (예: 홈에서 새 project 만들기) 경로로. |

### 5.6 Result Retry ("이 top-K 마음에 안 들어")

| Aspect | Value |
|---|---|
| Rule | **"더 swipe" 버튼** — **동일 `session_id` 안에서** 기존 pool + 기존 signal 보존 + 5-10개 추가 swipe → 재계산된 top-K |
| "Auto-stop 15" 와의 관계 | 15 는 **시스템 자동 종료점** (auto 진행 시 멈추는 cap). 사용자가 "더 swipe" 를 누르면 같은 session 안에서 15 를 초과 swipe 가능. System 은 자동으로 이어가지 않고 user agency 로만 연장. |
| 완전 리셋 | 새 project 만들기로 유도 (같은 project 내 reset 없음) |
| Pool 고갈 보호 | **Implementation requirement** (Section 6 참조): main terminal 이 pool 크기가 예상 swipe 수보다 현저히 작아지면 3-tier relaxation 을 즉시 실행하여 고갈 방지 |

### 5.7 Combined Failure (V_initial 실패 + likes=0 동시 발생)

| Aspect | Value |
|---|---|
| Situation | 5.2 와 5.4 교집합 — HyDE API 장애 + 사용자 signal 부재 |
| Rule | **Filter-only pool 상위 10개로 top-K 채움** (pool 내부 기존 CASE WHEN 점수 기반 정렬) |
| UX surface | "정보가 적어 기본 추천이에요" 식의 notice (5.2 보다 조금 더 명시적) |
| Rationale | Quality drop 이 제일 큰 구간이므로 사용자에게 기대치 조정 cue 제공 |

---

## 6. Session Logging Requirements

**Purpose**: Primary objective function (top-10 bookmark rate) 실측과 후속 튜닝 (bandit, CF) 을 가능케 하는 전제 조건. **Spec 범위는 이벤트 목록까지**; 구체 스키마 필드 설계 / DB 테이블 구조 / 인덱스 설계 는 **main terminal 이 구현 단계에서 결정**.

### Events to Log (이벤트 수준 명세)

| Event | Trigger | 포함되어야 할 의미적 정보 (spec-level) |
|---|---|---|
| `session_start` | Chat phase 확정 직후 session 생성 시 | query, filters, filter_priority, raw_query, visual_description, V_initial 성공/실패 |
| `swipe` | 매 카드 swipe 시 | 방향 (like/love/dislike), intensity (A-1), card_id, timestamp, rank_in_pool (해당 카드의 pool 내 순위) |
| `tag_answer` | B-1 태그 prompt 응답 시 | 선택된 tag 또는 Skip, like/dislike 맥락 |
| `confidence_update` | C-1 confidence 변화 시 (내부 계산) | confidence 값, dominant attributes |
| `session_end` | 세션 종료 시 | end_reason (user_confirm / auto_stop_15 / error), total_swipes, likes_count, loves_count, dislikes_count |
| `session_extend` | "더 swipe" 버튼 클릭 시 | additional_target, timestamp |
| `bookmark` | Result page ⭐ 클릭 시 | card_id, rank_zone (1-10 primary / 11-50 secondary), timestamp, action (save/unsave) |
| `detail_view` | Top-K 카드 클릭하여 detail page 진입 시 | card_id, timestamp |
| `external_url_click` | Detail page 의 "Original 보기" 클릭 시 | card_id, url |
| `failure` | API 실패 / pool 소진 경고 발생 시 | failure_type (gemini_parse / hf_embedding / pool_exhaustion_warning), recovery_path |

### Implementation Requirements (Main Terminal 유의 사항)

1. **Pool 소진 방지** (critical): pool 크기가 예상 swipe 수 대비 현저히 작으면 (예: 남은 pool < 5 building 시점), 3-tier filter relaxation 을 즉시 실행하여 새 buildings 를 pool 에 확보해야 함. Pool 고갈 상태에서 swipe 요청이 들어오면 안 됨.
2. **Event timestamp 정확성**: 이벤트 간 순서가 분석에서 load-bearing (예: bookmark 가 어느 rank 위에서 발생했는지, swipe 직후 얼마 만에 intent 가 바뀌었는지). DB 수준에서 monotonic timestamp 보장.
3. **Anonymized aggregation 호환**: 개인 식별 정보와 분리 가능하도록 user_id / session_id 체인 설계. 장기적으로는 user-agnostic 집계가 bandit reward 학습 / CF 에 쓰임.
4. **Bookmark 이벤트 의미 해석**: rank_zone 분리 (1-10 primary metric 대상, 11-50 secondary exploration signal) 를 로그에 명시적으로 기록하여 metric 추출 시 혼동 방지.

---

## 7. Session Lifecycle

### Flow (end-to-end)

```
[Home: 프로젝트 선택 or 새 project]
  ↓
[Chat phase] NL → Gemini probe (0-2 turn) → confirm
   → { filters, filter_priority, raw_query, visual_description, V_initial }
  ↓  (time-to-first-card < 3-4s)
[Swipe phase]
  Card 1-N with prefetch (per-swipe <500ms)
  ├─ A-1 intensity (Like/Love/Dislike)
  ├─ B-1 tag prompt (occasional)
  ├─ C-1 confidence bar (live)
  └─ Background: consecutive dislike detection (>=5 → silent fallback)
  ↓  (8-10 구간: "더 볼래요 / 끝낼래요" prompt 가능)
  ↓  (15에서 auto-stop, user 가 "더 swipe" 로 연장 가능 — 동일 session_id)
[Result page]
  ├─ 상단 compact header: persona_type + one_liner + Imagen accent (≤40% viewport)
  │   - Imagen 은 async prefetch, 도착 전 skeleton UI
  ├─ 하단 Top-K carousel (K=10 primary + lazy-scroll to 50, divider at rank 11)
  │   - 각 카드에 ⭐ bookmark 버튼
  └─ 카드 클릭 → Detail page
  ↓
[Detail page] (per building)
  ├─ image_photos gallery
  ├─ image_drawings
  ├─ metadata (architect, year, program, style, atmosphere, etc.)
  ├─ visual_description (long-form)
  ├─ ⭐ save button
  └─ "Original 보기" → external URL 새 탭
```

### Persistent State

Per `Project`:
- `liked_ids` (existing, **구조 변경**): `list[{id: str, intensity: float}]` — Like 는 1.0, Love 는 1.8 로 intensity 영속 저장. Resume / persona 재계산 시 intensity 활용.
- `disliked_ids` (existing): `list[str]` — 단순 ID 리스트 (intensity 없음)
- `saved_ids` (**NEW**): `list[{id: str, saved_at: datetime}]` — top-K 에서의 ⭐ bookmark. Timestamp 로 saving 순서 / analytics 추적.
- `session_history` (existing): sessions 이어서 resume

---

## 8. Result Page & Bookmark Design

### Result Screen Layout

```
┌─────────────────────────────────────┐
│  [Persona header + Imagen accent]   │ ≤ 40% viewport
│  persona_type (big text)            │
│  one_liner (smaller)                │
│    ← Imagen 이미지 옆에 accent      │
│      (async prefetch, skeleton 표시) │
├─────────────────────────────────────┤
│                                     │
│  [Top-K Carousel]                   │ ≥ 60% viewport, scroll
│  ┌───┐ ┌───┐ ┌───┐ ...              │
│  │ ⭐ │ │ ⭐ │ │ ⭐ │  (rank 1-10)   │
│  │card│ │card│ │card│                │
│  └───┘ └───┘ └───┘                  │
│  ── "더 많은 추천" divider ──       │
│  ┌───┐ ┌───┐ ...                    │
│  │ ⭐ │ │ ⭐ │   (rank 11-50,       │
│  │card│ │card│    lazy-scroll)      │
│  └───┘ └───┘                        │
│   ↓ 카드 클릭                        │
│  [Detail page 이동]                 │
└─────────────────────────────────────┘
```

**제약**:
- Initial viewport 에서 Top-K 첫 카드가 최소 1개는 보여야 함 (scroll 안 내리면 bookmark 행동이 일어나지 않음 → metric 오염 방지).
- Persona Imagen 이미지는 **비동기 prefetch** — 생성이 완료될 때까지 skeleton placeholder 표시. Result page 진입을 Imagen 생성이 block 해선 안 됨.

### Top-K Loading Behavior

| Item | Value |
|---|---|
| Initial 노출 | Top-10 (primary recommendation zone) |
| Lazy-scroll 확장 상한 | Rank 50 까지 (상위 50 이 exploration zone) |
| 로딩 방식 | Scroll 하단 도달 시 10개씩 추가 fetch (IntersectionObserver) |
| 시각 구분 | Rank 10 직후에 divider + "더 많은 추천" heading — 사용자에게 "이후는 탐색용" 이라는 프레임 |
| Primary metric 분모 | **10 (고정)** — lazy-load 해도 분모 변동 없음. 11-50 bookmark 는 secondary exploration signal 로 별도 로깅 |
| Pool 상한 | 남은 pool 이 50 미만이면 가능한 만큼만 노출 + "더 볼 게 없어요" label. Section 6 의 pool 소진 방지 규칙과 연동. |

### Bookmark Semantics

| Action | Trigger | Storage | Semantic |
|---|---|---|---|
| Like (heart) | Swipe-time, 오른쪽 | `Project.liked_ids` 에 `{id, intensity: 1.0}` append | 빠른 반응 — "이거 괜찮음" |
| Love (heart+) | Swipe-time, 위쪽 | `Project.liked_ids` 에 `{id, intensity: 1.8}` append | 강한 긍정 반응 |
| Dislike (×) | Swipe-time, 왼쪽 | `Project.disliked_ids` 에 id append | 거부 |
| ⭐ Bookmark | Result page, 버튼 클릭 | `Project.saved_ids` 에 `{id, saved_at: now()}` append (**NEW**) | **최종 선별** — primary success metric |

### Persona Report Integration

- `persona_type` + `one_liner`: header 에 직접 표시
- `description` (긴 텍스트): header 안에 포함 안 함. "자세히 보기" 토글 또는 생략
- `dominant_programs` / `dominant_styles` / `dominant_materials`: 표시 optional (미니 칩 형태로 header 에 얹을 수 있음)
- `report_image` (Imagen generated PNG, base64): header 우측 accent. **비동기 prefetch, 도착 전 skeleton**.

### Detail Page

| Element | Source |
|---|---|
| Image gallery | `architecture_vectors.image_photos`, `image_drawings` |
| Title + metadata | `name_en`, `project_name`, `architect`, `year`, `program`, `style`, `atmosphere`, `material`, `location_country`, `area_sqm` |
| Long description | `visual_description`, `description` |
| External link | `url` (새 탭) |
| Actions | ⭐ bookmark toggle, ← back to top-K |

---

## 9. Hard System Constraints (pre-existing)

- Corpus: `architecture_vectors` ≈ 3,465 buildings; pre-computed 384-dim multilingual MiniLM embeddings; Make DB owned (read-only from Make Web).
- Stack: pgvector on Neon PostgreSQL; no local SentenceTransformers dependency; Gemini 2.5-flash + Imagen 3 integrated.
- Frontend: React + Vite, inline JS styles (see `DESIGN.md`).
- Django 4.2 LTS, raw SQL for `architecture_vectors`.

---

## 10. Open Design Questions (tracked)

### User-side open (사용자 추가 고민 중)
1. **A-1 제스처 세부** — 위쪽 swipe 애니메이션, threshold 거리, 기존 `tinder-card` 라이브러리 호환. Frontend jsx 변경 범위 파악 후 결정.
2. **B-1 빈도 + UI 디테일** — 매 swipe vs uncertainty-triggered vs "세션 초기 3회 + 중간 1회" 같은 간단 규칙. UI pill-slide-in 이 best인지 재검토.

### Newly surfaced (2026-04-25 audit)
3. **Session 간 신호 전이** — 같은 project 의 여러 session 간 `liked_ids` / `pref_vector` 이어쓰기 여부. 현재 spec 은 암묵적 독립이지만 명시 필요.
4. **Empty-state** — Project 0개 상태 사용자 방문 시 UX (guided flow / empty state + create button / demo query?). 현재 spec 은 "Home → project 선택" 만 명시, 0-project 분기 미정.
5. **"그냥 random 보여줘" 메타 요청** — Chat phase 에서 사용자가 constraint-free exploration 을 요청한 경우. `raw_query` 를 그대로 Gemini 가 해석하게 맡길지, 명시적 메타 intent 로 분기할지.

### Scope / Secondary (defer-able, spec 없어도 V1 가능)
6. **Multi-project relationship** — 같은 user의 project 간 신호 공유? 현재 독립. 필요 시 Phase 16+ (Recommendation expansion) 와 함께 설계.
7. **Multi-language behavior** — Korean 입력 처리. Gemini는 multilingual, embeddings도 multilingual MiniLM. 기본적으로 문제 없어 보이지만 edge case 검증 필요.
8. **Mobile vs desktop UX 차이** — 현재 viewport-lock 모바일 first. Detail page 등이 데스크톱에서 어떻게 보일지.
9. **Privacy / sharing** — Phase 13+ Profile/Board 시스템과 함께 설계. 검색 엔진 자체 범위 밖.

### Implementation-side open (구현 진입 시 결정)
10. **C-1 phase UI 현황 검증** — 프론트 현재 phase 표시 위치 / 통합안 1 과 충돌 여부. 구현 시 code read.
11. **A-1 weight 값 튜닝** — Like 1.0 / Love 1.8 추정치, Optuna 튜닝 대상. Dislike 비대칭 (topic 05 실증 지지) 유지.
12. **Session logging schema 상세** — Section 6 은 이벤트 목록까지만 spec. DB 테이블 구조 / 필드 타입 / 인덱스는 main terminal 이 구현 단계에서 결정.
13. **`Project.liked_ids` 구조 변경 migration** — `list[int]` → `list[{id, intensity}]` schema 변경 (기존 데이터 intensity=1.0 로 default).
14. **`Project.saved_ids` 필드 추가 migration** — Django model + migration 파일 준비.

---

## 11. Actionable Technical Directives (absorbed from 12 research topics)

**Purpose of this section**: Main terminal should be able to implement all spec decisions **without reading any file under `research/search/**`**. Each directive below consolidates the concrete actionable outcome from its source research report — flag names, hyperparameter values, file locations, gating conditions. Source reports remain as reasoning archive only.

Priority tiers are research-terminal recommendations; main terminal decides task breakdown and sequencing.

### Critical — blocks the new design

| Topic | Directive | Flag / Config | Priority |
|---|---|---|---|
| **03** HyDE V_initial | Gemini 의 `visual_description` 출력을 HuggingFace Inference API (`paraphrase-multilingual-MiniLM-L12-v2`, 384-dim) 로 임베딩 → `V_initial`. Pool 생성 시 재랭킹에 사용. C-3 (Section 4) + 5.2 low-likes fallback + 5.7 combined failure 의 전제. | `HYDE_VINITIAL_ENABLED` | **Critical** (not optional) |
| **10** Convergence bug fix | 2개 구조적 버그 unconditional fix: (1) Delta-V 를 every swipe 에 append (현재 like-only), (2) `convergence_history` 를 phase 전환 시 reset. 이후 optional: 1-D Kalman filter with credible-interval gating + Prechelt patience/min-delta fallback. | Kalman: `KALMAN_CONVERGENCE_ENABLED` | **Critical bug** (unconditional); Kalman optional |

### Priority Up under new spec

| Topic | Directive | Flag / Config | Priority |
|---|---|---|---|
| **01** Hybrid retrieval | Katz-style RRF blend between tsvector (BM25 on `visual_description`, `tags`, `material_visual`) and pgvector cosine. `raw_query` (Section 3 chat output) 을 BM25 채널 입력으로. 위치: `get_top_k_mmr()` 이후. | `HYBRID_RETRIEVAL_ENABLED`, α=0.6 vec / 0.4 tsvector | High |
| **02** Gemini session-end rerank | Gemini 2.5-flash setwise rerank of ~60 candidates at session completion (off swipe hot path). Fuse with MMR via RRF (diversity 보존). ~$0.003/session. | `GEMINI_RERANK_ENABLED` | High |
| **04** Diversity | (a) Per-swipe MMR λ ramp: `λ(t) = λ_base · min(1, \|exposed\|/N_ref)` (one-line change). (b) Session-final DPP greedy MAP (Chen 2018 Cholesky-incremental) at top-K. MMR λ 기본값은 유지. | DPP: `DPP_TOPK_ENABLED` | High (directly boosts top-10 bookmark rate) |

### Spec-agnostic improvements (still applicable)

| Topic | Directive | Flag / Config | Priority |
|---|---|---|---|
| **06** Adaptive k ∈ {1, 2} | K-Means clustering 이 sample-starved 일 때 k=1 로 degrade. Silhouette score 기반 자동 선택, threshold 0.15. 직교적으로 soft-assignment relevance (softmax over centroid distances). <40-line sklearn-only change. 위치: `engine.py:451-489, 516, 722, 737`. | `ADAPTIVE_K_CLUSTERING_ENABLED`, `SOFT_RELEVANCE_ENABLED` | Medium |
| **12** Pool score normalization | `_build_score_cases()` 의 score 를 Σ active-filter weights 로 나눠 [0,1] 로 정규화 (weight-scale drift 제거). Seed boost 는 clean 1.1. 1-line fix. | N/A (직접 수정) | Medium (low-risk cleanup) |
| **09** ANN indexing | **Do nothing now.** 현재 ~3,465 corpus 에서 brute-force cosine < 1ms. Trigger: p95 > 150ms OR corpus > 50K rows. Ship per-query timing logs 만. Trigger 도달 시 HNSW `CREATE INDEX CONCURRENTLY` (IVFFlat 보다 선호). | timing logs 만 | Low (defer migration) |

### Integrate with existing design decisions

| Topic | Directive | Notes |
|---|---|---|
| **11** Cold-start seed | C-3 Better 의 층3 (`farthest_point_from_pool`, `engine.py:410-448`) 에 통합됨. 별도 ship 필요 없음. 옵션으로 query-informativeness branch: bare query → pool 250 + tier-ordering skip, flag `BARE_POOL_WIDEN_ENABLED` default off. | 층3 만 구현하면 core 는 완료 |
| **08** Multi-modal embedding | Additive channel: `architecture_vectors` 에 `image_embedding` 컬럼 신설 (jina-clip-v2 1024-dim 또는 SigLIP 2 768-dim). **Make DB 협의 필수** — Make Web 은 읽기만. Phase 16+ 후기 사이클. | Make DB coordination 트랙, 현재 구현 대상 아님 |

### Deprioritized / Defer

| Topic | Directive | Notes |
|---|---|---|
| **05** Preference weight learning (bandits) | Optuna-tuned fixed weights 유지. Bandits 도입 조건: ≥1K logged sessions + per-weight signal 명확. 지금은 **Section 6 logging 먼저**. 옵션: online EMA on like/dislike asymmetry ratio (flag-gated). | pref_vector 가 analyzing phase card selection 에 미사용 → ceiling 낮음 |
| **07** Collaborative filtering | 진짜 CF (iALS, LightGCN, PinSage) 는 defer — 조건 `N_projects ≥ 500 AND median_likes ≥ 20`. 지금 ship 가능 한 가지: flag-gated global popularity prior (default weight=0.0, min_exposures=5), `_build_score_cases()` 에 블렌드. | Scale-gated |

### Not currently actionable (informational)

- **Multi-modal embedding (08)** — Make DB 오너십 바깥. 후기 coordination 트랙.

### Archive pointer

각 topic 의 literature 근거 / 대안 분석 / sources 는 `research/search/NN-*.md` 에 보존. **정상 구현 시에는 읽을 필요 없음** — 여기 표의 directive 만으로 충분. Research terminal 이 추가 탐구·수정 시 참조.

---

## 12. Governance

### Terminal Role Separation (hard rule)

사용자 지시 (2026-04-22): 터미널별 책임 분리는 **절대적 규칙**이며, 세션·대화가 바뀌더라도 준수되어야 함.

| Terminal | Role | Write permissions |
|---|---|---|
| **Research terminal (this)** | 리서치 + 사용자 대화 + 요구사항 정교화 + spec 문서화 | `research/**` (모든 하위 폴더), `.claude/Task.md` (append-only RESEARCH-READY 마커만). 그 외 **절대 금지**. |
| **Main terminal** | 실제 코드 작성 + 구현 + 커밋 | `backend/`, `frontend/`, `web-testing/`, `.claude/Report.md`, 기타 application files. `research/**` 은 읽기만. |

### Research terminal 금지 사항 (명시)
- `backend/`, `frontend/`, `web-testing/` 어떤 파일도 수정/생성/삭제 금지
- `.claude/agents/**` 수정 금지
- `.claude/settings*.json` 수정 금지
- `CLAUDE.md`, `DESIGN.md`, `GEMINI.md`, `.claude/Goal.md`, `.claude/Report.md` 수정 금지
- Git commit / push 금지
- Dev server 실행 / 테스트 / 벤치마크 실행 금지

### 문서 유지보수 규칙

- 이 `requirements.md` 는 **research terminal이 유지** — main terminal은 읽기만.
- 업데이트 트리거: 사용자 결정에 따른 design decision 확정 / 재조정.
- 새로운 open question 등장 시 Section 10 에 append.
- Decision이 "확정" 상태로 바뀌면 해당 섹션의 PENDING 마커 제거 + Status 갱신.

### Main terminal로의 전달 채널

1. `research/spec/requirements.md` (이 문서) — **spec 기준점 (binding)**
2. `research/spec/research-priority-rebaselined.md` — 12 research topics 의 우선순위 재평가 + 제안 sprint 구성 (**recommendation, non-binding**)
3. `research/search/**` — 상세 research reports (참고 근거)
4. `.claude/Task.md` 의 `## Research Ready` 섹션 — RESEARCH-READY 마커로 각 research topic 의 이행 대기 상태 표시

### Binding vs Recommendation 경계

- **Binding (반드시 따름)**: 이 `requirements.md` 의 내용 — 사용자 의도 / 목표 메트릭 / UX 결정 / 실패 모드 / Section 6 logging 이벤트 목록 등
- **Recommendation (참고 자료)**: `research-priority-rebaselined.md` 의 Tier 분류 및 Sprint 0-5+ 구성, `research/search/**` 의 각 topic Options 섹션

### Main terminal 의 권한 (authority)

Main terminal 은 spec 을 따르되 다음을 **독자적으로** 결정:
- Task 분해 (granularity, 병렬성)
- 작업 순서 / 우선순위 / 페이싱
- Sprint 재편성 (rebaselined.md 의 Sprint 경계를 그대로 쓸지, 재구성할지, 아예 다른 방식으로 조직할지)
- 기술 선택 (research report 의 여러 Option 중 어느 것을 쓸지, 또는 다른 방식으로 해결할지)
- 언제 구현할지 / 언제 defer 할지

Research terminal 은 근거 자료를 제공할 뿐, 실행 계획과 구현 결정에는 개입하지 않음. Main terminal 이 research 문서를 참조한 뒤 자체 orchestrator 파이프라인으로 계획·코드를 작성한다.

---

## Changelog

각 버전 bump 는 `.claude/Task.md ## Handoffs` 에 `SPEC-UPDATED: vX.Y → vX.Z — <sections> — <summary>` 형태로도 기록 (main terminal notification).

| Version | Date | Changes | Scope |
|---|---|---|---|
| **1.0** | 2026-04-25 | Initial consolidated spec — Dimensions A/B/C/D + Sections 5 Failure modes + 6 Session Logging + 7 Lifecycle + 8 Result Page. Audit reconciliation (C1~C4 / H1~H3 / M1~M4 / L1~L4). Section 11 expanded to actionable directives per topic (main no longer needs to read individual research reports). | Initial |
