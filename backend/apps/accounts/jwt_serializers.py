"""Custom JWT serializer — adds is_guest claim to token payload.

FULL-LOGIN-REDESIGN-1 (PR 1): wired via SIMPLE_JWT['TOKEN_OBTAIN_SERIALIZER']
in config/settings.py.  The claim lets the frontend decode guest status from the
token directly, without a separate /auth/me/ round-trip.

GuestLoginView and GuestPromoteView also inject the claim manually on the access
token they build directly (RefreshToken.for_user path), so this serializer only
matters for the standard simplejwt token-obtain endpoint (if we ever expose it).
It is shipped now to keep the JWT claim consistent regardless of how the token
is issued.
"""

from rest_framework_simplejwt.serializers import TokenObtainPairSerializer


class CustomTokenObtainPairSerializer(TokenObtainPairSerializer):
    """Adds is_guest claim to both refresh and access token payloads."""

    @classmethod
    def get_token(cls, user):
        token = super().get_token(user)
        try:
            token['is_guest'] = user.profile.is_guest
        except Exception:
            # profile missing (e.g. during tests that don't create a profile)
            token['is_guest'] = False
        return token
