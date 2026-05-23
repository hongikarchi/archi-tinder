"""TTL caches for recommendation engine."""

import numpy as np
from django.core.cache import cache

from . import engine

TASTE_TTL = 300  # seconds — 5-minute freshness window


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
