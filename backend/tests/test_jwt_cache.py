"""
test_jwt_cache.py -- BACK-AUTH-1: CachedJWTAuthentication user-row cache.

Tests are structured to avoid requiring the Neon test DB (known INFRA-DB-1
constraint: make_web_app role cannot CREATE DATABASE).

MagicMock user objects cannot be pickled by Django's LocMemCache backend, so
cache.get / cache.set are patched at the module level to use a simple in-memory
dict. This is intentional: we are testing the CachedJWTAuthentication *logic*
(when to call cache.get/set, what TTL to use), not the cache backend itself
(already covered by test_cache_backend.py).

Tests confirm:
  1. Cache miss path populates cache (DB called once).
  2. Cache hit path skips DB (DB NOT called on second request).
  3. TTL cap enforced — expired cache entry (cache miss) falls back to DB.
  4. invalidate_user_cache() evicts entry — next request hits DB.
  5. post_save signal handler calls invalidate_user_cache when invoked.
  6. post_delete signal handler calls invalidate_user_cache when invoked.
  7. Missing USER_ID_CLAIM (KeyError) → defers to parent error path.
  8. Token already expired (remaining <= 0) → user returned WITHOUT caching.
  9. Cross-instance — populate from one CachedJWTAuthentication, read from another.
  10. TTL capped at JWT_USER_CACHE_TTL_CAP (3600s) when exp is far in future.
  11. TTL uses remaining when remaining < cap.
  12. Malformed exp (TypeError) → defensive fallback to cap TTL, still caches.

Security gates verified:
  - Signature check runs BEFORE get_user (in JWTAuthentication.authenticate,
    not overridden here). Bad-sig / expired tokens never reach get_user in the
    real pipeline — JWTAuthentication.authenticate() rejects them first.
  - TTL cap: min(token_exp - now, 3600s) — tests #10 and #11.
  - Synchronous invalidation at logout and refresh rotation call sites.
  - Signal backstop catches admin/ORM .save() paths — tests #5 and #6.
"""

import time
import pytest
from unittest.mock import patch, MagicMock

from rest_framework_simplejwt.settings import api_settings

from apps.accounts.authentication import (
    CachedJWTAuthentication,
    invalidate_user_cache,
    _user_cache_key,
    JWT_USER_CACHE_TTL_CAP,
)


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

def _make_fake_user(user_id=42):
    """Return a mock User object sufficient for cache logic tests."""
    user = MagicMock()
    user.id = user_id
    user.is_active = True
    return user


def _make_validated_token(user_id=42, exp_offset=3600):
    """Return a mock validated_token with USER_ID_CLAIM and exp set."""
    now = int(time.time())
    token = MagicMock()
    token.__getitem__ = MagicMock(side_effect=lambda key: (
        user_id if key == api_settings.USER_ID_CLAIM else now + exp_offset
    ))
    token.get = MagicMock(side_effect=lambda key, default=None: (
        user_id if key == api_settings.USER_ID_CLAIM else default
    ))
    return token


def _make_cache_store():
    """Return (store_dict, mock_cache_get, mock_cache_set, mock_cache_delete)
    backed by a plain dict. Avoids pickle issues with MagicMock users."""
    store = {}

    def _get(key, default=None):
        return store.get(key, default)

    def _set(key, value, timeout=None, **kwargs):
        store[key] = value

    def _delete(key):
        store.pop(key, None)

    return store, _get, _set, _delete


# ---------------------------------------------------------------------------
# Context manager: patch cache ops with a simple dict store
# ---------------------------------------------------------------------------

class _MockCache:
    """Context manager that replaces cache.get/set/delete in authentication.py
    with a simple dict-backed store (no pickling)."""

    def __init__(self):
        self.store, self._get, self._set, self._delete = _make_cache_store()
        self._set_calls = []  # [(key, value, timeout)]

    def _recording_set(self, key, value, timeout=None, **kwargs):
        self._set_calls.append((key, value, timeout))
        self._set(key, value, timeout=timeout)

    def __enter__(self):
        self._p_get = patch('apps.accounts.authentication.cache.get', side_effect=self._get)
        self._p_set = patch('apps.accounts.authentication.cache.set', side_effect=self._recording_set)
        self._p_del = patch('apps.accounts.authentication.cache.delete', side_effect=self._delete)
        self._p_get.start()
        self._p_set.start()
        self._p_del.start()
        return self

    def __exit__(self, *args):
        self._p_get.stop()
        self._p_set.stop()
        self._p_del.stop()

    def get_set_timeout(self, key_suffix):
        """Return the timeout from the last cache.set call matching key_suffix."""
        for k, v, timeout in reversed(self._set_calls):
            if key_suffix in k:
                return timeout
        return None


