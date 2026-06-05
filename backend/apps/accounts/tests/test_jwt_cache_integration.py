"""
test_jwt_cache_integration.py -- BACK-AUTH-2: CachedJWTAuthentication DRF
pipeline integration tests.

These tests exercise the *full* DRF request pipeline with a real SQLite DB and
real Django cache (LocMemCache) — in contrast to the unit tests in
backend/tests/test_jwt_cache.py which mock the cache backend.

Test matrix:
  INT-1  DRF cache-hit: second request to /me/ is served from cache (auth
         backend's parent get_user not called twice).
  INT-2  is_active stale-cache via signal: deactivate user via user.save()
         → post_save signal fires → cache invalidated → next request re-fetches
         DB → 401.  Result and mechanism documented precisely.
  INT-3  post_save signal invalidation: user.save() invalidates cache; next
         authed request re-fetches from DB (parent called again).
  INT-4  logout invalidation: POST /api/v1/auth/logout/ evicts cache entry.
  INT-5  token-refresh rotation invalidation: POST /api/v1/auth/token/refresh/
         causes invalidate_user_cache to fire (cache cleared).

Design note on is_active (INT-2):
  The cache-hit branch in CachedJWTAuthentication.get_user() returns the
  cached user WITHOUT re-checking is_active.  A request is rejected only if
  either (a) the cache entry was invalidated before the request, or (b) the
  token itself has expired.  For the tested path (is_active toggle via
  user.save()), the post_save signal fires invalidate_user_cache() → cache
  miss → super().get_user() rejects inactive user → 401.  This is CORRECT
  behaviour for the .save() path.

  The documented gap (authentication.py lines 26-32): User.objects.update()
  paths do NOT fire signals and would allow a stale cache hit.  This is a
  known, accepted limitation; no bulk .update() on is_active exists in the
  codebase.  See INT-2 test body + its docstring for further detail.
"""

import pytest
from unittest.mock import patch
from django.contrib.auth.models import User
from django.core.cache import cache
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from apps.accounts.models import UserProfile
from apps.accounts.authentication import _user_cache_key


# ---------------------------------------------------------------------------
# Local autouse cache-clear (root conftest _clear_cache doesn't reach here
# when running this file in isolation via pytest apps/accounts/tests/).
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def _clear_local_cache():
    cache.clear()
    yield
    cache.clear()


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

_ME_URL = '/api/v1/auth/me/'
_LOGOUT_URL = '/api/v1/auth/logout/'
_REFRESH_URL = '/api/v1/auth/token/refresh/'


def _make_user_and_client(username='inttest', email='int@example.com'):
    """Create User + UserProfile and return (user, profile, client, refresh_token)."""
    user = User.objects.create_user(username=username, email=email, password='pass')
    profile = UserProfile.objects.create(user=user, display_name='IntTest')
    client = APIClient()
    refresh = RefreshToken.for_user(user)
    client.credentials(HTTP_AUTHORIZATION=f'Bearer {refresh.access_token}')
    return user, profile, client, refresh


# ---------------------------------------------------------------------------
# INT-1: DRF cache-hit — second /me/ request served from cache
# ---------------------------------------------------------------------------

@pytest.mark.django_db
def test_drf_cache_hit_skips_parent_on_second_request():
    """Second authenticated /me/ request resolves user from cache.

    Strategy: spy on JWTAuthentication.get_user() (the parent).  With the real
    cache (LocMemCache) and CachedJWTAuthentication in DEFAULT_AUTHENTICATION_CLASSES:
      - Request 1: cache miss → parent called (call_count = 1).
      - Request 2: cache hit → parent NOT called again (call_count stays 1).
    """
    user, _, client, _ = _make_user_and_client(username='int1user')

    with patch(
        'rest_framework_simplejwt.authentication.JWTAuthentication.get_user',
        side_effect=lambda *a, **k: User.objects.get(pk=user.id),
    ) as mock_parent:
        resp1 = client.get(_ME_URL)
        assert resp1.status_code == 200
        first_call_count = mock_parent.call_count

        resp2 = client.get(_ME_URL)
        assert resp2.status_code == 200
        # Parent must NOT have been called again — second request was a cache hit.
        assert mock_parent.call_count == first_call_count, (
            f'Expected no additional parent calls after cache warm; '
            f'got {mock_parent.call_count - first_call_count} extra call(s)'
        )


# ---------------------------------------------------------------------------
# INT-2: is_active stale-cache security via post_save signal
# ---------------------------------------------------------------------------

