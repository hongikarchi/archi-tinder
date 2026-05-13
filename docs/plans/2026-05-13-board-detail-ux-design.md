# Board Detail Page — UX Design & 구현 완료
**Date:** 2026-05-13 (설계) / 2026-05-14 (구현)
**Branch:** feature/sns-profile-system
**Status:** Implemented ✅

---

## 목표

보드 상세 페이지(`/board/:id`)를 완성된 UX로 만든다.

---

## 최종 상태

```
BoardDetailPage (/board/:id)
│
├── 헤더 (커버 이미지 + 보드명 + 오너)       ✅
├── ❤️ Love this 버튼                         ✅
│
├── ── Buildings ──
│   └── 이미지 그리드 (liked_ids)             ✅
│       └── 클릭 → 전체화면 갤러리 오버레이   ✅
│
├── ── Recommended ──
│   └── 추천 건축물 그리드 (예측 결과)        ✅
│       └── 클릭 → 전체화면 갤러리 오버레이   ✅
│       └── liked보다 작은 그리드 (160px vs 260px)
│       └── liked 이미지 스크롤 후 하단에 표시
│       └── 세션이 없는 보드 → 섹션 숨김
│
└── [하단 탭바 없음]                          ✅
```

탭바: Library 탭 제거 → 3탭 (New / Swipe / Profile) ✅
프로필 보드 카드: 플립 애니메이션 제거 → 클릭 시 `/board/:id` 직접 이동 ✅

---

## 변경 파일

| 파일 | 변경 내용 |
|------|-----------|
| `frontend/src/pages/FavoritesPage.jsx` | ProjectCard 클릭 → `/board/:id` 직접 이동 |
| `frontend/src/layouts/MainLayout.jsx` | `/board/*` 경로에서 TabBar 미렌더링; FavoritesPage 블록 제거 |
| `frontend/src/pages/BoardDetailPage.jsx` | GalleryOverlay 연결, Recommended 섹션 추가 |
| `frontend/src/hooks/useBoard.js` | 세션 결과 병렬 fetch → `board.recommended` |
| `backend/apps/recommendation/serializers.py` | `latest_session_id` 필드 추가 |
| `frontend/src/components/TabBar.jsx` | Library(folders) 탭 제거 → 3탭 |
| `frontend/src/App.jsx` | `/library/*` → `/user/me` 리다이렉트; `onViewResults` → `/board/:id` |
| `frontend/src/components/profile/BoardCard.jsx` | 플립 애니메이션 제거 → onClick 시 `/board/:id` 이동 |

---

## 구현 상세

### 1. FavoritesPage.jsx — 보드 진입

```jsx
// 컴포넌트 props 단순화
export default function FavoritesPage({ projects }) {
  const navigate = useNavigate()

  // ProjectCard 클릭 → 직접 이동 (backendId 없으면 무시)
  onClick={() => project.backendId && navigate(`/board/${project.backendId}`)
}
```

### 2. MainLayout.jsx — 탭바 숨김 + FavoritesPage 제거

```jsx
const isBoard = pathname.startsWith('/board/')

{!isBoard && <TabBar swipeEnabled={!!activeProject} />}
```

FavoritesPage는 Outlet을 통해 라우팅되므로, 항상 마운트 패턴에서 제거.
라이브러리 관련 props (`onDeleteProject`, `onResumeProject`, `onGenerateReport`, `onImageGenerated`, `onToggleBookmark`, `projects`) 시그니처에서 제거.

### 3. BoardDetailPage.jsx — GalleryOverlay + Recommended

**컨테이너 높이:** 탭바 없으므로 `100vh` (기존: `calc(100vh - 64px)`)

**BuildingTile 클릭:**
```jsx
onClick={() => setSelectedBuilding({
  image_id: building.building_id,
  image_title: building.name_en,
  image_url: building.image_url,
  gallery: building.gallery || [],                    // extra photos + Divisare + drawings
  gallery_drawing_start: building.gallery_drawing_start ?? null,
})}
```

> **수정 이력:** 초기 구현에서 `gallery: []` 하드코딩 → "No additional images" 버그.
> `getBoardBuildings` → `_row_to_card`가 gallery를 이미 반환하므로 `building.gallery` 사용.

**Recommended 섹션:**
```jsx
const recommended = board?.recommended || []

{recommended.length > 0 && (
  <div style={{
    display: 'grid',
    gridTemplateColumns: 'repeat(auto-fill, minmax(160px, 1fr))',  // liked(260px)보다 작음
    gap: 12,
  }}>
    {recommended.slice(0, 10).map(card => (
      <RecommendedTile card={card} onClick={() => setSelectedBuilding(card)} />
    ))}
  </div>
)}
```