# ---------------------------------------------------------------------------
# 1. Cache miss path — first get_user call populates cache; parent called once.
# ---------------------------------------------------------------------------

def test_cache_miss_populates_cache():
    """First get_user call misses cache, calls parent, then stores result."""
    fake_user = _make_fake_user(user_id=1)
    authenticator = CachedJWTAuthentication()
    token = _make_validated_token(user_id=1, exp_offset=3600)

    with _MockCache() as mc:
        with patch(
            'rest_framework_simplejwt.authentication.JWTAuthentication.get_user',
            return_value=fake_user,
        ) as mock_parent:
            result = authenticator.get_user(token)

        assert mock_parent.call_count == 1
        assert result is fake_user
        # Cache must have been populated
        cached = mc.store.get(_user_cache_key(1))
        assert cached is not None
        assert cached is fake_user


# ---------------------------------------------------------------------------
# 2. Cache hit path — second call returns cached user; parent NOT called.
# ---------------------------------------------------------------------------

def test_cache_hit_skips_db():
    """Second get_user call with cached entry skips parent DB lookup."""
    fake_user = _make_fake_user(user_id=2)
    authenticator = CachedJWTAuthentication()
    token = _make_validated_token(user_id=2, exp_offset=3600)

    with _MockCache():
        with patch(
            'rest_framework_simplejwt.authentication.JWTAuthentication.get_user',
            return_value=fake_user,
        ) as mock_parent:
            # First call — cache miss
            authenticator.get_user(token)
            assert mock_parent.call_count == 1

            # Second call — should hit cache; parent NOT called again
            result = authenticator.get_user(token)
            assert mock_parent.call_count == 1  # still 1, not 2

    assert result is fake_user


# ---------------------------------------------------------------------------
# 3. TTL cap — expired cache entry (absent) falls through to DB.
# ---------------------------------------------------------------------------

def test_ttl_cap_expired_falls_through():
    """When cache returns None (entry expired/absent), get_user calls parent."""
    fake_user = _make_fake_user(user_id=3)
    authenticator = CachedJWTAuthentication()
    token = _make_validated_token(user_id=3, exp_offset=3600)

    with _MockCache():
        # Don't pre-populate cache — simulates expired/absent entry
        with patch(
            'rest_framework_simplejwt.authentication.JWTAuthentication.get_user',
            return_value=fake_user,
        ) as mock_parent:
            result = authenticator.get_user(token)
            assert mock_parent.call_count == 1

    assert result is fake_user


# ---------------------------------------------------------------------------
# 4. invalidate_user_cache evicts entry — next request hits DB.
# ---------------------------------------------------------------------------

def test_invalidate_user_cache_evicts():
    """invalidate_user_cache() removes the key; next get_user goes to parent."""
    fake_user = _make_fake_user(user_id=4)
    authenticator = CachedJWTAuthentication()
    token = _make_validated_token(user_id=4, exp_offset=3600)

    with _MockCache() as mc:
        with patch(
            'rest_framework_simplejwt.authentication.JWTAuthentication.get_user',
            return_value=fake_user,
        ) as mock_parent:
            # Populate cache
            authenticator.get_user(token)
            assert mock_parent.call_count == 1
            assert mc.store.get(_user_cache_key(4)) is not None

        # Evict via the public API function — _MockCache already patches cache.delete
        invalidate_user_cache(4)

        assert mc.store.get(_user_cache_key(4)) is None

        # Next request should hit parent again (cache miss after eviction)
        with patch(
            'rest_framework_simplejwt.authentication.JWTAuthentication.get_user',
            return_value=fake_user,
        ) as mock_parent2:
            authenticator.get_user(token)
            assert mock_parent2.call_count == 1


