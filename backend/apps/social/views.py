"""
views.py -- apps/social (Phase 15 SOC1 + SOC2)

SOC1 — 4 endpoints for user-to-user asymmetric follow:
  POST   /api/v1/users/{user_id}/follow/      -- 201/200/400/404
  DELETE /api/v1/users/{user_id}/follow/      -- 204/404
  GET    /api/v1/users/{user_id}/followers/   -- paginated list (AllowAny)
  GET    /api/v1/users/{user_id}/following/   -- paginated list (AllowAny)

SOC2 — 2 endpoints for project reaction (single-tier):
  POST   /api/v1/projects/{project_id}/react/  -- 201/200/403/404
  DELETE /api/v1/projects/{project_id}/react/  -- 204/403/404

SOC3 — 2 endpoints for Office follow:
  POST   /api/v1/offices/{office_id}/follow/   -- 201/200/404
  DELETE /api/v1/offices/{office_id}/follow/   -- 204/404

Counter caches (UserProfile.follower_count / following_count,
Project.reaction_count, Office.follower_count) are managed exclusively by
signal receivers in models.py (post_save / post_delete on Follow /
Reaction / OfficeFollow). This covers both explicit view-level deletes and
CASCADE deletes triggered by user/project/office
account removal — no counter drift possible.
"""
import logging

from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import UserRateThrottle
from rest_framework.views import APIView

from apps.accounts.models import UserProfile
from apps.accounts.serializers import UserMiniSerializer
from apps.social.models import Follow, OfficeFollow, Reaction

logger = logging.getLogger('apps.social')

_PAGE_SIZE_DEFAULT = 50
_PAGE_SIZE_MAX = 50


class FollowWriteThrottle(UserRateThrottle):
    """60 follow/unfollow actions per user per minute — prevents mass-follow bots."""
    scope = 'follow_write'


def _paginate_queryset(qs, request):
    """Minimal inline pagination: page (1-indexed), page_size (capped at 50).

    Returns (items, meta_dict).
    """
    try:
        page = max(1, int(request.query_params.get('page', 1)))
    except (ValueError, TypeError):
        page = 1
    try:
        page_size = min(_PAGE_SIZE_MAX, max(1, int(request.query_params.get('page_size', _PAGE_SIZE_DEFAULT))))
    except (ValueError, TypeError):
        page_size = _PAGE_SIZE_DEFAULT

    total = qs.count()
    offset = (page - 1) * page_size
    items = list(qs[offset: offset + page_size])
    has_more = (offset + page_size) < total
    return items, {'page': page, 'page_size': page_size, 'has_more': has_more, 'total': total}


class FollowView(APIView):
    """POST + DELETE /api/v1/users/{user_id}/follow/"""

    permission_classes = [IsAuthenticated]
    throttle_classes = [FollowWriteThrottle]

    def post(self, request, user_id):
        """Follow a user.

        Returns:
          201 {follower_count, following: true} -- new follow created
          200 {follower_count, following: true} -- already following (idempotent)
          400 {detail}                           -- self-follow attempt
          404                                    -- user not found
        """
        followee = get_object_or_404(UserProfile, user__id=user_id)
        requester = getattr(request.user, 'profile', None)
        if requester is None:
            return Response({'detail': 'Profile not found.'}, status=status.HTTP_403_FORBIDDEN)

        if requester.pk == followee.pk:
            return Response({'detail': 'Cannot follow yourself.'}, status=status.HTTP_400_BAD_REQUEST)

        _follow, created = Follow.objects.get_or_create(
            follower=requester,
            followee=followee,
        )
        # Counter update is handled by _follow_post_save signal when created=True.

        followee.refresh_from_db(fields=['follower_count'])
        response_status = status.HTTP_201_CREATED if created else status.HTTP_200_OK
        return Response(
            {'follower_count': followee.follower_count, 'following': True},
            status=response_status,
        )

    def delete(self, request, user_id):
        """Unfollow a user.

        Returns:
          204 no body -- unfollowed (counter decremented by signal)
          404         -- not following, or user not found
        """
        followee = get_object_or_404(UserProfile, user__id=user_id)
        requester = getattr(request.user, 'profile', None)
        if requester is None:
            return Response({'detail': 'Profile not found.'}, status=status.HTTP_403_FORBIDDEN)

        deleted_count, _ = Follow.objects.filter(
            follower=requester, followee=followee
        ).delete()
        # _follow_post_delete signal handles counter decrement per deleted instance.

        if deleted_count == 0:
            return Response({'detail': 'Not following.'}, status=status.HTTP_404_NOT_FOUND)
        return Response(status=status.HTTP_204_NO_CONTENT)


class OfficeFollowView(APIView):
    """POST + DELETE /api/v1/offices/{office_id}/follow/"""

    permission_classes = [IsAuthenticated]
    throttle_classes = [FollowWriteThrottle]

    def post(self, request, office_id):
        from apps.profiles.models import Office
        office = get_object_or_404(Office, office_id=office_id)
        requester = getattr(request.user, 'profile', None)
        if requester is None:
            return Response({'detail': 'Profile not found.'}, status=status.HTTP_403_FORBIDDEN)

        _follow, created = OfficeFollow.objects.get_or_create(
            follower=requester,
            followee=office,
        )
        # Counter update is handled by _office_follow_post_save signal when created=True.

        office.refresh_from_db(fields=['follower_count'])
        response_status = status.HTTP_201_CREATED if created else status.HTTP_200_OK
        return Response(
            {'follower_count': office.follower_count, 'following': True},
            status=response_status,
        )

    def delete(self, request, office_id):
        from apps.profiles.models import Office
        office = get_object_or_404(Office, office_id=office_id)
        requester = getattr(request.user, 'profile', None)
        if requester is None:
            return Response({'detail': 'Profile not found.'}, status=status.HTTP_403_FORBIDDEN)

        deleted_count, _ = OfficeFollow.objects.filter(
            follower=requester, followee=office
        ).delete()
        # _office_follow_post_delete signal handles counter decrement per deleted instance.

        if deleted_count == 0:
            return Response({'detail': 'Not following.'}, status=status.HTTP_404_NOT_FOUND)
        office.refresh_from_db(fields=['follower_count'])
        return Response(status=status.HTTP_204_NO_CONTENT)


