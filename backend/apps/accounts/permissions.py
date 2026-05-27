"""Custom DRF permissions for ArchiTinder.

FULL-LOGIN-REDESIGN-1 (PR 1): IsVerifiedUser rejects guest (unverified) users
with 403 and a machine-readable detail payload.

Usage example (future callers — social/profiles endpoints):
    from apps.accounts.permissions import IsVerifiedUser

    class MyView(APIView):
        permission_classes = [IsAuthenticated, IsVerifiedUser]

The verify-gate in ProjectListCreateView uses an inline check instead of this
class (board-limit gate logic is more nuanced than a flat permission reject),
but IsVerifiedUser is available so future views can adopt it without duplication.
"""

from rest_framework.permissions import BasePermission


class IsVerifiedUser(BasePermission):
    """Deny access to guest (is_guest=True) users.

    Returns 403 with:
        {'detail': 'verify_required', 'reason': 'guest_not_allowed'}
    """

    message = {'detail': 'verify_required', 'reason': 'guest_not_allowed'}

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        try:
            return not request.user.profile.is_guest
        except Exception:
            return True  # no profile — let IsAuthenticated handle it
