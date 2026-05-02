# Fix: Swipe Page Infinite Loading + Full Code Audit

## Context
User reports swipe page shows loading spinner and nothing works.
After 18 tasks across 6 phases, multiple changes have introduced regressions.
This plan addresses all critical issues found during code audit.

## Root Cause
**Primary:** `initSession()` in App.jsx has NO try-catch. Any backend error leaves
`isSwipeLoading=true` forever → infinite spinner. The recent timeout/retry logic (BE1)
means the frontend now properly throws on timeout, but `initSession` doesn't catch it.

**Secondary issues compounding the problem:**
- Centroid cache key collision (only hashes first 3 floats of 384-dim embedding)
- Missing `building_id` validation in SwipeView could corrupt session state
- `select_for_update()` inside long transaction could slow responses

---

## Fixes (ordered by impact)

### Fix 1: initSession error handling (CRITICAL)
**File:** `frontend/src/App.jsx` — `initSession()` (~line 162-192)

Wrap in try-catch-finally:
```javascript
async function initSession(projectId, filters, filterPriority, seedIds) {
  setIsSwipeLoading(true)
  setIsSessionCompleted(false)
  try {
    const result = await api.startSession({...})
    // ... existing state updates ...
  } catch (err) {
    setCurrentCard(null)
    setPrefetchCard(null)
    setPrefetchCard2(null)
    setSwipeError(err.message || 'Failed to start session')
  } finally {
    setIsSwipeLoading(false)
  }
}
```
Also: explicitly reset `setPrefetchCard2(null)` when not returned by backend.

### Fix 2: Centroid cache key collision (HIGH)
**File:** `backend/apps/recommendation/engine.py` — centroid cache (~line 457-462)

Current: `tuple(lv['embedding'][:3])` — only 3 of 384 dims → collisions guaranteed.
Fix: hash full embedding fingerprint:
```python
# Use hash of full embedding data for cache key
emb_hash = hash(tuple(
    (round(lv['embedding'][0], 6), round(lv['embedding'][-1], 6), len(lv['embedding']))
    for lv in like_vectors
))
cache_key = (emb_hash, len(like_vectors), round_num)
```
Or simpler: use first AND last 3 elements + length as fingerprint.

### Fix 3: building_id validation (HIGH)
**File:** `backend/apps/recommendation/views.py` — SwipeView.post (~line 239-244)

Add validation after extracting building_id:
```python
building_id = request.data.get('building_id')
action = request.data.get('action')

if not building_id:
    return Response({'detail': 'building_id is required'}, status=400)
if action not in ('like', 'dislike'):
    return Response({'detail': 'action must be like or dislike'}, status=400)
```

### Fix 4: Narrow select_for_update transaction scope (MEDIUM)
**File:** `backend/apps/recommendation/views.py` — SwipeView.post (~line 331-335)

Move prefetch calculation OUTSIDE the `transaction.atomic()` block.
The lock only needs to cover: read session → update exposed_ids → save session.
Prefetch computation doesn't need the lock.

```python
# Inside transaction: only session state update
with transaction.atomic():
    session = AnalysisSession.objects.select_for_update().get(...)
    # ... process swipe, update exposed_ids, determine next_card ...
    session.save(update_fields=[...])

# Outside transaction: calculate prefetch (no lock needed)
prefetch_card = engine.farthest_point_from_pool(...)
prefetch_card_2 = ...
```

### Fix 5: SwipePage loading priority (LOW)
**File:** `frontend/src/pages/SwipePage.jsx` — card rendering (~line 536-558)

If `currentCard` exists, show it even if `isLoading` is true (show a subtle loading
indicator instead of replacing the entire card with a spinner).

---

## Files to Modify
| File | Changes |
|------|---------|
| `frontend/src/App.jsx` | try-catch in initSession, reset prefetchCard2 |
| `frontend/src/pages/SwipePage.jsx` | Loading priority: card > spinner |
| `backend/apps/recommendation/engine.py` | Fix centroid cache key |
| `backend/apps/recommendation/views.py` | building_id validation, narrow transaction scope |

## Verification
1. Start backend: `cd backend && python3 manage.py runserver 8001`
2. Start frontend: `cd frontend && npm run dev`
3. Run backend tests: `cd backend && python3 -m pytest tests/ -v`
4. Web-tester: full swipe flow with 10+ swipes
5. Test error case: stop backend mid-session → frontend should show error, not infinite spinner
6. Test rapid swiping: 5 swipes in 2 seconds → no duplicates, no hangs
