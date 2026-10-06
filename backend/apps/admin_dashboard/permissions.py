"""IsAdminOperator -- the single admin gate for the whole API (ADMIN-DASH-1).

An admin operator must satisfy ALL of:
  1. authenticated
  2. ``user.is_staff`` (granted out-of-band via ``manage.py grant_admin``)
  3. lowercased ``user.email`` in ``settings.ADMIN_EMAILS`` (env allow-list;
     empty/unset -> nobody)
  4. profile is not a guest (``is_guest`` == "not Google-verified", LOGIN-ONBOARD-1)
  5. a ``SocialAccount(provider='google')`` row exists for the profile

``SocialAccount`` stores no email, so (3) compares the mutable-looking ``User.email``.
That is safe ONLY because no endpoint lets a user set ``User.email`` to an arbitrary
value (audited 2026-10-06, ADMIN-DASH-1):
  - register / guest-login create users with ``email=''``;
  - ``GuestPromoteView`` (Google, ``email_verified`` required) and ``LinkEmailView``
    (Google, ``email_verified`` required) are the only writers, and both copy the
    Google-verified address; no profile/settings serializer exposes ``email``.
  - Kakao / Naver login only link by email; they never write ``User.email``.
If a future endpoint can change ``User.email``, compare against the Google-sourced
email instead (and add it to this audit note).

Denials are logged with ``logger.warning`` ONLY -- never a DB row (the permission
check runs before the throttle, so a DB write here would be a DB-fill vector).

Kept dependency-light (no model imports at module level) so ``accounts`` can import
``is_admin_operator`` without a circular import.
"""
import logging

from django.conf import settings
from rest_framework.permissions import BasePermission

logger = logging.getLogger('apps.admin_dashboard')


def is_admin_operator(user):
    """Pure predicate shared by IsAdminOperator and the /auth/me/ ``is_admin`` flag."""
    if user is None or not getattr(user, 'is_authenticated', False):
        return False
    if not getattr(user, 'is_staff', False):
        return False
    allow = getattr(settings, 'ADMIN_EMAILS', None) or ()
    email = (getattr(user, 'email', '') or '').strip().lower()
    if not email or email not in allow:
        return False
    # Local import: avoids a circular import with apps.accounts at module load.
    from apps.accounts.models import SocialAccount
    profile = getattr(user, 'profile', None)
    if profile is None or profile.is_guest:
        return False
    return SocialAccount.objects.filter(user=profile, provider='google').exists()


class IsAdminOperator(BasePermission):
    message = 'Admin access required.'

    def has_permission(self, request, view):
        user = request.user
        if not user or not user.is_authenticated:
            return False  # DRF turns this into 401 (JWT authenticator has a header)
        if is_admin_operator(user):
            return True
        logger.warning('admin access denied: user=%s path=%s', user.pk, request.path)
        return False
