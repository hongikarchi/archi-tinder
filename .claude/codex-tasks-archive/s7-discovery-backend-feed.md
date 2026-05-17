# S7 Backend — Discovery Feed Endpoint + Taste Vector

## Slug
`s7-discovery-backend-feed`

## Decision Owner
Claude-main. Implement only the bounded task below.

## Goal
Ship `GET /api/v1/discovery/` — paginated taste-ranked or cold-start-random
building feed for the new Discovery tab. Also add the algorithm helper
`engine.compute_user_taste_vector` so the surprise endpoint (next commit) can
reuse it.

## Allowed Files
- `backend/apps/recommendation/views/discovery.py` (NEW)
- `backend/apps/recommendation/views/__init__.py` (EDIT — add re-export)
- `backend/apps/recommendation/urls.py` (EDIT — register path)
- `backend/apps/recommendation/engine.py` (APPEND ~60 LOC near end of file —
  do NOT touch existing helpers)
- `backend/apps/recommendation/tests/test_discovery.py` (NEW)

Anything else → stop and report `BACK-NEEDS-CLARIFICATION`.

## Inputs / Contracts

### Endpoint shape
`GET /api/v1/discovery/?cursor=<int>&limit=<int>` (trailing slash MANDATORY per CLAUDE.md).
- `IsAuthenticated`. Use `_get_profile(request)` from `views/_shared.py:29` (returns `UserProfile` or `None`).
- Query params:
  - `cursor` int ≥ 0, default 0. Treat as offset.
  - `limit` int 1-30, default 12.
  - Reject invalid values with `400 {"detail": "..."}`.
- Response 200:
  ```json
  {
    "cards": [ImageCard...],
    "next_cursor": <int|null>,
    "has_more": <bool>,
    "taste_state": "cold" | "warm"
  }
  ```
  - `next_cursor = cursor + len(cards)` if `has_more`, else `null`.
  - `taste_state = "cold"` if `compute_user_taste_vector` returned `None`, else `"warm"`.
- Card shape = whatever `engine._row_to_card(row)` produces (already used by
  other views; do NOT invent a new shape).

### Algorithm (live in `engine.py`)

Two new public helpers, **appended** to `engine.py`:

```python
def compute_user_taste_vector(profile):
    """
    Aggregate the user's taste signal as the mean embedding of every
    building_id appearing in any of their Projects' liked_ids.

    Reads:
      Project.objects.filter(user=profile).values_list('liked_ids', flat=True)
    where liked_ids is JSONField — list[{id: str, intensity: float}].

    Returns:
      numpy.ndarray shape (384,) normalized, OR None if the user has zero
      liked buildings or zero embeddings could be fetched.

    Notes:
      - intensity is honored as a multiplicative weight (default 1.0 if absent).
      - Use the existing get_pool_embeddings(building_ids) helper to fetch
        embeddings in one round-trip; missing rows are skipped.
      - normalize via the existing _normalize() helper.
    """
```

```python
def taste_ranked_page(v_taste, exclude_ids, limit, offset):
    """
    Cosine-rank the corpus against v_taste, skip exclude_ids, return one page.

    Returns list of card dicts (shape matches _row_to_card).

    SQL:
      WITH ranked AS (
        SELECT <cols>, embedding <=> %s::vector AS score
        FROM architecture_vectors
        WHERE building_id <> ALL(%s::text[])   -- empty list is fine
        ORDER BY embedding <=> %s::vector ASC
        OFFSET %s LIMIT %s
      )
      SELECT * FROM ranked

    Use _build_select_columns / _required_cols / _optional_cols patterns from
    get_diverse_random (engine.py:208-253). Use _vec_to_pg(v_taste) for the
    vector parameter. Wrap in try/except per IMP-7 cascade discipline; on
    pgvector failure, log a warning and return [].
    """
```

### View (`views/discovery.py`)

```python
class DiscoveryFeedView(APIView):
    """
    GET /api/v1/discovery/?cursor=&limit=

    Returns a taste-ranked or cold-start-random page of buildings for the
    Discovery tab. Cursor is integer offset; stable within a single tab
    visit but may reshuffle if the user likes new buildings via the Swipe
    tab in parallel (documented limitation).
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        ...
```

