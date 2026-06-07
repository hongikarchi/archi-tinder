"""Custom DRF throttle classes for ArchiTinder accounts app.

FULL-LOGIN-REDESIGN-1 (PR 1): GuestLoginThrottle limits guest-account creation
to 3 requests per minute per IP address (tighter than the codex baseline of
10/min, per user decision Q5).

AUTH-LOGIN-1: PasswordLoginThrottle + RegisterThrottle + LinkEmailThrottle
added for handle+password auth and OAuth email-linking endpoints.
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


class RegisterThrottle(AnonRateThrottle):
    """10 registrations per minute per IP.

    AllowAny endpoint — AnonRateThrottle keys on IP.
    Prevents bulk account creation / handle squatting.
    """
    scope = 'register'
    rate = '10/min'


class PasswordLoginThrottle(AnonRateThrottle):
    """10 password-login attempts per minute per IP — brute-force guard.

    AllowAny endpoint, so AnonRateThrottle (keyed on IP) is correct.
    UserRateThrottle would be a no-op before authentication succeeds.
    """
    scope = 'password_login'
    rate = '10/min'


class LinkEmailThrottle(UserRateThrottle):
    """5 link-email calls per minute per authenticated user.

    IsAuthenticated endpoint — must be UserRateThrottle; AnonRateThrottle
    is a no-op on authenticated endpoints (skips authenticated callers).
    Performs a Google OAuth exchange, so tight rate is appropriate.
    """
    scope = 'link_email'
    rate = '5/min'


class SetPasswordThrottle(UserRateThrottle):
    """5 set/change-password calls per minute per authenticated user.

    IsAuthenticated endpoint — UserRateThrottle keys on authenticated user,
    correct here (AnonRateThrottle is a no-op on authenticated endpoints).
    Tight rate because each call performs a current_password check —
    an unbounded rate allows brute-force against a stolen access token.
    """
    scope = 'set_password'
    rate = '5/min'
