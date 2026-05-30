# Plan: Taste 탭 질문 카드 삽입 — ALGO-QCARD-1

## 한국어 요약

스와이프 세션 중 특정 조건에서 일반 스와이프 카드 대신 A/B 선택 질문 카드를 삽입.
백엔드에서 태그 카운팅 + 트리거 판정 → 스와이프 응답에 `question_trigger` 포함 → 프론트 렌더.
답변은 서버에 `SessionEvent(tag_answer)` 로 기록 (MVP: 추천 풀 즉시 반영 없음).

## Trigger Spec

### Refine trigger (like 시, cooldown=0)
- **조건 A (연속 교집합)**: `recent_like_tag_sets` 최근 3개 항목의 교집합이 존재 (전체 like ≥ 3 이후부터 체크)
- **조건 B (비중 70%)**: `tag_axis_counts` 전체에서 단일 태그가 총 like 수의 ≥ 70%
- 두 조건 중 하나라도 만족 + cooldown=0 → 트리거
- 축 우선순위: `tag_axis_counts`에서 비중이 가장 높은 axis 선택

### Refresh trigger (dislike 시, cooldown=0)
- `q_card_consecutive_dislikes` ≥ 4

### Cooldown
- 트리거 발동, 답변(A/B), 스킵 → 모두 `question_cooldown = 5`
- 스와이프마다 `question_cooldown -= 1` (최솟값 0)
- 질문 응답/스킵 시 → `q_card_consecutive_dislikes = 0` 리셋 (refine 트리거는 리셋 안 함)

## PR Plan

이 plan은 1개 PR (feature/algo-question-card → develop) 를 승인한다.

---

## Back-maker spec

### 1. models.py — AnalysisSession에 4개 필드 추가

```python
# 태그 카운팅 (question card trigger)
tag_axis_counts        = models.JSONField(default=dict)
# {"style": {"minimal": 3}, "atmosphere": {"warm": 4}, "material_visual": {"wood": 3}}
# 각 like 시 buildings DB에서 style[], atmosphere[], material_visual[] 조회해 업데이트

recent_like_tag_sets   = models.JSONField(default=list)
# 최근 3장의 liked card 태그 배열: [["minimal","warm","wood"], ...]
# like 시 append, len > 3 이면 oldest 제거. 교집합 체크용.

question_cooldown      = models.IntegerField(default=0)
# 스와이프마다 -1, 트리거/답변/스킵 시 5로 세팅

q_card_consecutive_dislikes = models.IntegerField(default=0)
# dislike마다 +1, like or 답변/스킵 시 0 리셋
```

### 2. Migration 0020
파일명: `0020_question_card_fields.py`
4개 필드만 `AddField`. 기존 데이터 backfill 불필요 (default 값 사용).

### 3. views/swipe.py — SwipeView.post 내 trigger 로직 추가

SwipeView.post 내에서 swipe 기록 직후:

**A. 세션 필드 업데이트 헬퍼 `_update_question_state(session, action, bld_id)`**

```python
AXIS_FIELDS = ['style', 'atmosphere', 'material_visual']

AXIS_QUESTIONS = {
    'atmosphere':      {'q': '어떤 분위기에 더 끌리세요?',      'a': '따뜻하고 아늑한',     'b': '차갑고 절제된'},
    'material_visual': {'q': '재료감은 어느 쪽이 더 끌리세요?',  'a': '나무·돌 같은 자연재료', 'b': '콘크리트·유리 같은 인공재료'},
    'style':           {'q': '디자인 방향은 어느 쪽이 더 끌리세요?', 'a': '간결하고 미니멀한',   'b': '풍부하고 디테일한'},
}

REFRESH_QUESTION = {
    'q': '마음에 드는 건물이 잘 없었네요.',
    'a': '더 다양한 유형 보여줘',
    'b': '지금 타입으로 계속',
}
```

- `action == 'like'`:
  1. buildings DB (`connections['buildings']`) 로 `style`, `atmosphere`, `material_visual` 조회
  2. 각 axis별 태그 카운트 업데이트 → `tag_axis_counts`
  3. 현재 카드의 모든 태그 합쳐서 `recent_like_tag_sets` 에 append, len > 3 이면 pop(0)
  4. `q_card_consecutive_dislikes = 0`
  5. cooldown -= 1 (최솟값 0)

- `action == 'dislike'`:
  1. `q_card_consecutive_dislikes += 1`
  2. cooldown -= 1 (최솟값 0)

**B. 트리거 체크 `_check_question_trigger(session)` → dict or None**

```
cooldown > 0 → None

# Refresh check
if q_card_consecutive_dislikes >= 4:
    question_cooldown = 5
    return {'type': 'refresh', 'axis': None, ...REFRESH_QUESTION}

# Refine check (like action only, total_likes >= 3)
total_likes = sum of all tag_axis_counts values across all axes / 3  (average proxy)
  실제: sum(sum(v.values()) for v in tag_axis_counts.values()) / len(AXIS_FIELDS)
  더 간단: 세션의 like_vectors 길이로 total_likes 대체 가능

# 조건 A: 최근 3개 like 교집합
if len(recent_like_tag_sets) == 3:
    intersection = set(recent_like_tag_sets[0]) & set(recent_like_tag_sets[1]) & set(recent_like_tag_sets[2])
    if intersection:
        winning_axis = axis_with_highest_proportion(tag_axis_counts, intersection)
        question_cooldown = 5
        return build_refine_trigger(winning_axis)

# 조건 B: 특정 태그 비중 ≥ 70%
total_count = sum(sum(v.values()) for v in tag_axis_counts.values())
if total_count >= 3:
    for axis, counts in tag_axis_counts.items():
        for tag, cnt in counts.items():
            if cnt / total_count >= 0.70:
                question_cooldown = 5
                return build_refine_trigger(axis)

return None
```

