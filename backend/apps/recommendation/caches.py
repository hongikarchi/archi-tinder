"""TTL caches for recommendation engine."""

import numpy as np
from django.core.cache import cache

from . import engine

TASTE_TTL = 300  # seconds — 5-minute freshness window
PROJECTS_LIST_TTL = 60  # seconds — UX-acceptable staleness window


def _taste_key(profile_id):
    return f"taste:{profile_id}"


def get_or_build_taste(profile):
    """Cached wrapper around engine.compute_user_taste_vector.

    Returns np.ndarray (float32) or None.

    Cache stores float32 bytes; deserialized on hit. Cold path = original
    compute + 5-min cache. Using float32 (vs engine's float64) is precision-
    by-design: cosine similarity ranking is insensitive to the 32→64-bit
    difference and halves the serialized payload size.

    Invalidation: call evict_taste(profile.id) whenever liked_ids changes.
    None is never cached (no cache poisoning on cold-start / empty-likes).
    """
    key = _taste_key(profile.id)
    raw = cache.get(key)
    if raw is not None:
        # np.frombuffer returns read-only; callers that need mutation must copy.
        return np.frombuffer(raw, dtype=np.float32)
    vec = engine.compute_user_taste_vector(profile)
    if vec is None:
        return None
    arr = np.asarray(vec, dtype=np.float32)
    cache.set(key, arr.tobytes(), TASTE_TTL)
    return arr


def evict_taste(profile_id):
    """Immediately invalidate the cached taste vector for a UserProfile PK."""
    cache.delete(_taste_key(profile_id))


# ── Projects list cache ───────────────────────────────────────────────────────

def _projects_list_key(profile_id, page, page_size):
    return f"projects_list:{profile_id}:p{page}:ps{page_size}"


def get_or_build_projects_list(profile, page, page_size, builder):
    """Cached wrapper around the projects-list response payload.

    `builder` is a zero-arg callable that returns the response dict
    {results, total, page, has_more}. Result is cached per
    (profile_id, page, page_size) for PROJECTS_LIST_TTL seconds.
    """
    key = _projects_list_key(profile.id, page, page_size)
    cached = cache.get(key)
    if cached is not None:
        return cached
    data = builder()
    cache.set(key, data, PROJECTS_LIST_TTL)
    return data


def evict_projects_list(profile_id):
    """Invalidate the canonical page-1 cache entry for a profile.

    Other page sizes / pages will self-expire via the TTL. The canonical
    page (page=1, page_size=50) covers the App.jsx default fetch.
    """
    cache.delete(_projects_list_key(profile_id, 1, 50))
    # Also evict common page_size variants to be safe
    for ps in (10, 20, 25):
        cache.delete(_projects_list_key(profile_id, 1, ps))


# ── User profile detail cache ────────────────────────────────────────────────

PROFILE_DETAIL_TTL = 60  # seconds — same staleness budget as projects list


def _user_profile_version(viewed_user_id):
    """Return current version int for the viewed user's profile detail cache.

    Default 0 when key is absent (first request, or after Redis LRU eviction).
    Version is stored with no expiry so it survives across the 60s payload TTL.
    """
    return cache.get(f'user_profile_version:{viewed_user_id}', 0)


def evict_user_profile_detail(viewed_user_id):
    """Invalidate all cached profile-detail payloads for a user by bumping version.

    All existing cache keys embed the version number; bumping makes them
    unreachable (they TTL-expire harmlessly on their own). Concurrent callers
    that fetched the old version will serve stale data until their 60s TTL lapses
    — acceptable trade-off (next GET after that will see fresh data).

    Call when:
      - viewed user updates their own profile (UserProfileSelfUpdateView.patch)
      - a Project owned by this user is created / updated / deleted
      - another user follows / unfollows this user (follower_count change)
      - this user follows / unfollows another user (following_count change)
    """
    ver_key = f'user_profile_version:{viewed_user_id}'
    try:
        cache.incr(ver_key)
    except ValueError:
        # Key absent (first call or evicted) — initialise to 1.
        cache.set(ver_key, 1, None)


def get_user_profile_detail_cache_key(viewed_user_id, requester_id_for_cache, page, page_size):
    """Build cache key for UserProfileDetailView response payload."""
    ver = _user_profile_version(viewed_user_id)
    return (
        f'user_profile_detail:{viewed_user_id}'
        f':v{ver}'
        f':r{requester_id_for_cache}'
        f':p{page}:ps{page_size}'
    )


# ── Discovery feed cache ──────────────────────────────────────────────────────

DISCOVERY_FEED_TTL = 60  # seconds — same UX staleness window as PERF-1 projects list


def _discovery_feed_key(profile_id, cursor, limit):
    return f"discovery_feed:{profile_id}:cursor{cursor}:limit{limit}"


def get_or_build_discovery_feed(profile, cursor, limit, builder):
    """Cached wrapper around the discovery-feed response payload.

    `builder` is a zero-arg callable that returns the response dict
    {cards, next_cursor, has_more, taste_state}. Result is cached per
    (profile_id, cursor, limit) for DISCOVERY_FEED_TTL seconds.
    Invalidation: call evict_discovery_feed(profile_id) on swipe/bookmark/
    project mutations.
    """
    key = _discovery_feed_key(profile.id, cursor, limit)
    cached = cache.get(key)
    if cached is not None:
        return cached
    data = builder()
    cache.set(key, data, DISCOVERY_FEED_TTL)
    return data


def evict_discovery_feed(profile_id):
    """Invalidate the canonical cursor=0, limit=12 discovery-feed cache entry.

    Other cursor offsets / limits self-expire via the TTL. The canonical entry
    (cursor=0, limit=12) covers the Discovery-tab default fetch.
    """
    cache.delete(_discovery_feed_key(profile_id, 0, 12))
    # Also evict common limit variants
    for limit in (10, 20, 30):
        cache.delete(_discovery_feed_key(profile_id, 0, limit))


# ── Project detail cache (BACK-BOARD-PERF-1) ─────────────────────────────────

PROJECT_DETAIL_TTL = 60  # seconds — same UX staleness window as projects list


def _project_detail_version_key(project_uuid):
    """Per-Project version counter key — incremented on any mutation."""
    return f'project_detail_version:{project_uuid}'


def _project_detail_version(project_uuid):
    """Current version int (0 if not yet set). Used in cache key composition."""
    return cache.get(_project_detail_version_key(project_uuid), 0)


def evict_project_detail(project_uuid):
    """Bump the version counter — all existing cache keys for this project become unreachable."""
    try:
        cache.incr(_project_detail_version_key(project_uuid))
    except ValueError:
        # cache.incr raises ValueError on missing key (LocMemCache) — initialize to 1
        cache.set(_project_detail_version_key(project_uuid), 1, None)


def get_project_detail_cache_key(project_uuid, requester_id_for_cache):
    """Compose the response cache key for ProjectDetailView GET.

    project_uuid: str(Project.project_id)
    requester_id_for_cache: str(requester profile.id) for authenticated callers,
        'anon' for unauthenticated.

    Partitions by requester because `is_reacted` and `is_owner` are per-caller.
    Version counter in the key makes all prior entries unreachable on eviction.
    """
    ver = _project_detail_version(project_uuid)
    return f'project_detail:{project_uuid}:v{ver}:r{requester_id_for_cache}'
