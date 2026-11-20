"""Permission gating the follow API behind FOLLOW_ENABLED (SNS-FOLLOW-1)."""
from django.conf import settings
from rest_framework.exceptions import NotFound
from rest_framework.permissions import BasePermission


class FollowEnabled(BasePermission):
    """404 (not 403) for every follow endpoint while FOLLOW_ENABLED is OFF.

    Read at request time so `override_settings` / env flips apply without reload.
    Must be listed FIRST in permission_classes so even unauthenticated callers
    see the same 404 as authenticated ones. Mirrors messaging.permissions.MessagingEnabled.
    """

    def has_permission(self, request, view):
        if not getattr(settings, 'FOLLOW_ENABLED', False):
            raise NotFound()
        return True
