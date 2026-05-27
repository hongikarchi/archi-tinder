"""Custom DRF throttle classes for ArchiTinder accounts app.

FULL-LOGIN-REDESIGN-1 (PR 1): GuestLoginThrottle limits guest-account creation
to 3 requests per minute per IP address (tighter than the codex baseline of
10/min, per user decision Q5).
"""

from rest_framework.throttling import AnonRateThrottle, UserRateThrottle


class GuestLoginThrottle(AnonRateThrottle):
    """3 guest-account creations per minute per IP.

    Codex used 10/min; user decision Q5 tightened to 3/min.
    Subclasses AnonRateThrottle because /auth/guest/ is AllowAny.
    scope is set so DEFAULT_THROTTLE_RATES can override if needed.
    """
    scope = 'guest_login'
    rate = '3/min'


class GuestPromoteThrottle(UserRateThrottle):
    """5 promote calls per minute per authenticated user.

    AnonRateThrottle is a no-op on IsAuthenticated endpoints (anon throttle
    skips authenticated callers), so UserRateThrottle is required here.
    Tighter than guest login because promote performs Google OAuth exchange.
    """
    scope = 'guest_promote'
    rate = '5/min'