class FollowersListView(APIView):
    """GET /api/v1/users/{user_id}/followers/ -- users who follow this user."""
    permission_classes = [AllowAny]

    def get(self, request, user_id):
        target = get_object_or_404(UserProfile, user__id=user_id)
        qs = (
            UserProfile.objects
            .filter(following_set__followee=target)
            .select_related('user')
            .order_by('-following_set__created_at')
        )
        items, meta = _paginate_queryset(qs, request)
        return Response({
            'results': UserMiniSerializer(items, many=True).data,
            **meta,
        })


class FollowingListView(APIView):
    """GET /api/v1/users/{user_id}/following/ -- users this user follows."""
    permission_classes = [AllowAny]

    def get(self, request, user_id):
        target = get_object_or_404(UserProfile, user__id=user_id)
        qs = (
            UserProfile.objects
            .filter(follower_set__follower=target)
            .select_related('user')
            .order_by('-follower_set__created_at')
        )
        items, meta = _paginate_queryset(qs, request)
        return Response({
            'results': UserMiniSerializer(items, many=True).data,
            **meta,
        })


# ---------------------------------------------------------------------------
# SOC2 — Project Reaction (Phase 15)
# ---------------------------------------------------------------------------

class ReactionWriteThrottle(UserRateThrottle):
    """60 react/unreact actions per user per minute — prevents bulk-reaction abuse."""
    scope = 'reaction_write'


class ReactionView(APIView):
    """POST + DELETE /api/v1/projects/{project_id}/react/

    POST applies a private-visibility gate (private + non-owner = 403) to
    block new reactions on private projects. DELETE has no visibility gate:
    a user always has sovereignty over their own reaction row regardless of
    the project's current visibility (handles public→private flip cleanly,
    avoiding orphan reactions).

    POST:
      201 {reaction_count, reacted: true} -- new reaction created
      200 {reaction_count, reacted: true} -- already reacted (idempotent)
      403 {detail}                         -- private project + non-owner
      404                                  -- project not found

    DELETE:
      204                                  -- reaction removed; count decremented by signal
      404 {detail}                         -- not reacted, or project not found
    """

    permission_classes = [IsAuthenticated]
    throttle_classes = [ReactionWriteThrottle]

    def post(self, request, project_id):
        from apps.recommendation.models import Project
        requester = getattr(request.user, 'profile', None)
        if requester is None:
            return Response({'detail': 'Profile not found.'}, status=status.HTTP_403_FORBIDDEN)

        project = get_object_or_404(Project, project_id=project_id)
        if project.visibility != 'public' and project.user_id != requester.pk:
            return Response({'detail': 'Forbidden'}, status=status.HTTP_403_FORBIDDEN)

        _reaction, created = Reaction.objects.get_or_create(
            user=requester,
            project=project,
        )
        # Counter update handled by _reaction_post_save signal when created=True.

        project.refresh_from_db(fields=['reaction_count'])
        response_status = status.HTTP_201_CREATED if created else status.HTTP_200_OK
        return Response(
            {'reaction_count': project.reaction_count, 'reacted': True},
            status=response_status,
        )

    def delete(self, request, project_id):
        from apps.recommendation.models import Project
        requester = getattr(request.user, 'profile', None)
        if requester is None:
            return Response({'detail': 'Profile not found.'}, status=status.HTTP_403_FORBIDDEN)

        # No visibility gate on DELETE: users may always retract their own
        # reaction even after the project owner flips visibility to private.
        project = get_object_or_404(Project, project_id=project_id)

        deleted_count, _ = Reaction.objects.filter(
            user=requester, project=project
        ).delete()
        # _reaction_post_delete signal handles counter decrement per deleted instance.

        if deleted_count == 0:
            return Response({'detail': 'Not reacted.'}, status=status.HTTP_404_NOT_FOUND)
        return Response(status=status.HTTP_204_NO_CONTENT)


class ProjectReactorsListView(APIView):
    """GET /api/v1/projects/{project_id}/reactors/

    Users who reacted to a project.

    Visibility gate (mirrors POST):
      - public project: anyone can list (200)
      - private project + owner viewing: 200 with full list
      - private project + non-owner / anonymous: 403

    Query params:
      page (default 1), page_size (default 50, max 50)
      same as _paginate_queryset.

    Response 200:
      {results: [UserMiniSerializer...], page, page_size, has_more, total}
    """
    permission_classes = [AllowAny]

    def get(self, request, project_id):
        from apps.recommendation.models import Project
        project = get_object_or_404(Project, project_id=project_id)

        # Visibility gate mirrors POST in ReactionView.
        if project.visibility != 'public':
            if request.user.is_authenticated:
                requester = getattr(request.user, 'profile', None)
            else:
                requester = None
            if requester is None or project.user_id != requester.pk:
                return Response(
                    {'detail': 'Forbidden'},
                    status=status.HTTP_403_FORBIDDEN,
                )

        qs = (
            UserProfile.objects
            .filter(reactions__project=project)
            .select_related('user')
            .order_by('-reactions__created_at')
        )
        items, meta = _paginate_queryset(qs, request)
        return Response({
            'results': UserMiniSerializer(items, many=True).data,
            **meta,
        })
