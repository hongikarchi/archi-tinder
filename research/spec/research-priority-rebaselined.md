# 12 Research Topics — Priority Rebaselined Under New Spec

**Context**: The 12 topics in `research/search/01..12-*.md` were written *before* the requirements spec was finalized (see `research/spec/requirements.md`). They optimized within the pre-existing pipeline shape. This document re-prioritizes each topic under the finalized spec.

**Last updated**: 2026-04-25 (post-audit; reflects `requirements.md` v2026-04-25 resolutions — C1~C4 / H1~H3 / M1~M4 / L1~L4 + new Section 6 Session Logging Requirements)

---

## Authority Boundary (read this first)

This document is a **research terminal recommendation**. It re-prioritizes the 12 research topics under the finalized spec and proposes a possible sequencing for reference.

**Binding**: the content of `research/spec/requirements.md` (the spec itself).
**Non-binding (recommendation)**: Priority Tiers and Sprint 0-5+ groupings below. They represent the research terminal's view of dependencies and impact-ordering.

**Main terminal has full authority to**:
- Break tasks differently (smaller / larger units, parallel vs serial)
- Reorder sprints or merge/split phases based on current codebase state
- Skip, defer, or inject topics that aren't in the tier list
- Reject the "Sprint N" framing entirely if a different plan fits better

The value of this document is as **input material for main terminal's own planning**, not as a task queue to execute verbatim.

---

## Priority Tiers (new)

### Tier A — Critical for the New Design (블록 관계에 있는 전제)

| # | Topic | Why critical now |
|---|-------|------------------|
| **03** | Query understanding (HyDE V_initial) | C-3 (초기 좋은 첫 카드) 의 **필수 전제**. V_initial 없이는 pool 재랭킹 불가. 또한 Chat phase output `visual_description`을 바로 소비하는 자연 경로. |
| **10** | Convergence detection bug-fix | 구조적 버그 2개 (Delta-V like-only append / phase 전환 시 history 미reset) 는 spec 독립적 — 어떤 pipeline shape에서도 고쳐야 함. |

### Tier B — Priority Up Under New Spec

| # | Topic | Why up |
|---|-------|--------|
| **01** | Hybrid retrieval (BM25 + vector) | Chat phase 의 `raw_query` + `visual_description` 을 활용할 경로가 spec에 명시됨. Topic 01의 tsvector 채널이 자연스럽게 consumer가 됨. |
| **02** | Gemini setwise rerank (session-end) | Session output이 **top-K list 품질** 이라는 primary objective로 확정 → session-end rerank가 목적함수에 직접 기여. 이전 "nice to have"에서 "objective-critical"로 격상. |
| **04** | Diversity (DPP at session-final top-K) | 같은 이유 — session-final top-K의 품질이 objective이므로 DPP greedy MAP의 기대 영향이 명확해짐. MMR λ ramp (per-swipe)도 여전히 유효. |

### Tier C — Still Applicable (spec-agnostic fixes)

| # | Topic | Why still good |
|---|-------|----------------|
| **06** | Adaptive k ∈ {1, 2} via silhouette | K-Means 샘플 기아 문제는 spec과 무관한 수학 문제. 구현 <40줄, sklearn only. |
| **12** | Pool score normalization | 1줄 수정 — weight-scale drift 해결. spec과 독립. |
| **09** | ANN indexing (logging only, defer migration) | 현재 corpus size에서 brute-force 충분. Timing logs만 ship → trigger 감지용. |

### Tier D — Recontextualize / Merge

| # | Topic | Action |
|---|-------|--------|
| **11** | Cold-start seed strategies | C-3 와 통합 검토. Topic 11의 "query-informativeness branch" 아이디어는 Chat phase의 "probe needed vs not" 결정과 자연스럽게 overlap. Integration plan 별도 작성 필요. |
| **08** | Multi-modal embedding (image + text) | Make DB 협의 필요 (architecture_vectors 스키마 변경). Sprint 1-2 아님, 후기 사이클에 coordination 트랙으로. |

