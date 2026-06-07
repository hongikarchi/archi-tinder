# 사무소 추천 보드 — 설계 문서
작성: 2026-06-01 / 검토 반영: 2026-06-01

---

## 배경 및 결정 사항

**목표**: BoardDetailPage의 추천 건물 그리드 사이에 "추천 사무소(architect)" 섹션을 삽입.
사용자 취향과 연관된 건축가/사무소를 보드 건물 기반으로 추천.

**핵심 결정**: Office 테이블(현재 0개)을 우회하여 buildings DB의
`architect_canonical_ids` + `architect_names` 필드를 직접 활용.

### DB 현황
| 항목 | 상태 |
|------|------|
| `Office` 테이블 | 0개 (미싱크) |
| `OfficeProjectLink` | 0개 |
| `canonical_v2_buildings.architect_canonical_ids` | 36,864개 건물 100% 존재 (`arch_XXXXXX` 형식) |
| `canonical_v2_buildings.architect_names` | 36,864개 건물 100% 존재 |

---

## 전체 아키텍처

```
BoardDetailPage
  └── useBoard(projectId)
        ├── getProject()
        ├── getBoardBuildings()
        ├── getResult()                         ← 기존
        └── getRecommendedArchitects()          ← NEW

  Recommended 섹션
  ├── [건물카드 × 8] (4열 × 2행)
  ├── ArchitectSection (architect A)            ← NEW
  ├── [건물카드 × 8]
  ├── ArchitectSection (architect B)            ← NEW
  └── [나머지 건물카드]
```

**클릭 흐름**: ArchitectSection → 버튼 클릭 → `/architects/:architectId` → ArchitectProfilePage (NEW)

---

## 구현 범위 — 총 10개 파일

---

## 1. 백엔드 — 신규 endpoint

### 파일: `backend/apps/recommendation/views/office_recommendation.py` (신규)

**엔드포인트**: `GET /api/v1/projects/<uuid:pk>/recommended_architects/`

**로직**:
1. Project 조회 (소유자 또는 public 검증)
2. `project.saved_ids` + `project.liked_ids` → canonical_bld_id 목록
3. buildings DB 쿼리 — 보드 건물의 architect 집계:
   ```sql
   -- UNNEST로 모든 architect 집계 (협업 프로젝트의 두 번째 이후 architect 누락 방지)
   -- [0]만 쓰면 공동 설계 건물에서 두 번째 architect가 통째로 누락됨
   SELECT
       unnested_id AS architect_id,
       COUNT(*) AS cnt
   FROM canonical_v2_buildings,
        UNNEST(architect_canonical_ids) AS unnested_id
   WHERE canonical_bld_id = ANY(%(ids)s)
     AND is_publishable = true
   GROUP BY unnested_id
   ORDER BY cnt DESC
   LIMIT 3
   ```
4. 각 architect의 **다른 건물** (보드에 없는 것) 상위 5개 조회:
   ```sql
   SELECT canonical_bld_id, architect_names, cover_image_url_default,
          name, location_country, project_year
   FROM canonical_v2_buildings
   WHERE %(arch_id)s = ANY(architect_canonical_ids)
     AND canonical_bld_id != ALL(%(board_ids)s)
     AND is_publishable = true
   ORDER BY confidence_tier DESC, project_year DESC NULLS LAST
   LIMIT 5
   ```
5. `buildings` 가 빈 architect는 응답에서 제외
6. 응답 직렬화 후 반환

**응답 shape** (필드명 `canonical_bld_id` 로 통일):
```json
[
  {
    "architect_id": "arch_000042",
    "name": "Foster + Partners",
    "board_building_count": 3,
    "buildings": [
      {
        "canonical_bld_id": "bld_000123",
        "image_url": "https://...",
        "name_en": "Hearst Tower",
        "location_country": "US",
        "project_year": 2006
      }
    ]
  }
]
```

**에러 처리**:
- 보드 건물이 없으면 `[]` 반환
- architect_canonical_ids 가 빈 배열인 건물은 집계에서 자동 제외 (UNNEST 결과 없음)
- 해당 architect의 다른 건물이 없으면 해당 architect는 응답에서 제외

---

### 파일: `backend/apps/recommendation/urls.py` (수정)

```python
from django.urls import re_path

# arch_XXXXXX 패턴만 매칭 — 미래에 /architects/ 목록 endpoint 추가 시 충돌 방지
re_path(r'^architects/(?P<architect_id>arch_[0-9]{6})/$', ArchitectDetailView.as_view()),
path('projects/<uuid:pk>/recommended_architects/', RecommendedArchitectsView.as_view()),
```

---

### 파일: `backend/apps/recommendation/views/__init__.py` (수정)

