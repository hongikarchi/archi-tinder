"""Shared permission gating the whole messaging surface behind MESSAGING_ENABLED (D12)."""
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
