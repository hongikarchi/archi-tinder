"""
test_cache_backend.py -- INFRA-REDIS-1: cache backend dispatch logic.

Tests the _build_caches_dict helper extracted from config/settings.py.
No live Redis daemon required -- the helper is a pure dict-building function;
the Redis URL is never connected to during these tests.

Tests:
- TestLocMemBranch: REDIS_URL='' (empty/unset) -> LocMemCache backend,
  MAX_ENTRIES=2000 preserved.
- TestRedisBranch: REDIS_URL set -> django_redis.cache.RedisCache backend,
  LOCATION matches the URL, KEY_PREFIX='makeweb', socket timeouts present.
- TestMutualExclusion: helper called twice with different inputs returns
  independent dicts (no shared mutable state).
"""
# ---------------------------------------------------------------------------
# Import the helper directly -- no manage.py, no env mutation, no reload.
# settings.py is already imported by the time pytest starts (via DJANGO_SETTINGS_MODULE),
# so we can import the helper from the already-loaded module.
# ---------------------------------------------------------------------------

import pytest
from config.settings import _build_caches_dict, _check_async_prefetch_safety


# ---------------------------------------------------------------------------
# TestLocMemBranch
# ---------------------------------------------------------------------------

class TestLocMemBranch:
    """REDIS_URL unset / empty string -> LocMemCache fallback."""

    def test_empty_string_returns_locmem_backend(self):
        caches = _build_caches_dict('')
        assert caches['default']['BACKEND'] == (
            'django.core.cache.backends.locmem.LocMemCache'
        )

    def test_whitespace_only_returns_locmem(self):
        # settings.py calls .strip() before passing; simulate the stripped value.
        caches = _build_caches_dict('   '.strip())
        assert caches['default']['BACKEND'] == (
            'django.core.cache.backends.locmem.LocMemCache'
        )

    def test_max_entries_2000_preserved(self):
        caches = _build_caches_dict('')
        options = caches['default'].get('OPTIONS', {})
        assert options.get('MAX_ENTRIES') == 2000

    def test_no_key_prefix_in_locmem(self):
        caches = _build_caches_dict('')
        # KEY_PREFIX is a Redis concern; LocMemCache dict should not include it.
        assert 'KEY_PREFIX' not in caches['default']

    def test_no_location_key_in_locmem(self):
        caches = _build_caches_dict('')
        assert 'LOCATION' not in caches['default']


# ---------------------------------------------------------------------------
# TestRedisBranch
# ---------------------------------------------------------------------------

class TestRedisBranch:
    """REDIS_URL set -> django_redis.cache.RedisCache with expected config."""

    _FAKE_URL = 'redis://redis.railway.internal:6379'

    def test_redis_url_returns_django_redis_backend(self):
        caches = _build_caches_dict(self._FAKE_URL)
        assert caches['default']['BACKEND'] == 'django_redis.cache.RedisCache'

    def test_location_matches_redis_url(self):
        caches = _build_caches_dict(self._FAKE_URL)
        assert caches['default']['LOCATION'] == self._FAKE_URL

    def test_key_prefix_is_makeweb(self):
        caches = _build_caches_dict(self._FAKE_URL)
        assert caches['default']['KEY_PREFIX'] == 'makeweb'

    def test_client_class_is_default_client(self):
        caches = _build_caches_dict(self._FAKE_URL)
        options = caches['default']['OPTIONS']
        assert options['CLIENT_CLASS'] == 'django_redis.client.DefaultClient'

    def test_socket_connect_timeout_set(self):
        caches = _build_caches_dict(self._FAKE_URL)
        options = caches['default']['OPTIONS']
        assert 'SOCKET_CONNECT_TIMEOUT' in options
        assert options['SOCKET_CONNECT_TIMEOUT'] == 3

    def test_socket_timeout_set(self):
        caches = _build_caches_dict(self._FAKE_URL)
        options = caches['default']['OPTIONS']
        assert 'SOCKET_TIMEOUT' in options
        assert options['SOCKET_TIMEOUT'] == 3

    def test_no_max_entries_in_redis_branch(self):
        # MAX_ENTRIES is a LocMemCache option; Redis manages memory server-side.
        caches = _build_caches_dict(self._FAKE_URL)
        options = caches['default'].get('OPTIONS', {})
        assert 'MAX_ENTRIES' not in options

    def test_different_redis_urls_produce_correct_location(self):
        url2 = 'rediss://user:pass@prod-redis.example.com:6380/0'
        caches = _build_caches_dict(url2)
        assert caches['default']['LOCATION'] == url2


# ---------------------------------------------------------------------------
# TestMutualExclusion
# ---------------------------------------------------------------------------

class TestMutualExclusion:
    """Helper returns independent dicts on each call -- no shared mutable state."""

    def test_locmem_and_redis_dicts_are_independent(self):
        locmem = _build_caches_dict('')
        redis = _build_caches_dict('redis://localhost:6379')
        # Mutating one must not affect the other.
        locmem['default']['OPTIONS']['MAX_ENTRIES'] = 9999
        assert redis['default'].get('OPTIONS', {}).get('MAX_ENTRIES') != 9999

    def test_two_redis_dicts_are_independent(self):
        d1 = _build_caches_dict('redis://a:6379')
        d2 = _build_caches_dict('redis://b:6379')
        d1['default']['KEY_PREFIX'] = 'changed'
        assert d2['default']['KEY_PREFIX'] == 'makeweb'

    def test_two_locmem_dicts_are_independent(self):
        d1 = _build_caches_dict('')
        d2 = _build_caches_dict('')
        d1['default']['OPTIONS']['MAX_ENTRIES'] = 1
        assert d2['default']['OPTIONS']['MAX_ENTRIES'] == 2000


# ---------------------------------------------------------------------------
# TestAsyncPrefetchSafetyGuard
# ---------------------------------------------------------------------------

class TestAsyncPrefetchSafetyGuard:
    """INFRA-REDIS-1 follow-up: _check_async_prefetch_safety startup guard.

    Prod (DEBUG=False) + async_prefetch_enabled=True + no REDIS_URL must
    raise ImproperlyConfigured so ops sees the misconfiguration immediately
    rather than silently running per-process LocMemCache with broken prefetch.
    """

    def test_redis_required_in_prod_when_async_prefetch_enabled(self):
        """Prod + async prefetch ON + no REDIS_URL -> ImproperlyConfigured."""
        from django.core.exceptions import ImproperlyConfigured
        with pytest.raises(ImproperlyConfigured):
            _check_async_prefetch_safety(
                debug=False,
                async_prefetch_enabled=True,
                redis_url='',
            )

    def test_no_error_when_redis_url_set_in_prod(self):
        """Prod + async prefetch ON + REDIS_URL set -> no error."""
        _check_async_prefetch_safety(
            debug=False,
            async_prefetch_enabled=True,
            redis_url='redis://redis.railway.internal:6379',
        )

    def test_no_error_in_debug_mode_without_redis(self):
        """Debug=True (local dev) + no REDIS_URL -> no error (LocMemCache OK for dev)."""
        _check_async_prefetch_safety(
            debug=True,
            async_prefetch_enabled=True,
            redis_url='',
        )

    def test_no_error_when_async_prefetch_disabled_in_prod(self):
        """Prod + async prefetch OFF + no REDIS_URL -> no error (flag guards the path)."""
        _check_async_prefetch_safety(
            debug=False,
            async_prefetch_enabled=False,
            redis_url='',
        )