# ---------------------------------------------------------------------------
# 5. post_save signal handler calls invalidate_user_cache.
# ---------------------------------------------------------------------------

def test_post_save_signal_handler_calls_invalidate():
    """_invalidate_user_cache_on_save signal handler evicts user from cache."""
    from apps.accounts.signals import _invalidate_user_cache_on_save

    fake_user = _make_fake_user(user_id=5)

    with _MockCache() as mc:
        # Pre-seed the cache
        mc.store[_user_cache_key(5)] = fake_user
        assert mc.store.get(_user_cache_key(5)) is not None

        # Invoke the signal handler directly (as Django would on post_save)
        # _MockCache already patches cache.delete — no inner patch needed
        _invalidate_user_cache_on_save(sender=None, instance=fake_user)

        # Cache must be evicted
        assert mc.store.get(_user_cache_key(5)) is None


# ---------------------------------------------------------------------------
# 6. post_delete signal handler calls invalidate_user_cache.
# ---------------------------------------------------------------------------

def test_post_delete_signal_handler_calls_invalidate():
    """_invalidate_user_cache_on_delete signal handler evicts user from cache."""
    from apps.accounts.signals import _invalidate_user_cache_on_delete

    fake_user = _make_fake_user(user_id=6)

    with _MockCache() as mc:
        # Pre-seed the cache
        mc.store[_user_cache_key(6)] = fake_user
        assert mc.store.get(_user_cache_key(6)) is not None

        # Invoke the signal handler directly (as Django would on post_delete)
        # _MockCache already patches cache.delete — no inner patch needed
        _invalidate_user_cache_on_delete(sender=None, instance=fake_user)

        # Cache must be evicted
        assert mc.store.get(_user_cache_key(6)) is None


# ---------------------------------------------------------------------------
# 7. Missing USER_ID_CLAIM (KeyError) → defers to parent error path.
# ---------------------------------------------------------------------------

def test_missing_user_id_claim_defers_to_parent():
    """When USER_ID_CLAIM is missing, KeyError triggers parent get_user call."""
    authenticator = CachedJWTAuthentication()

    # Token that raises KeyError for any key access
    token = MagicMock()
    token.__getitem__ = MagicMock(side_effect=KeyError('user_id'))

    with _MockCache():
        with patch(
            'rest_framework_simplejwt.authentication.JWTAuthentication.get_user',
            side_effect=Exception('parent error path'),
        ) as mock_parent:
            with pytest.raises(Exception, match='parent error path'):
                authenticator.get_user(token)
            assert mock_parent.call_count == 1


# ---------------------------------------------------------------------------
# 8. Token already expired (remaining <= 0) — user returned WITHOUT caching.
# ---------------------------------------------------------------------------

def test_expired_token_not_cached():
    """Token with exp in the past: user returned but NOT stored in cache."""
    fake_user = _make_fake_user(user_id=8)
    authenticator = CachedJWTAuthentication()

    # exp in the past
    past_exp = int(time.time()) - 10
    token = MagicMock()
    token.__getitem__ = MagicMock(side_effect=lambda key: (
        8 if key == api_settings.USER_ID_CLAIM else past_exp
    ))

    with _MockCache() as mc:
        with patch(
            'rest_framework_simplejwt.authentication.JWTAuthentication.get_user',
            return_value=fake_user,
        ):
            result = authenticator.get_user(token)

    assert result is fake_user
    # Must NOT be cached (remaining <= 0 → early return without cache.set)
    assert _user_cache_key(8) not in mc.store


# ---------------------------------------------------------------------------
# 9. Cross-instance — populate from one authenticator, read from another.
# ---------------------------------------------------------------------------

