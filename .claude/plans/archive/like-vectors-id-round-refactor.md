# like_vectors 구조 개선 — 세션엔 {id, round}만, 임베딩은 hydrate

## 배경 (측정으로 확정)
취향 스와이프 후반 느려짐의 원인은 세션 `AnalysisSession.like_vectors`(JSONField, `[{embedding:[384 floats], round}]`)가 like마다 누적되어 **매 스와이프 원격 Neon에서 전체 읽기+쓰기**(O(n)). 계측 분해 결과:
- `deser~` ≈ 2ms (역직렬화 무죄)
- `lockwait` ≈ 900ms 일정 (= BEGIN + SELECT FOR UPDATE 원격 왕복; 로컬 전용 아티팩트)
- `load` 87ms→650ms (bytes 2→92940에 비례) = **원격 전송이 증가 주범**
프로덕션(Railway↔Neon 동일 리전)에선 증폭 작음. 로컬 개발 체감 + DB IO + prod tail 개선 목적.

## 결정 (사용자 승인 2026-06-29→07-01)
**Option B**: 세션 `like_vectors`에 `{id: canonical_bld_id, round}`만 저장(≈20B/entry). 임베딩은 hydrate 헬퍼로 복원(불변·사전계산·like 시점 보유).

## 설계
### 1. shape 변경 (쓰기 3지점)
- `services/swipe_service.py:738` — `session.like_vectors + [{'id': canonical_bld_id, 'round': session.current_round}]`; 동시에 이미 손에 있는 `embedding`을 embedding-cache에 set.
- `services/session_service.py:~423` (seed) — `{'id': bid, 'round': 0}` + cache set.
- `views/discovery.py:~423` (discovery seed) — `{'id': bid, 'round': i}` + cache set.

### 2. hydration 헬퍼 (신규)
`hydrate_like_vectors(session) -> list[{'embedding': [...], 'round': int}]`:
- 각 entry: `embedding` 키 있으면(구-데이터) 그대로; `id` 키면 캐시/DB에서 임베딩 조회.
- 임베딩 출처: **Django cache** (`from django.core.cache import cache`, Redis prod / LocMem local — INFRA-REDIS-1). 키 네임스페이스 예 `emb:v2:{canonical_bld_id}`, 장기 TTL(불변).
- miss → buildings DB 배치 조회(`connections['buildings']`, canonical_v2_buildings.embedding, `is_publishable` 게이트 불필요 — 이미 노출된 카드) → `cache.set_many`.
- like 시점에 cache.set 하므로 정상 흐름은 항상 히트; resume(cold)만 1회 배치 조회.
- **round 순서/개수 보존** 필수(최신성 가중이 round 사용).

### 3. 소비처 교체 (~12곳; `session.like_vectors` → `hydrate_like_vectors(session)`)
(a) 전체 벡터 필요 → hydrate 경유:
- `swipe_service.py` 수렴추적(~762), MMR(~607/867/890/945), extend(~592), prefetch(`compute_sync_prefetch` saved_like_vectors ~1154)
- `session_service.py` result/extend(~494/519/555/578/657/662)
- `engine.py` compute_taste_centroids/compute_mmr_next/get_top_k_mmr/compute_dpp_topk — **시그니처 불변**(호출자가 hydrate해서 전달)
- `caches.py` 디스커버리 피드(~363, 자체 구성이면 무변경)
(c) 개수만 → **무변경**(`len(session.like_vectors)` = 길이 동일): `views/_shared.py:34`, `serializers.py` `_latest_like_count`/`_like_count`, `session_service.py:117` resume-log.
- 리포트(`generation.py`)는 like_vectors 미사용 → 무관.

### 4. 마이그레이션
- **스키마 마이그레이션 없음**(JSONField shape 변경). 헬퍼가 양쪽 shape 처리 → 기존 세션 무중단, 데이터 백필 불필요.

### 5. 테스트
- 회귀: centroid/MMR/수렴 Δv/result/resume가 hydrate 전후 **동일 결과**.
- 단위: hydrate 히트/미스/양쪽-shape 혼재/round 보존/빈 리스트.
- 실-PG(인라인 DB 변수) + flake8. app-test FEATURE-SCOPED(스와이프 경로).

## 리스크
- R1 캐시 미스 폭주(prod 멀티워커 프로세스별 LocMem이면): Redis 사용으로 공유. 로컬 LocMem은 단일 프로세스라 무방.
- R2 round 순서 붕괴 → 최신성 가중 오류: hydrate가 입력 순서/round 그대로 유지.
- R3 buildings DB 임베딩 컬럼 조회 헬퍼 재사용(엔진 pool_embeddings fetch와 동일 경로) — 신규 쿼리는 배치 IN.
- R4 구-shape 세션과 신-shape 혼재 entry: 헬퍼가 entry별 분기.

## Git
브랜치 `feature/algo-taste-llm` 위 새 커밋. 구현=orchestrate(feature workflow: back-maker→code-review+security→opus verify→fix loop). 커밋/푸시는 별도 승인(publish gate).