@pytest.mark.django_db
def test_is_active_false_via_save_rejects_next_request():
    """Deactivating a user via user.save() → signal → cache evicted → 401.

    Mechanism:
      1. First /me/ warms the cache.
      2. user.is_active = False; user.save() → post_save signal →
         invalidate_user_cache(user.id) → cache key deleted.
      3. Next /me/ with the SAME access token → cache miss → super().get_user()
         → simplejwt rejects inactive user → 401.

    This test verifies the .save() path is secure.  The documented gap:
    User.objects.filter().update(is_active=False) does NOT fire post_save →
    stale cache could remain until TTL.  That gap is accepted/documented in
    authentication.py and is NOT a regression introduced here.
    """
    user, _, client, _ = _make_user_and_client(username='int2user')

    # Warm the cache
    resp1 = client.get(_ME_URL)
    assert resp1.status_code == 200
    assert cache.get(_user_cache_key(user.id)) is not None, (
        'Cache should be warm after first authenticated request'
    )

    # Deactivate via .save() → post_save signal fires → cache invalidated
    user.is_active = False
    user.save(update_fields=['is_active'])

    # Signal should have evicted the cache entry immediately
    assert cache.get(_user_cache_key(user.id)) is None, (
        'post_save signal must have evicted cache after is_active=False save'
    )

    # Next request with the same access token → cache miss → DB → 401
    resp2 = client.get(_ME_URL)
    assert resp2.status_code == 401, (
        'Deactivated user must not be authenticated after cache invalidation'
    )


# ---------------------------------------------------------------------------
# INT-3: post_save signal invalidation → re-fetch from DB
# ---------------------------------------------------------------------------

@pytest.mark.django_db
def test_post_save_signal_invalidates_cache_and_causes_refetch():
    """user.save() invalidates cache; next request calls parent again.

    Confirms the signal backstop: an ORM .save() (e.g. admin UI, password
    change) always clears the cache so the next request re-reads the DB row.
    """
    user, profile, client, _ = _make_user_and_client(username='int3user')

    with patch(
        'rest_framework_simplejwt.authentication.JWTAuthentication.get_user',
        side_effect=lambda *a, **k: User.objects.get(pk=user.id),
    ) as mock_parent:
        # Warm the cache
        resp1 = client.get(_ME_URL)
        assert resp1.status_code == 200
        call_count_after_first = mock_parent.call_count  # = 1

        # Trigger post_save signal via User.save() (arbitrary field change).
        # Note: profile.save() fires UserProfile post_save, NOT User post_save —
        # only User.save() triggers the cache-invalidation signal backstop.
        user.first_name = 'Updated'
        user.save(update_fields=['first_name'])

        # Cache must have been evicted
        assert cache.get(_user_cache_key(user.id)) is None, (
            'post_save on User must evict the cache entry'
        )

        # Next request must re-hit parent (cache miss after invalidation)
        resp2 = client.get(_ME_URL)
        assert resp2.status_code == 200
        assert mock_parent.call_count > call_count_after_first, (
            'Parent get_user must be called again after cache invalidation'
        )


# ---------------------------------------------------------------------------
# INT-4: logout invalidation
# ---------------------------------------------------------------------------

@pytest.mark.django_db
def test_logout_evicts_cache():
    """POST /logout/ evicts the user cache entry.

    Note: the access token remains technically valid until its natural expiry
    (simplejwt does not blacklist access tokens).  We assert cache eviction,
    not 401 on the next /me/ request.
    """
    user, _, client, refresh = _make_user_and_client(username='int4user')

    # Warm the cache
    resp = client.get(_ME_URL)
    assert resp.status_code == 200
    assert cache.get(_user_cache_key(user.id)) is not None

    # Logout (blacklists refresh + evicts cache)
    logout_resp = client.post(
        _LOGOUT_URL,
        {'refresh': str(refresh)},
        format='json',
    )
    assert logout_resp.status_code == 204

    # Cache entry must be gone
    assert cache.get(_user_cache_key(user.id)) is None, (
        'LogoutView must evict cache entry via invalidate_user_cache()'
    )


# ---------------------------------------------------------------------------
# INT-5: token-refresh rotation invalidation
# ---------------------------------------------------------------------------

@pytest.mark.django_db
def test_token_refresh_rotation_evicts_cache():
    """POST /token/refresh/ with rotation fires invalidate_user_cache.

    ROTATE_REFRESH_TOKENS + BLACKLIST_AFTER_ROTATION are True in settings.
    TokenRefreshView.post() calls invalidate_user_cache(user_id) after
    refresh.blacklist() when rotation is enabled.  Verify the cache entry is
    cleared after a successful refresh.
    """
    user, _, client, refresh = _make_user_and_client(username='int5user')

    # Warm the cache
    resp = client.get(_ME_URL)
    assert resp.status_code == 200
    assert cache.get(_user_cache_key(user.id)) is not None

    # Perform token refresh — use an unauthenticated client (no bearer needed)
    anon_client = APIClient()
    refresh_resp = anon_client.post(
        _REFRESH_URL,
        {'refresh': str(refresh)},
        format='json',
    )
    assert refresh_resp.status_code == 200, (
        f'Token refresh must succeed; got {refresh_resp.status_code}: {refresh_resp.data}'
    )

    # Cache must be evicted after rotation
    assert cache.get(_user_cache_key(user.id)) is None, (
        'TokenRefreshView must evict cache entry after BLACKLIST_AFTER_ROTATION'
    )