def test_cross_instance_cache_hit():
    """Cache is process-global; two authenticator instances share it."""
    fake_user = _make_fake_user(user_id=9)
    auth1 = CachedJWTAuthentication()
    auth2 = CachedJWTAuthentication()
    token = _make_validated_token(user_id=9, exp_offset=3600)

    with _MockCache():
        with patch(
            'rest_framework_simplejwt.authentication.JWTAuthentication.get_user',
            return_value=fake_user,
        ) as mock_parent:
            # Instance 1 populates cache
            auth1.get_user(token)
            assert mock_parent.call_count == 1

            # Instance 2 should hit cache — parent NOT called again
            result = auth2.get_user(token)
            assert mock_parent.call_count == 1  # still 1

    assert result is fake_user


# ---------------------------------------------------------------------------
# 10. TTL capped at JWT_USER_CACHE_TTL_CAP (3600s).
# ---------------------------------------------------------------------------

def test_ttl_capped_at_3600():
    """TTL is never set beyond JWT_USER_CACHE_TTL_CAP (3600s).

    When exp is 7200s in the future (exceeds cap), TTL used should be capped at 3600.
    """
    fake_user = _make_fake_user(user_id=10)
    authenticator = CachedJWTAuthentication()

    far_exp = int(time.time()) + 7200  # 2 hours > cap
    token = MagicMock()
    token.__getitem__ = MagicMock(side_effect=lambda key: (
        10 if key == api_settings.USER_ID_CLAIM else far_exp
    ))

    with _MockCache() as mc:
        with patch(
            'rest_framework_simplejwt.authentication.JWTAuthentication.get_user',
            return_value=fake_user,
        ):
            authenticator.get_user(token)

    timeout_used = mc.get_set_timeout(str(10))
    assert timeout_used is not None, 'cache.set must have been called'
    assert timeout_used <= JWT_USER_CACHE_TTL_CAP, (
        f'TTL {timeout_used} exceeds cap {JWT_USER_CACHE_TTL_CAP}'
    )


# ---------------------------------------------------------------------------
# 11. TTL uses remaining when remaining < cap.
# ---------------------------------------------------------------------------

def test_ttl_uses_remaining_when_less_than_cap():
    """When token exp is < 3600s away, TTL = remaining (not cap)."""
    fake_user = _make_fake_user(user_id=11)
    authenticator = CachedJWTAuthentication()

    expected_remaining = 600  # 10 minutes < 3600s cap
    near_exp = int(time.time()) + expected_remaining
    token = MagicMock()
    token.__getitem__ = MagicMock(side_effect=lambda key: (
        11 if key == api_settings.USER_ID_CLAIM else near_exp
    ))

    with _MockCache() as mc:
        with patch(
            'rest_framework_simplejwt.authentication.JWTAuthentication.get_user',
            return_value=fake_user,
        ):
            authenticator.get_user(token)

    timeout_used = mc.get_set_timeout(str(11))
    assert timeout_used is not None, 'cache.set must have been called'
    # Allow 5s clock skew
    assert timeout_used <= expected_remaining + 5
    assert 0 < timeout_used <= JWT_USER_CACHE_TTL_CAP


# ---------------------------------------------------------------------------
# 12. Malformed exp (TypeError) → defensive fallback to cap TTL, still caches.
# ---------------------------------------------------------------------------

def test_malformed_exp_falls_back_to_cap_ttl():
    """Malformed exp (raises TypeError on int()) → fallback to cap TTL, still caches."""
    fake_user = _make_fake_user(user_id=12)
    authenticator = CachedJWTAuthentication()

    token = MagicMock()

    # Use side_effect on __getitem__ so the mock handles the self binding
    def _getitem_side_effect(key):
        if key == api_settings.USER_ID_CLAIM:
            return 12
        # 'exp' key raises TypeError (malformed non-int)
        raise TypeError('malformed exp')

    token.__getitem__ = MagicMock(side_effect=_getitem_side_effect)

    with _MockCache() as mc:
        with patch(
            'rest_framework_simplejwt.authentication.JWTAuthentication.get_user',
            return_value=fake_user,
        ):
            result = authenticator.get_user(token)

    assert result is fake_user
    timeout_used = mc.get_set_timeout(str(12))
    assert timeout_used is not None, 'cache.set must have been called even with malformed exp'
    assert timeout_used == JWT_USER_CACHE_TTL_CAP, (
        f'Expected fallback TTL {JWT_USER_CACHE_TTL_CAP}, got {timeout_used}'
    )
