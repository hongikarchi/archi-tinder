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
