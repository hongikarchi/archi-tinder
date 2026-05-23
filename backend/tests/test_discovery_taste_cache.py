"""
test_discovery_taste_cache.py — unit tests for recommendation.caches.

Tests:
1. test_cache_miss_builds_and_caches — cold path: compute called, result cached.
2. test_cache_hit_skips_compute — warm path: compute NOT called on second hit.
3. test_evict_clears_cache — evict_taste(profile_id) removes the cache entry.
4. test_compute_none_not_cached — None from compute → no cache poisoning.
"""
import numpy as np
import pytest
from unittest.mock import patch, MagicMock

from django.core.cache import cache


@pytest.fixture(autouse=True)
def _clear_cache():
    """Clear the Django cache before and after every test."""
    cache.clear()
    yield
    cache.clear()


def _make_profile(pk=42):
    """Return a minimal UserProfile-like mock with a numeric .id."""
    p = MagicMock()
    p.id = pk
    return p


def _fake_vec():
    """Return a reproducible float64 ndarray (384,) that compute_user_taste_vector would return."""
    rng = np.random.default_rng(0)
    v = rng.standard_normal(384)
    return v / np.linalg.norm(v)


# ---------------------------------------------------------------------------
# 1. Cold path: compute called, result cached
# ---------------------------------------------------------------------------

def test_cache_miss_builds_and_caches():
    """On a cold call, compute_user_taste_vector is called and result is cached."""
    from apps.recommendation.caches import get_or_build_taste, _taste_key

    profile = _make_profile(pk=1)
    vec = _fake_vec()

    with patch(
        'apps.recommendation.caches.engine.compute_user_taste_vector',
        return_value=vec,
    ) as mock_compute:
        result = get_or_build_taste(profile)

    # Function returns the vector
    assert result is not None
    assert result.dtype == np.float32
    assert result.shape == (384,)

    # compute was called once
    mock_compute.assert_called_once_with(profile)

    # Cache now has the serialized bytes
    raw = cache.get(_taste_key(profile.id))
    assert raw is not None
    cached_vec = np.frombuffer(raw, dtype=np.float32)
    np.testing.assert_allclose(cached_vec, result, rtol=1e-5)


# ---------------------------------------------------------------------------
# 2. Warm path: cache hit — compute NOT called
# ---------------------------------------------------------------------------

def test_cache_hit_skips_compute():
    """On a warm call (cache pre-populated), compute_user_taste_vector is NOT called."""
    from apps.recommendation.caches import get_or_build_taste, _taste_key, TASTE_TTL

    profile = _make_profile(pk=2)
    pre_vec = _fake_vec().astype(np.float32)

    # Pre-populate the cache as if a previous call had filled it
    cache.set(_taste_key(profile.id), pre_vec.tobytes(), TASTE_TTL)

    with patch(
        'apps.recommendation.caches.engine.compute_user_taste_vector',
    ) as mock_compute:
        result = get_or_build_taste(profile)

    # compute was never called
    mock_compute.assert_not_called()

    # Result matches what was in the cache
    assert result is not None
    assert result.dtype == np.float32
    np.testing.assert_allclose(result, pre_vec, rtol=1e-5)


# ---------------------------------------------------------------------------
# 3. Eviction: evict_taste clears the cache entry
# ---------------------------------------------------------------------------

def test_evict_clears_cache():
    """evict_taste(profile_id) removes the taste key from the cache."""
    from apps.recommendation.caches import evict_taste, _taste_key, TASTE_TTL

    profile_id = 7
    pre_vec = _fake_vec().astype(np.float32)

    cache.set(_taste_key(profile_id), pre_vec.tobytes(), TASTE_TTL)
    assert cache.get(_taste_key(profile_id)) is not None, 'Pre-condition: cache should have entry'

    evict_taste(profile_id)

    assert cache.get(_taste_key(profile_id)) is None, 'Post-evict: cache entry should be gone'


# ---------------------------------------------------------------------------
# 4. None not cached — no cache poisoning on cold start
# ---------------------------------------------------------------------------

def test_compute_none_not_cached():
    """When compute returns None (no likes yet), nothing is written to cache."""
    from apps.recommendation.caches import get_or_build_taste, _taste_key

    profile = _make_profile(pk=99)

    with patch(
        'apps.recommendation.caches.engine.compute_user_taste_vector',
        return_value=None,
    ) as mock_compute:
        result = get_or_build_taste(profile)

    # Caller receives None
    assert result is None

    # compute was called (not short-circuited by a wrong cache hit)
    mock_compute.assert_called_once_with(profile)

    # Cache must have nothing — no poisoning
    assert cache.get(_taste_key(profile.id)) is None, (
        'None result must not be stored in cache'
    )
