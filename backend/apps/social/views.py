"""
views.py -- apps/social (Phase 15 SOC2)

SOC2 — 2 endpoints for project reaction (single-tier):
  POST   /api/v1/projects/{project_id}/react/  -- 201/200/403/404
  DELETE /api/v1/projects/{project_id}/react/  -- 204/403/404

Project.reaction_count is managed exclusively by signal receivers in
models.py (post_save / post_delete on Reaction). This covers both explicit
view-level deletes and CASCADE deletes triggered by user/project account
removal — no counter drift possible.
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
from apps.social.models import Reaction
from apps.recommendation.caches import evict_project_detail

logger = logging.getLogger('apps.social')

_PAGE_SIZE_DEFAULT = 50
_PAGE_SIZE_MAX = 50


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
        if created:
            # reaction_count changed — evict project detail cache (BACK-BOARD-PERF-1)
            evict_project_detail(str(project_id))
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
        # reaction_count changed — evict project detail cache (BACK-BOARD-PERF-1)
        evict_project_detail(str(project_id))
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


class UserSavedStudiosView(APIView):
    """GET /api/v1/users/<int:user_id>/saved_studios/

    Returns list of architects the user follows (ArchitectFollow records),
    enriched with name + logo_url from canonical_v2_architects (buildings DB).
    Public endpoint — any authenticated user can view any user's saved studios.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request, user_id):
        from apps.social.models import ArchitectFollow
        from django.db import connections

        follows = list(
            ArchitectFollow.objects.filter(follower__user_id=user_id)
            .order_by('-followed_at')
            .values('architect_id', 'followed_at')
        )
        if not follows:
            return Response([], status=status.HTTP_200_OK)

        arch_ids = [f['architect_id'] for f in follows]

        with connections['buildings'].cursor() as cur:
            cur.execute(
                """
                SELECT canonical_arch_id, canonical_name, logo_url, primary_country
                FROM canonical_v2_architects
                WHERE canonical_arch_id = ANY(%s)
                """,
                [arch_ids],
            )
            rows = cur.fetchall()

        meta_map = {row[0]: row for row in rows}

        with connections['buildings'].cursor() as cur:
            cur.execute(
                """
                SELECT DISTINCT ON (unnested_id) unnested_id AS architect_id,
                       cover_image_url_default
                FROM canonical_v2_buildings,
                     unnest(architect_canonical_ids) AS unnested_id
                WHERE unnested_id = ANY(%s)
                  AND is_publishable = true
                ORDER BY unnested_id, project_year DESC NULLS LAST
                """,
                [arch_ids],
            )
            cover_rows = cur.fetchall()

        cover_map = {row[0]: row[1] for row in cover_rows}

        result = []
        for f in follows:
            arch_id = f['architect_id']
            row = meta_map.get(arch_id)
            result.append({
                'architect_id': arch_id,
                'name': row[1] if row else '',
                'logo_url': row[2] if row and row[2] else '',
                'primary_country': row[3] if row and row[3] else '',
                'followed_at': f['followed_at'],
                'cover_image_url': cover_map.get(arch_id, ''),
            })

        return Response(result, status=status.HTTP_200_OK)