`RecommendedArchitectsView`, `ArchitectDetailView` import 추가.

---

## 2. 백엔드 — Architect Profile endpoint

### 파일: `backend/apps/recommendation/views/office_recommendation.py` (위와 동일 파일)

**엔드포인트**: `GET /api/v1/architects/<arch_id>/`
URL 패턴 정규식 `arch_[0-9]{6}` 으로 제한되므로 view 내부 재검증 불필요.

**로직**:
1. buildings DB에서 해당 architect 건물 조회:
   ```sql
   SELECT canonical_bld_id, name, cover_image_url_default,
          architect_names, architect_canonical_ids,
          location_country, location_city, project_year, program
   FROM canonical_v2_buildings
   WHERE %(arch_id)s = ANY(architect_canonical_ids)
     AND is_publishable = true
   ORDER BY confidence_tier DESC, project_year DESC NULLS LAST
   LIMIT 50
   ```
2. architect_names: `architect_canonical_ids.index(arch_id)` 로 대응 이름 추출
3. 결과 0개 → 404 반환

**응답 shape**:
```json
{
  "architect_id": "arch_000042",
  "name": "Foster + Partners",
  "building_count": 77,
  "buildings": [
    { "canonical_bld_id": "...", "image_url": "...", "name_en": "...", ... }
  ]
}
```

**에러/엣지케이스**:
- `arch_id` 패턴은 URL 정규식에서 이미 제한 → view 내 추가 검증 불필요
- 건물 0개 → 404 (잘못된 architect_id 또는 publishable 건물 없음)

---

## 3. 프론트엔드 — API 함수

### 파일: `frontend/src/api/architects.js` (신규)

`profiles.js` 에 넣으면 architect가 "profile" 범주인지 어색하고, `projects.js` 와도 결이 다름.
architect 전용 파일로 분리:

```js
export async function getRecommendedArchitects(projectId) {
  // GET /projects/{projectId}/recommended_architects/
  // 실패 시 [] 반환 (추천 없음으로 graceful degradation — 보드 로드 블로킹 안 함)
}

export async function getArchitectProfile(architectId) {
  // GET /architects/{architectId}/
  // 404 → null 반환, 기타 에러는 throw
}
```

---

### 파일: `frontend/src/api/client.js` (수정)

`architects.js` re-export 추가:
```js
export { getRecommendedArchitects, getArchitectProfile } from './architects.js'
```

---

## 4. 프론트엔드 — useBoard hook

### 파일: `frontend/src/hooks/useBoard.js` (수정)

- `recommendedArchitects` state 추가 (초기값 `[]`)
- `getRecommendedArchitects(projectId)` 를 `getResult()` 와 **병렬** fetch
- 실패 시 빈 배열 fallback — 추천 섹션 미노출만, 보드 로드 영향 없음
- 반환값에 `recommendedArchitects` 추가

---

## 5. 프론트엔드 — BoardDetailPage

### 파일: `frontend/src/pages/BoardDetailPage.jsx` (수정)

**변경 내용**:
1. `recommendedArchitects` useBoard 에서 가져오기
2. 추천 그리드를 **4열 고정** (`gridTemplateColumns: 'repeat(4, 1fr)'`)으로 변경
3. 추천 카드 수 20개로 확대 (`recommended.slice(0, 20)`)
4. ArchitectSection 삽입 트리거:

```
추천 카드 수와 무관하게 항상 안정적으로 렌더되도록:
- 추천 카드 수 >= 1 이면, 전체 그리드를 8개 단위로 청크 분할
- 각 청크 뒤에 recommendedArchitects[chunkIndex] 삽입 (있을 때만)
- 예: 카드 10개 → [0..7] → ArchitectSection[0] → [8..9] → ArchitectSection[1] (있으면)
- 예: 카드 3개  → [0..2] → ArchitectSection[0] (있으면)  ← 16개 미만에도 렌더됨
```

**ArchitectSection 컴포넌트**: `frontend/src/pages/boardDetail/ArchitectSection.jsx` (신규)

```
┌──────────────────────────────────────────┐
│ 추천 사무소 (소문자 라벨)                   │
│ Foster + Partners          [프로필 →]     │
│ ─────────────────────────────────────     │
│ [건물1][건물2][건물3][건물4][건물5] →       │
│  (가로 스크롤, hide-scrollbar)             │
└──────────────────────────────────────────┘
```

- 건물 카드 클릭 → `/buildings/:canonical_bld_id`
- [프로필 →] 클릭 → `/architects/:architectId`
- `recommendedArchitects` 빈 배열이면 섹션 렌더 안 함

---

## 6. 프론트엔드 — ArchitectProfilePage (신규)

