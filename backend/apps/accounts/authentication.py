"""User-row cached JWTAuthentication — saves ~590ms Neon roundtrip on authenticated requests.

BACK-AUTH-1 (.claude/plans/merry-toasting-dove.md PR 3 of 4). Depends on PR 1
INFRA-REDIS-1: Redis is the prod cache backend; LocMemCache fallback in local dev.

Caches the result of simplejwt's ``JWTAuthentication.get_user()`` lookup keyed
by ``user_id``. TTL is the smaller of (token's natural expiry, 3600s) so a
cache entry can never outlast the access token itself — limits exposure
window if invalidation is missed elsewhere.

CACHE INVALIDATION CONTRACT — every code path that mutates a user's
authentication-relevant state MUST call ``invalidate_user_cache(user_id)``:

  - logout (RefreshToken.blacklist) — apps/accounts/views.py LogoutView
  - refresh rotation (refresh.blacklist) — apps/accounts/views.py TokenRefreshView
  - password change / set_unusable_password
  - is_active toggle (admin deactivation)
  - User row deletion
  - Any future admin "kill switch" / "revoke all sessions" feature

A ``post_save`` signal on the User model is wired as a safety-net backstop:
any Django ORM ``User.save()`` (admin UI included) auto-invalidates. The
explicit ``invalidate_user_cache(...)`` calls give synchronous immediate-evict
semantics that bypass any signal ordering issues.

NOTE on ``User.objects.update(...)`` — Django's queryset ``.update()`` does NOT
fire ``post_save`` signals. The signal backstop therefore DOES NOT protect
against bulk ``.update()`` calls. Any future code path that does
``User.objects.filter(...).update(is_active=False)`` or similar MUST call
``invalidate_user_cache(user_id)`` explicitly. The grep-confirmed assertion as
of BACK-AUTH-1: no ``.update()`` paths on auth-relevant User fields exist in
apps/accounts/ or apps/profiles/.

If you ever ADD a new authentication-relevant state mutation (especially via
``.update()``), document it here AND wire the explicit invalidate call. The
signal is a backstop for ``.save()`` paths only, not a substitute.
"""

import time
from django.core.cache import cache
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework_simplejwt.settings import api_settings

JWT_USER_CACHE_KEY_PREFIX = 'jwt_user:'
JWT_USER_CACHE_TTL_CAP = 3600  # access token's natural lifetime per SIMPLE_JWT


def _user_cache_key(user_id):
    return JWT_USER_CACHE_KEY_PREFIX + str(user_id)


def invalidate_user_cache(user_id):
    """Evict a cached user row. Call from every auth-relevant state mutation."""
    cache.delete(_user_cache_key(user_id))


class CachedJWTAuthentication(JWTAuthentication):
    """JWTAuthentication with Redis-backed user-row validation cache.

    Only the DB lookup (get_user) is cached. Token signature verification and
    expiry/jti checks run inside ``JWTAuthentication.authenticate()`` BEFORE
    ``get_user`` is called — bad signatures and expired tokens are rejected
    before the cache is consulted.
    """

    def get_user(self, validated_token):
        try:
            user_id = validated_token[api_settings.USER_ID_CLAIM]
        except KeyError:
            # Defer to parent for the proper error path (raises InvalidToken).
            return super().get_user(validated_token)

        cache_key = _user_cache_key(user_id)
        cached_user = cache.get(cache_key)
        if cached_user is not None:
            return cached_user

        # Cache miss — exercise the full simplejwt path (Neon roundtrip + checks).
        # If the user is inactive, super().get_user() raises AuthenticationFailed
        # before we reach cache.set(), so inactive users are never cached.
        user = super().get_user(validated_token)

        # TTL cap: token exp - now, bounded by JWT_USER_CACHE_TTL_CAP (3600s).
        # validated_token['exp'] is a unix timestamp (int).
        ttl = JWT_USER_CACHE_TTL_CAP
        try:
            exp_ts = int(validated_token['exp'])
            now_ts = int(time.time())
            remaining = exp_ts - now_ts
            if remaining > 0:
                ttl = min(remaining, JWT_USER_CACHE_TTL_CAP)
            else:
                # Token already expired — let super() handle, don't cache.
                return user
        except (KeyError, TypeError, ValueError):
            # Defensive: if exp is malformed, fall back to capped TTL.
            pass

        cache.set(cache_key, user, timeout=ttl)
        return user