| 섹션 | minmax | 비고 |
|------|--------|------|
| Buildings (liked) | 260px | 대형 타일, 4:5 비율 |
| Recommended | 160px | 소형 타일, 3:4 비율 |

### 4. useBoard.js — 추천 데이터 fetch

```js
const [buildings, resultData] = await Promise.all([
  getBoardBuildings(buildingIds),
  project.latest_session_id
    ? getResult({ session_id: project.latest_session_id }).catch(() => null)
    : Promise.resolve(null),
])
const recommended = resultData?.predicted_like_images || []
setBoard(adaptProjectToBoard(project, buildings, recommended))
```

- 건물 fetch + 세션 결과 fetch **병렬** 처리
- 세션 결과 실패 시 조용히 무시 (추천은 optional)

### 5. serializers.py — latest_session_id

```python
latest_session_id = serializers.SerializerMethodField()

def get_latest_session_id(self, obj):
    # 세션 완료 여부 무관 — 보드에 세션이 있으면 추천 시도
    session = obj.sessions.order_by('-created_at').first()
    return str(session.session_id) if session else None
```

- 마이그레이션 불필요 (계산 필드)
- `AnalysisSession.related_name='sessions'` 활용

### 6. TabBar.jsx — Library 탭 제거

```jsx
// 제거: folders 아이콘, folders 탭, getActiveTab에서 /library 분기
const tabs = [
  { id: 'home', label: 'New', path: '/' },
  { id: 'swipe', label: 'Swipe', path: '/swipe' },
  { id: 'profile', label: 'Profile', path: '/user/me' },
]
```

### 7. App.jsx — Library 라우트 리다이렉트

```jsx
<Route path="library" element={<Navigate to="/user/me" replace />} />
<Route path="library/:folderId" element={<Navigate to="/user/me" replace />} />
```

`onViewResults` 콜백: `/library/${activeProjectId}` → `/board/${activeProjectId}`

### 8. BoardCard.jsx — 플립 제거, 직접 이동

```jsx
// isFlipped state 제거; isHovered 유지
onClick={() => navigate('/board/' + board.board_id)}
```

- 플립 애니메이션(back face, perspective, rotateY) 전면 제거
- hover lift(translateY(-4px)) 유지

---

## 데이터 흐름

```
ProfilePage (프로필 탭)
  └── BoardCard 클릭 → navigate('/board/:uuid')

FavoritesPage
  └── ProjectCard 클릭 → navigate('/board/:uuid')

BoardDetailPage (/board/:uuid)
  └── useBoard(boardId)
        ├── getProject(boardId)
        │     └── { liked_ids, saved_ids, latest_session_id, ... }
        │
        ├── [병렬]
        │   ├── getBoardBuildings(liked_ids + saved_ids)
        │   │     └── POST /images/batch/ → buildings (raw + gallery)
        │   │
        │   └── latest_session_id 있을 때:
        │       getResult({ session_id })
        │             └── predicted_like_images → board.recommended
        │
        └── board = { buildings, recommended, ... }

이미지 클릭 (liked or recommended)
  └── setSelectedBuilding(card)
        └── <GalleryOverlay fullscreen />
```

---

## 성공 기준

| 기준 | 상태 |
|------|------|
| 보드 카드 클릭 → `/board/:id` 진입 (프로필 + FavoritesPage) | ✅ |
| 진입 시 탭바 없음 | ✅ |
| 건물 이미지 클릭 → 전체화면 갤러리 (실제 이미지) | ✅ |
| liked 그리드 아래 Recommended 섹션 | ✅ |
| Recommended 그리드가 liked보다 작음 | ✅ |
| 세션 있는 보드 → 추천 표시, 세션 없는 보드 → 숨김 | ✅ |
| 건물 fetch + 세션 결과 fetch 병렬 처리 | ✅ |
| 탭바 3탭 (New / Swipe / Profile) | ✅ |
| Library 라우트 → `/user/me` 리다이렉트 | ✅ |
| ProfilePage 보드카드 플립 제거 → 직접 이동 | ✅ |

---

## 알려진 제한

- 건물에 R2 사진과 Divisare gallery 모두 없으면 GalleryOverlay "No additional images" — 데이터 문제, 프론트 이슈 아님
- 세션 결과 API는 `IsAuthenticated` 필요 — 비로그인 시 추천 섹션 없음 (의도된 동작)