Algorithm:
1. Validate cursor + limit.
2. Resolve profile via `_get_profile`. Return 401 if None.
3. `v_taste = engine.compute_user_taste_vector(profile)`.
4. Build `exclude_ids` from `Project.objects.filter(user=profile)`:
   - all `liked_ids[*].id` (using `_liked_id_only` helper if present, else
     plain list comprehension extracting `.id`)
   - all `disliked_ids` (plain list[str])
   - all `saved_ids[*].id` (list[{id, saved_at}])
   - Deduplicate to a flat list[str].
5. If `v_taste is None`: `cards = engine.get_diverse_random(n=limit, filters=None)` then drop any whose `building_id` ∈ exclude_ids; if that drops below limit, do NOT refetch (cold-start is best-effort).
   - `taste_state = "cold"`, `has_more = False` (cold-start has no stable pagination), `next_cursor = None`.
6. Else: `cards = engine.taste_ranked_page(v_taste, exclude_ids, limit, offset=cursor)`.
   - `taste_state = "warm"`, `has_more = len(cards) == limit`, `next_cursor = cursor + len(cards) if has_more else None`.
7. Return Response with the 4-field JSON.

### urls.py
Add ONE path inside the existing urlpatterns list — alphabetical-ish near
`images/`:
```python
path('discovery/', DiscoveryFeedView.as_view()),
```
Import the new class at the top.

### views/__init__.py
Re-export `DiscoveryFeedView` in both the `from .discovery import ...` block
and the `__all__` list.

### Tests (`tests/test_discovery.py`)

Reuse fixtures from `tests/test_sessions.py` (or `conftest.py`) — particularly
authenticated client + profile factory. Test cases:

1. `test_cold_start_returns_random` — user with zero Projects → response has
   `taste_state == "cold"`, `len(cards) <= limit`, `has_more is False`.
2. `test_warm_returns_taste_ordered` — user with Project having ≥1 liked
   building → `taste_state == "warm"`, `len(cards) == limit` (assuming
   corpus has enough rows after exclusions), cards do NOT contain any
   liked/disliked/saved building_id.
3. `test_pagination_cursor_advances` — warm path; cursor=0 then cursor=12;
   no overlapping building_ids in the two pages.
4. `test_invalid_params_return_400` — cursor=-1 → 400; limit=999 → 400;
   limit=abc → 400.
5. `test_unauthenticated_returns_401`.

Use the existing test helper utilities for vector mocking if the corpus
fixture is small. If the corpus fixture is empty/minimal, mock
`engine.get_diverse_random` and `engine.taste_ranked_page` for the
exclusion + pagination tests; only one happy-path integration test needs
to hit real pgvector.

## Implementation Notes
- Trailing slashes on URL patterns — Django `APPEND_SLASH` only redirects GET.
- No new model, no migration, no `architecture_vectors` write.
- Do NOT edit `docs/algorithm.md` (admin-owned).
- Do NOT edit `docs/database-schema.md`.
- Re-use `_build_filter_sql`, `_build_select_columns`, `_dictfetchall`, `_row_to_card`, `_vec_to_pg`, `_normalize`, `get_pool_embeddings` from engine.py.
- Honor `RECOMMENDATION` settings but do NOT add new settings keys for v1 (limit/cursor defaults are hard-coded in the view).
- No print statements; use `logger = logging.getLogger('apps.recommendation')`.
- `compute_corpus_rank` (engine.py:1034) is NOT applicable here — it returns the rank of a single card, not a list. Use the pgvector pattern shown above.

## Verification
```bash
tools/back-validate.sh recommendation
```
Must pass flake8 + migrations + pytest (including new `test_discovery.py`).
Do NOT skip migrations.

## Handoff
On green → append to `.claude/Task.md`:
```
BACK-DONE: s7-discovery-backend-feed
```

On blocked → append (include grep / pytest excerpt):
```
BACK-BLOCKED: s7-discovery-backend-feed — <root cause + 1-2 line evidence>
```
