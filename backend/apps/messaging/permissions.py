"""Permissions gating the messaging surface behind MESSAGING_ENABLED (D12) / FOLLOW_ENABLED."""
from django.conf import settings
from rest_framework.exceptions import NotFound
from rest_framework.permissions import BasePermission


class MessagingEnabled(BasePermission):
    """404 (not 403) for every messaging endpoint while the flag is OFF.

    Read at request time so `override_settings` / env flips apply without reload.
    Must be listed FIRST in permission_classes so even unauthenticated callers
    see the same 404 as authenticated ones.
    """

    def has_permission(self, request, view):
        if not getattr(settings, 'MESSAGING_ENABLED', False):
            raise NotFound()
        return True


class MessagingOrFollowEnabled(BasePermission):
    """404 only when BOTH MESSAGING_ENABLED and FOLLOW_ENABLED are off.

    Gates Block / Report: with follow on and messaging off, block is the only
    defence a user has against unwanted followers, so it must stay reachable
    whenever either surface is on. Same listed-FIRST / request-time rules as
    MessagingEnabled.
    """

    def has_permission(self, request, view):
        if not (
            getattr(settings, 'MESSAGING_ENABLED', False)
            or getattr(settings, 'FOLLOW_ENABLED', False)
        ):
            raise NotFound()
        return True
