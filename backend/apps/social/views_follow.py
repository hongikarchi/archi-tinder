"""views_follow.py -- apps/social (SNS-FOLLOW-1) one-way user-to-user follow.

  GET    /api/v1/users/<user_id>/follow/ -> 200 status body
  POST   /api/v1/users/<user_id>/follow/ -> 201 created / 200 already following / 400 unavailable
  DELETE /api/v1/users/<user_id>/follow/ -> 204 (always)

`user_id` is the auth User id (== UserProfile.user_id), the API-wide user id.
Integer PKs in URLs follow the existing pattern; non-enumerable ids are tracked
in #391.

Gate order: FollowEnabled (404 when FOLLOW_ENABLED is off, even anonymous) ->
IsAuthenticated -> IsVerifiedUser for non-safe methods (a guest gets the
existing `verify_required` 403 the frontend already handles).

PRIVACY: `can_follow=false` carries no reason (blocked either way, guest or
opted-out target and self are indistinguishable) except `reason='verify_required'`
for a guest REQUESTER (their own state). Nothing here ever reveals that the
target blocked the requester: `blocked_by_me` is the requester's own action only,
and `has_conversation` is False for a closed conversation (a block closes it), so a
target-side block reads exactly like "no conversation".
"""
from django.db import IntegrityError, transaction
from django.http import Http404
from rest_framework import status
from rest_framework.permissions import SAFE_METHODS, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.permissions import IsVerifiedUser
from apps.messaging import services as messaging_services

from . import services
from .models import UserFollow
from .permissions import FollowEnabled
from .throttling import FollowStatusReadThrottle, FollowWriteThrottle


def follow_status(me, target):
    """Status body for `me` looking at `target` (never reveals target-blocked-me).

    `has_conversation` is the requester's own info: True only when a messaging
    Conversation exists for the pair and is not closed (closed_at is null). It is
    independent of who follows whom (the peer who does not follow still sees it
    once they were messaged). Always False for self.
    """
    is_self = me.pk == target.pk
    guest_requester = services.is_guest_account(me)
    conv = None if is_self else messaging_services.find_conversation(me, target)
    body = {
        'is_following': False if is_self else services.is_following(me, target),
        'is_followed_by': False if is_self else services.is_following(target, me),
        'can_follow': (not is_self) and (not guest_requester) and services.can_follow(me, target),
        'blocked_by_me': False if is_self else messaging_services.has_blocked(me, target),
        'has_conversation': conv is not None and conv.closed_at is None,
    }
    if guest_requester and not is_self:
        body['reason'] = 'verify_required'
    return body


class UserFollowView(APIView):
    """GET/POST/DELETE /api/v1/users/<user_id>/follow/"""

    def get_permissions(self):
        perms = [FollowEnabled(), IsAuthenticated()]
        if self.request.method not in SAFE_METHODS:
            perms.append(IsVerifiedUser())
        return perms

    def get_throttles(self):
        if self.request.method in SAFE_METHODS:
            return [FollowStatusReadThrottle()]
        return [FollowWriteThrottle()]

    @staticmethod
    def _me(request):
        profile = getattr(request.user, 'profile', None)
        if profile is None:
            raise Http404()
        return profile

    @staticmethod
    def _target(user_id):
        target = messaging_services.get_profile_by_auth_id(user_id)
        if target is None:
            raise Http404()
        return target

    def get(self, request, user_id):
        me = self._me(request)
        target = self._target(user_id)
        return Response(follow_status(me, target))

    def post(self, request, user_id):
        me = self._me(request)
        target = self._target(user_id)

        if services.is_following(me, target):
            # Idempotent, even if can_follow is now false (opt-out / guest target).
            return Response(follow_status(me, target), status=status.HTTP_200_OK)
        if not services.can_follow(me, target):
            # One identical body for self / blocked / guest target / opt-out.
            return Response({'detail': 'unavailable'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            with transaction.atomic():
                edge = UserFollow.objects.create(follower=me, following=target)
                # A block committed between can_follow() and the insert would
                # leave an edge BlockView already swept: re-check and undo.
                if messaging_services.is_blocked_between(me, target):
                    edge.delete()
                    edge = None
        except IntegrityError:
            # Concurrent duplicate: treat as already following.
            return Response(follow_status(me, target), status=status.HTTP_200_OK)
        if edge is None:
            return Response({'detail': 'unavailable'}, status=status.HTTP_400_BAD_REQUEST)
        services.evict_follow_counts_cache(me, target)
        return Response(follow_status(me, target), status=status.HTTP_201_CREATED)

    def delete(self, request, user_id):
        me = self._me(request)
        target = self._target(user_id)
        deleted, _ = UserFollow.objects.filter(follower=me, following=target).delete()
        if deleted:
            services.evict_follow_counts_cache(me, target)
        return Response(status=status.HTTP_204_NO_CONTENT)