`axis_with_highest_proportion`: 교집합 태그 중 자신의 axis count 비율이 가장 높은 axis 반환.

**C. SwipeView.post 응답에 `question_trigger` 필드 추가**

```python
question_trigger = _check_question_trigger(session) if action in ('like', 'dislike') else None
# ... 기존 response dict에:
'question_trigger': question_trigger,
```

`update_fields` 에 4개 신규 필드 추가.

### 4. views/swipe.py — QuestionResponseView (새 클래스)

```
POST /analysis/sessions/<uuid:session_id>/question-responses/
인증 필요

Request body:
  question_type: "refine" | "refresh"
  axis: str | null
  selected_option: "A" | "B" | "skip"

동작:
  1. 세션 조회 + select_for_update
  2. SessionEvent(event_type='tag_answer', payload={...}) 생성
  3. session.question_cooldown = 5
  4. session.q_card_consecutive_dislikes = 0
  5. session.save(update_fields=['question_cooldown', 'q_card_consecutive_dislikes'])
  6. 200 { "accepted": true }
```

### 5. urls.py

```python
path('analysis/sessions/<uuid:session_id>/question-responses/', QuestionResponseView.as_view()),
```

### 6. views/__init__.py

`QuestionResponseView` import 추가.

---

## Front-maker spec

### 1. api/sessions.js — recordSwipe() 응답에 question_trigger pass-through

`recordSwipe()` 반환 객체에 `question_trigger: result.question_trigger ?? null` 추가.

```js
export async function submitQuestionResponse({ session_id, question_type, axis, selected_option }) {
  return await callApi('POST', `/analysis/sessions/${session_id}/question-responses/`, {
    question_type, axis, selected_option,
  })
}
```

`client.js` barrel에 `submitQuestionResponse` export 추가.

### 2. QuestionCard.jsx (신규 컴포넌트)

파일: `frontend/src/components/QuestionCard.jsx`

```
Props:
  trigger: { type, axis, question, option_a, option_b }
  onAnswer(option: "A" | "B" | "skip")

크기: CARD_WIDTH × CARD_HEIGHT (SwipeCard와 동일)
레이아웃:
  - 배경: var(--color-surface), border-radius: 20, border: 1px solid var(--color-border)
  - boxShadow: '0 25px 50px rgba(0,0,0,0.4)'
  - 상단 badge: "지금 취향을 파악하고 있어요" (작은 텍스트, --color-text-dim)
  - 중앙: 질문 텍스트 (fontSize 18, fontWeight 700)
  - 하단: A버튼, B버튼 (전체 너비, 세로 배치, gap 8)
    A버튼: background var(--color-surface-2), border 1px solid var(--color-border)
    B버튼: 동일
  - 최하단: "건너뛰기" 텍스트 버튼 (color-text-dim, fontSize 12)
```

### 3. SwipePage.jsx — questionTrigger prop 수신 + QuestionCard 렌더

새 props:
```js
questionTrigger = null,    // { type, axis, question, option_a, option_b } | null
onQuestionAnswer,          // (option: "A"|"B"|"skip") => void
```

렌더 로직:
- `questionTrigger`가 non-null이면 TinderCard + SwipeCard 대신 `<QuestionCard>` 렌더
- QuestionCard의 `onAnswer` → `onQuestionAnswer(option)` 호출
- keyboard 이벤트 guard: `questionTrigger`가 있으면 arrow key 무시

### 4. MainLayout.jsx — props pass-through

`questionTrigger`, `onQuestionAnswer` props 추가 후 SwipePage에 전달.

### 5. App.jsx — state + handler

```js
const [pendingQuestion, setPendingQuestion] = useState(null)

// handleSwipeCard (recordSwipe 응답 처리) 에 추가:
if (result.question_trigger) {
  setPendingQuestion(result.question_trigger)
}

async function handleQuestionAnswer(option) {
  setPendingQuestion(null)
  await api.submitQuestionResponse({
    session_id: activeSession.session_id,
    question_type: pendingQuestion.type,
    axis: pendingQuestion.axis ?? null,
    selected_option: option,
  }).catch(() => {})  // fire-and-forget
}
```

MainLayout 호출 시 `questionTrigger={pendingQuestion}`, `onQuestionAnswer={handleQuestionAnswer}` 추가.

---

## Acceptance criteria (code-review 체크리스트)

- [ ] 4개 필드 migration 생성 + apply
- [ ] SwipeView 응답에 `question_trigger` 항상 포함 (null 또는 객체)
- [ ] cooldown 5 → 스와이프마다 -1 로직 동작
- [ ] 연속 like 교집합 조건 (3장) + 70% 비중 조건 둘 다 체크
- [ ] QuestionResponseView: SessionEvent(tag_answer) 생성 + cooldown/consecutive 리셋
- [ ] QuestionCard: CARD_WIDTH × CARD_HEIGHT 동일 크기
- [ ] 키보드 스와이프 비활성화 (questionTrigger 있을 때)
- [ ] submitQuestionResponse fire-and-forget (에러 무시)