### Tier E — Deprioritized Under New Spec

| # | Topic | Why down |
|---|-------|----------|
| **05** | Preference weight learning (bandits) | 이미 "impact ceiling low" (topic 05 자체 결론). 새 spec의 primary objective (top-K 품질) 하에서 ceiling 더 낮아짐. `pref_vector`는 analyzing phase card selection에서 안 쓰이고, top-K rerank는 Gemini에게 위임(Topic 02) — bandit이 움직일 공간이 거의 없음. **Optuna-tuned fixed weights 유지**. |
| **07** | Collaborative filtering | 여전히 scale-gated (`N_projects ≥ 500 AND median_likes ≥ 20`). **Popularity-prior bridge** (default weight=0) 만 ship 대상. |

---

## Suggested Implementation Sequence (research recommendation — non-binding)

> **Note**: Sprint grouping below is a research-terminal proposal based on topic dependencies (e.g., Topic 03 HyDE unblocks C-3; Section 6 logging unblocks objective measurement). Main terminal may adopt, reorder, merge, split, or ignore this structure based on its own assessment of code-state priorities, team capacity, and risk.

### Sprint 0 — Instrumentation + Spec-independent Bug Fixes + Schema Migration
- **Topic 10**: convergence bug fix (2 buggy bits, 즉시 ship)
- **Topic 09 partial**: per-query timing logs
- **Session logging infrastructure (expanded under audit)**: 이벤트 수준 명세는 `requirements.md` Section 6 참조 — `session_start`, `swipe` (with intensity), `tag_answer`, `bookmark` (with rank_zone 1-10 / 11-50), `session_end`, `session_extend`, `confidence_update`, `detail_view`, `external_url_click`, `failure`. DB 테이블·필드 구조는 main terminal 이 구현 단계 결정.
- **Topic 12**: pool score normalization (1줄)
- **Pool exhaustion guard (NEW, audit)**: `create_bounded_pool()` 에 남은 pool 감시 + 임계치 미만이면 3-tier filter relaxation 즉시 재실행 (requirements.md 5.6 implementation note).
- **Project schema migration (NEW, audit)**:
  - `liked_ids`: `list[int]` → `list[{id, intensity}]` (기존 데이터 default intensity=1.0)
  - `saved_ids`: 신설 (`list[{id, saved_at}]`)

### Sprint 1 — Chat Phase (Dimension C) Implementation
- Gemini prompt enrichment: `parse_query()` returns `{reply, filters, filter_priority, raw_query, visual_description}` in single call
- Gemini probe logic: "already precise?" judgment + abstract A/B probe question generation (LLM autonomy)
- Turn budget: **0-2 probe turn** (LLM 판단 시 0 turn skip 허용)
- Exit: text summary + confirm (NO seed cards)

### Sprint 2 — Pool Quality Upgrade (C-3 Better + Topic 03 + Topic 11 + 5.7)
- **Topic 03 (HyDE V_initial)**: HuggingFace Inference API client + flag
- **C-3 층 1 + 층 2 + 층 3 (Better scope 확정)** — 층 3 은 기존 `farthest_point_from_pool()` (`engine.py:410-448`) 재사용
- Topic 11의 query-informativeness branch를 C-3와 통합 (bare query → wider pool + skip tier-ordering)
- **Combined failure handling 5.7 (NEW, audit)**: V_initial fail + likes=0 동시 발생 시 filter-only pool 상위 10 + UI notice