### 파일: `frontend/src/pages/ArchitectProfilePage.jsx` (신규)

**라우트**: `/architects/:architectId`

**UI 상태 처리 (명시)**:
| 상태 | UI |
|------|----|
| 로딩 중 | 스켈레톤 shimmer (헤더 + 그리드) |
| 정상 | 사무소명 + 건물 수 + 건물 그리드 |
| 404 / 건물 0개 | "사무소 정보를 찾을 수 없어요" 메시지 |
| 네트워크 에러 | "불러오는 데 실패했어요. 다시 시도해주세요." |

**UI 구조** (FirmProfilePage 유사):
- 상단 헤더: 사무소명 + 건물 수 배지
- 건물 그리드: `getArchitectProfile(architectId).buildings` 카드 표시 (2열 또는 3열)
- 건물 카드 클릭 → `/buildings/:canonical_bld_id`
- 뒤로가기 버튼

### 파일: `frontend/src/App.jsx` (수정)

라우트 추가:
```jsx
<Route path="/architects/:architectId" element={<ArchitectProfilePage />} />
```

---

## 수정 파일 요약

| 파일 | 변경 유형 | 비고 |
|------|----------|------|
| `backend/apps/recommendation/views/office_recommendation.py` | 신규 | 두 view 클래스 포함 |
| `backend/apps/recommendation/views/__init__.py` | 수정 | import 2개 추가 |
| `backend/apps/recommendation/urls.py` | 수정 | re_path 포함 경로 2개 추가 |
| `frontend/src/api/architects.js` | 신규 | profiles.js 대신 분리 |
| `frontend/src/api/client.js` | 수정 | re-export 추가 |
| `frontend/src/hooks/useBoard.js` | 수정 | 병렬 fetch + 반환값 |
| `frontend/src/pages/BoardDetailPage.jsx` | 수정 | 그리드 + ArchitectSection 슬롯 |
| `frontend/src/pages/boardDetail/ArchitectSection.jsx` | 신규 | 가로 스크롤 섹션 |
| `frontend/src/pages/ArchitectProfilePage.jsx` | 신규 | 로딩/에러/빈 상태 포함 |
| `frontend/src/App.jsx` | 수정 | 라우트 추가 |

총 **10개 파일** (신규 4 + 수정 6)

---

## 성능 고려사항

- 추천 architects endpoint: UNNEST + GROUP BY 는 `WHERE canonical_bld_id = ANY(%(ids)s)` 가
  먼저 적용되므로 보드 건물 수(통상 수십 개)만 스캔 — 전체 36,864행 스캔 아님.
  단, 이 선택성이 인덱스에 의존하므로 **back-maker 구현 시 아래를 반드시 확인할 것**:
  ```sql
  -- buildings DB에서 실행 (읽기 전용 연결로도 가능)
  SELECT indexname FROM pg_indexes
  WHERE tablename = 'canonical_v2_buildings'
    AND indexdef ILIKE '%canonical_bld_id%';
  -- 결과 없으면 DDL 권한 계정으로:
  CREATE INDEX IF NOT EXISTS idx_cvb_canonical_bld_id
    ON canonical_v2_buildings (canonical_bld_id);
  -- buildings DB는 Make-DB 소유 → ORM migrate 금지, psql로 직접 실행
  ```
- 최대 3개 architect × 5개 건물 = 15행 → 빠름
- `getRecommendedArchitects` 보드 로드와 병렬, 실패해도 보드 무영향
- ArchitectProfilePage: 최대 50개 건물 단건 쿼리

---

## 검토 반영 내역 (2026-06-01)

1. **architect 집계**: `[0]` 인덱스 → `UNNEST` 로 변경 (협업 프로젝트 누락 방지)
2. **URL 충돌 방지**: `<str:architect_id>` → `re_path(r'arch_[0-9]{6}')` 정규식 제한
3. **ArchitectSection 삽입 트리거**: "16번째 카드 뒤" → "8개 단위 청크, 카드 수 무관하게 항상 렌더"
4. **ArchitectProfilePage 상태 처리**: 로딩/404/에러/빈 상태 명시
5. **API 파일 분리**: `profiles.js` → `architects.js` 신규 파일로 분리
6. **필드명 통일**: `image_id` → `canonical_bld_id`
7. **인덱스 확인 지시**: `canonical_bld_id` 인덱스 존재 여부 확인 후 없으면 추가 — back-maker 구현 지시사항에 명시

---

## 미포함 (추후 고려)

- 팔로우/팔로워 기능 (Office 테이블 싱크 후 연결)
- 취향 벡터 기반 architect 가중치 (현재는 UNNEST 빈도 집계)
- architect_id가 없는 건물의 집계 처리 (현재 제외)
