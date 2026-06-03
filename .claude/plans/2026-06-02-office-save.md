# Office 싱크 및 사무소 저장 기능 — 설계 문서
작성: 2026-06-02 / 브랜치: feature/office-save

---

## 배경 및 결정 사항

**목표**: Make-DB의 `canonical_v2_architects` 데이터를 앱 DB `Office` 테이블에 싱크해서
유저가 사무소를 저장(save)할 수 있게 만들기.

**핵심 결정**: Office 테이블이 기존에 있었으나 레코드 0개(Make-DB 싱크 미완료).
`canonical_v2_architects`는 buildings DB에 14,216개 사무소(recommendable 4,357개) 완비 상태.
→ 읽기 전용 buildings DB를 직접 쓸 수 없으므로 앱 DB Office 테이블에 싱크 후 사용자 행동 저장.

### DB 현황
| 항목 | 상태 |
|------|------|
| `Office` 테이블 (앱 DB) | 싱크 후 3,277개 (recommendable) |
| `canonical_v2_architects` (buildings DB) | 14,216개 전체, 4,357개 recommendable |
| `SavedOffice` 테이블 | 신규 생성 |

---

## 전체 아키텍처

```
buildings DB
  canonical_v2_architects (read-only)
        ↓ python manage.py sync_offices
앱 DB
  Office 테이블 (canonical_id = arch_XXXXXX 기준 upsert)
        ↓
  SavedOffice (user ↔ office)
        ↓
  API endpoints
    POST   /api/v1/offices/<arch_id>/save/
    DELETE /api/v1/offices/<arch_id>/save/
    GET    /api/v1/offices/saved/
```

---

## 구현 범위 — 총 8개 파일

---

## 1. 모델 변경 (`backend/apps/profiles/models.py`)

### Office 모델 변경
| 필드 | 변경 내용 |
|------|-----------|
| `canonical_id` | `IntegerField` → `TextField(unique=True)` |
| `primary_city` | 신규 추가 (TextField, blank) |
| `primary_country` | 신규 추가 (TextField, blank) |
| `is_recommendable` | 신규 추가 (BooleanField, default=False) |

기존 필드 (`name`, `logo_url`, `description`, `website`, `contact_email` 등) 변경 없음.

### SavedOffice 모델 신규
```python
class SavedOffice(models.Model):
    user    = ForeignKey(settings.AUTH_USER_MODEL, related_name='saved_offices')
    office  = ForeignKey(Office, related_name='saved_by')
    saved_at = DateTimeField(auto_now_add=True)
    class Meta:
        unique_together = [('user', 'office')]
```

### 마이그레이션
- `0003_office_is_recommendable_office_primary_city_and_more` — 필드 추가 + SavedOffice 생성
- `0004_alter_office_canonical_id` — canonical_id unique 제약 (중복 326개 수동 제거 후 적용)

---

## 2. 싱크 커맨드 (`backend/apps/profiles/management/commands/sync_offices.py`)

**실행**: `python manage.py sync_offices`

**로직**:
1. `connections['buildings']`로 `canonical_v2_architects WHERE is_recommendable=true` 전체 fetch
2. `canonical_id` 기준 `update_or_create` upsert
3. `.save(update_fields=...)` — admin 관리 필드(`verified`, `claim_status` 등) 덮어쓰기 방지
4. 완료 시 created/updated 건수 출력

**주의**: 여러 번 실행해도 안전. canonical_id unique 제약으로 중복 방지.

---

## 3. 엔드포인트 (`backend/apps/profiles/views.py`, `urls.py`)

### POST `/api/v1/offices/<arch_id>/save/`
- Auth required (IsAuthenticated)
- `get_or_create(user, office)` — 신규 201, 이미 저장된 경우 200
- Response: `{"saved": true}`

### DELETE `/api/v1/offices/<arch_id>/save/`
- Auth required
- `filter(user, office).delete()`
- Response: `{"saved": false}` 200

### GET `/api/v1/offices/saved/`
- Auth required
- 내가 저장한 사무소 목록 반환 (`saved_at` 역순)
- Response: `[{canonical_id, name, logo_url, primary_city, primary_country, saved_at}]`

**URL 패턴**: `re_path(r'^offices/(?P<canonical_id>arch_[0-9]{6})/save/$')` — arch_XXXXXX 형식만 매칭.
`offices/saved/`는 `offices/<canonical_id>/save/` 보다 앞에 선언 (라우팅 충돌 방지).

---

## 성능 고려사항

- `sync_offices` 1회 실행: 4,357개 upsert — 주기적 재실행 권장 (Make-DB 업데이트 시)
- `SavedOffice` 조회: `select_related('office')` + `user` 인덱스로 충분
- `canonical_id unique` 인덱스: `get_object_or_404` MultipleObjectsReturned 방지

---

## 미포함 (추후 고려)

- OfficeProjectLink 싱크 (현재 0개 — 건물 목록은 buildings DB 직접 쿼리로 대체)
- OfficeFollow (팔로우/팔로워) — SavedOffice와 별도 기능, SOC1 Phase 15에서 예정
- 사무소 프로필 페이지 프론트엔드 연결
- 저장된 사무소 수 배지 (UserProfile.saved_office_count 카운터 캐시)
