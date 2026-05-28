# Liked Projects Tab — Design

**Branch**: `feature/sns-liked-projects-tab`
**Date**: 2026-05-28

## 목표

Discovery 탭 스와이프 인터랙션 변경 + 프로필 탭 Liked Projects 서브 화면 추가.

## 확정된 설계

### 백엔드

1. `UserProfile.liked_building_ids = JSONField(default=list)` — `canonical_bld_id` 문자열 리스트
2. 마이그레이션 1개
3. `POST /api/v1/liked-buildings/` — body: `{ "canonical_bld_id": "bld_000123" }` → liked_building_ids에 추가 (중복 무시), 200 반환
4. `GET /api/v1/liked-buildings/` — liked_building_ids로 건물 카드 batch fetch 후 반환

### 프론트엔드

#### DiscoveryPage
- 오른쪽 스와이프 → `POST /liked-buildings/` 자동 호출 (SaveToBoardModal 제거)
- **400ms 롱프레스** → 기존 `SaveToBoardModal` 표시 (특정 보드에 저장)

#### 롱프레스 핸들러
- `onTouchStart` 시 400ms 타이머 시작
- `onTouchEnd` / `onTouchMove`(임계값 초과) 시 타이머 취소
- 카드가 스와이프 동작으로 넘어가지 않도록 타이머 취소 조건 처리

#### 프로필 탭 (UserProfilePage)
- 기존 "Curated Boards" 섹션 **옆에** "Liked Projects" 진입 버튼 추가
- 클릭 → `LikedProjectsPage`로 이동 (새 라우트 `/liked-projects`)

#### LikedProjectsPage (신규)
- `GET /liked-buildings/` 호출
- 건물 이미지 그리드 (기존 보드 디테일 그리드 스타일 참고)
- 카드 클릭 → `BuildingDetailPage`로 이동

## API 스펙

```
POST /api/v1/liked-buildings/
Authorization: Bearer <token>
Body: { "canonical_bld_id": "bld_000123" }
Response 200: { "liked_count": 5 }

GET /api/v1/liked-buildings/
Authorization: Bearer <token>
Response 200: { "buildings": [ ...card objects... ], "total": 5 }
```

## 변경 파일 예상

**Backend**
- `apps/accounts/models.py` — UserProfile에 liked_building_ids 추가
- `apps/accounts/migrations/xxxx_liked_building_ids.py` — 신규
- `apps/accounts/views.py` 또는 신규 `apps/accounts/views/liked_buildings.py`
- `apps/accounts/urls.py` — 새 엔드포인트 등록

**Frontend**
- `src/pages/DiscoveryPage.jsx` — 스와이프 핸들러 + 롱프레스
- `src/pages/LikedProjectsPage.jsx` — 신규
- `src/pages/UserProfilePage.jsx` — Liked Projects 진입 버튼
- `src/api/client.js` 또는 `src/api/likedBuildings.js` — API 함수
- `src/App.jsx` — `/liked-projects` 라우트 등록