### Sprint 3 — Swipe UX Supplements (A-1 + B-1 + C-1)
- A-1: 위쪽 swipe = Love handler (frontend tinder-card extension + backend intensity weight). **gesture 세부 (애니메이션, threshold 등) 는 사용자 확정 대기** (Outstanding Decisions #1).
- B-1: 태그 추출 (metadata 기반) 기술 path 구현. **frequency + UI (pill-slide-in 여부 포함) 는 사용자 확정 대기** (Outstanding Decisions #2) — 초기 안 (3회 + 1회, pill-slide-in) 은 참고 기준, 확정 아님.
- C-1: confidence bar + 1-line interpretation (Phase label 제거) + **semantic cue "사용자가 '끝낼래요' 판단하도록 보여주는 informational cue"** (audit 추가)

### Sprint 4 — List Quality + Result Page (Topic 01 + Topic 02 + Topic 04 partial + K=10/50 loading)
- Topic 01: Katz-style RRF hybrid (tsvector + pgvector cosine) — `raw_query` 는 chat output 에서 이미 확보 (Section 3)
- Topic 02: Gemini setwise rerank at session end (`GEMINI_RERANK_ENABLED` flag)
- Topic 04: session-final DPP greedy MAP (`DPP_TOPK_ENABLED` flag), MMR λ ramp per-swipe
- Topic 06: adaptive k + soft-assignment relevance
- **Result page loading (NEW, audit)**: Initial K=10 primary + lazy-scroll 상위 50 까지. rank 11 직전에 divider + "더 많은 추천" heading. **Primary metric 분모는 10 고정**, 11-50 bookmark 는 Section 6 의 bookmark event 에서 `rank_zone` 필드로 secondary exploration signal 로 별도 로깅.

### Sprint 5+ — Strategic Items
- Topic 07 popularity-prior bridge (weight=0 default, opt-in only)
- Topic 08 multi-modal embedding coordination with Make DB
- Topic 05 bandits — only after N≥1K logged sessions with clear per-weight signal

---

## Outstanding User Decisions (post-audit status)

**Resolved on 2026-04-25 audit** (previously blocking):
- ~~C-3 MVP vs Better~~ → **Better (층 1+2+3)** 확정
- ~~Swipe per-swipe latency~~ → **<500ms per-swipe, <3-4s first-card** 확정
- ~~End state trigger~~ → **user-agency-first + 15 auto-stop cap + user "더 swipe" 로 동일 session_id 내 연장 가능** 확정
- ~~Top-K 크기~~ → **Initial K=10 primary + 상위 50 lazy-scroll** 확정
- ~~Like/Love 영속 저장~~ → **`liked_ids` 를 `list[{id, intensity}]` 구조로 migrate** 확정
- ~~Bookmark rate 수학 정의~~ → **bookmarks_on_top10 / 10 per session** 확정
- ~~Combined failure 처리~~ → **Section 5.7** (filter-only pool 상위 10 + notice) 신설

**Still blocking Sprint 3 구현** (user-side):
1. A-1 제스처 세부 (Sprint 3 frontend 작업 전 확정 필요)
2. B-1 빈도 + UI 디테일 (Sprint 3 구현 전)

**New open questions from audit** (non-blocking, 향후 spec 추가 결정 가능):
3. Session 간 신호 전이 (같은 project 여러 session `liked_ids` / `pref_vector` 이어쓰기 여부)
4. Empty-state UX (project 0개 상태 사용자 방문)
5. "그냥 random 보여줘" 메타 요청 처리

`research/spec/requirements.md` Section 10 에서 live tracking.

---

## Tasks to Update in `.claude/Task.md`

기존 RESEARCH-READY 마커 12개는 모두 유효 — 각 topic 의 research report 는 main terminal 이 구현 시 참조하는 근거 자료.

**Main terminal 의 권한**: task 분해 / sprint 편성 / 실행 순서 결정은 전적으로 main terminal 의 판단 영역. 이 문서의 Tier 분류와 Sprint 구성은 research terminal 의 **recommendation for consideration** 이지 execution mandate 가 아님. Main 이 자체 code-state 평가 후 계획을 세우고, 필요 시 이 문서의 그룹핑을 재구성하거나 무시할 수 있음.
