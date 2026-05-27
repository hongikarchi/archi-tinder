import logging

from django.conf import settings
from django.db import transaction
from django.db.models import IntegerField, OuterRef, Subquery
from django.db.models.expressions import RawSQL
from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from ..models import AnalysisSession, Project
from ..serializers import ProjectListSerializer, ProjectSerializer, ProjectSelfUpdateSerializer
from ..caches import (
    evict_taste,
    get_or_build_projects_list,
    evict_projects_list,
    evict_discovery_feed,
    evict_user_profile_detail,
    evict_project_detail,
    get_project_detail_cache_key,
    PROJECT_DETAIL_TTL,
)
from ..perf_timing import endpoint, stage
from ._shared import _get_profile

logger = logging.getLogger('apps.recommendation')
RC = settings.RECOMMENDATION


# ── Projects ──────────────────────────────────────────────────────────────────

class ProjectListCreateView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        with endpoint('projects_list'):
            with stage('get_profile'):
                profile = _get_profile(request)
            if not profile:
                return Response({'results': [], 'total': None, 'has_more': False})
            try:
                page      = max(1, int(request.query_params.get('page', 1)))
                page_size = min(max(1, int(request.query_params.get('page_size', 50))), 50)
            except (ValueError, TypeError):
                page, page_size = 1, 50

            def _build():
                with stage('build_subqueries'):
                    _latest_sid_sq = Subquery(
                        AnalysisSession.objects.filter(project=OuterRef('pk'))
                        .order_by('-created_at').values('session_id')[:1]
                    )
                    # PERF-1 change A: replace full like_vectors fetch with a count.
                    # jsonb_array_length on the JSONField (mapped to jsonb in Postgres)
                    # returns only an int instead of transferring the entire 384-dim
                    # float list × N likes across the wire.
                    _latest_lc_sq = Subquery(
                        AnalysisSession.objects
                        .filter(project=OuterRef('pk'))
                        .order_by('-created_at')
                        .annotate(_lc=RawSQL('jsonb_array_length(like_vectors)', []))
                        .values('_lc')[:1],
                        output_field=IntegerField(),
                    )
                    _latest_ca_sq = Subquery(
                        AnalysisSession.objects.filter(project=OuterRef('pk'))
                        .order_by('-created_at').values('created_at')[:1]
                    )
                with stage('build_qs'):
                    qs = (
                        Project.objects
                        .filter(user=profile)
                        .select_related('user__user')
                        # PERF-1 change C: heavy LLM JSON not consumed by list view.
                        .defer('analysis_report')
                        .annotate(
                            _latest_session_id=_latest_sid_sq,
                            _latest_like_count=_latest_lc_sq,
                            _latest_session_created_at=_latest_ca_sq,
                        )
                        .order_by('-created_at')
                    )
                start = (page - 1) * page_size
                with stage('fetch_chunk_plus_one'):
                    # PERF-1 change C: page_size+1 trick eliminates the separate
                    # COUNT(*) query. has_more is derived from the extra row.
                    chunk_plus_one = list(qs[start:start + page_size + 1])
                has_more = len(chunk_plus_one) > page_size
                chunk = chunk_plus_one[:page_size]
                with stage('serialize', n=len(chunk)):
                    data = ProjectListSerializer(
                        chunk, many=True, context={'request': request}
                    ).data
                return {
                    'results':  list(data),
                    'total':    None,   # deprecated — frontend uses has_more
                    'page':     page,
                    'has_more': has_more,
                }

            with stage('cache_lookup_or_build'):
                payload = get_or_build_projects_list(profile, page, page_size, _build)
            return Response(payload)

    def post(self, request):
        profile = _get_profile(request)
        if not profile:
            return Response({'detail': 'Profile not found'}, status=status.HTTP_404_NOT_FOUND)
        serializer = ProjectSerializer(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        project = serializer.save(user=profile)
        evict_projects_list(profile.id)
        evict_user_profile_detail(profile.user.id)
        evict_project_detail(str(project.project_id))
        logger.info('Project created: %s by user %s', project.project_id, profile.pk)
        return Response(
            ProjectSerializer(project, context={'request': request}).data,
            status=status.HTTP_201_CREATED,
        )


class ProjectDetailView(APIView):
    """GET/PATCH/DELETE /api/v1/projects/{project_id}/ — BOARD1 Phase 13.

    GET:   AllowAny — returns 200 for own or public; 403 for private non-owner.
    PATCH: owner-only — name + visibility only (ProjectSelfUpdateSerializer).
    DELETE: owner-only — returns 404 for cross-user (not 403) to avoid leaking
            project existence to non-owners.
    """
    permission_classes = [AllowAny]

    def get(self, request, pk):
        from django.core.cache import cache as _cache

        profile = _get_profile(request)
        requester_id_for_cache = str(profile.id) if profile else 'anon'

        cache_key = get_project_detail_cache_key(str(pk), requester_id_for_cache)
        cached = _cache.get(cache_key)
        if cached is not None:
            return Response(cached)

        project = get_object_or_404(Project.objects.select_related('user__user'), project_id=pk)
        is_owner = profile and project.user_id == profile.pk
        if not is_owner and project.visibility != 'public':
            return Response({'detail': 'Forbidden'}, status=status.HTTP_403_FORBIDDEN)
        data = ProjectSerializer(project, context={'request': request}).data
        if request.user.is_authenticated and profile:
            from apps.social.models import Reaction
            data['is_reacted'] = Reaction.objects.filter(user=profile, project=project).exists()
        else:
            data['is_reacted'] = False

        _cache.set(cache_key, data, PROJECT_DETAIL_TTL)
        return Response(data)

    def patch(self, request, pk):
        profile = _get_profile(request)
        if not profile:
            return Response({'detail': 'Authentication required'}, status=status.HTTP_401_UNAUTHORIZED)

        # remove_building_ids: remove specified buildings from liked_ids and saved_ids
        remove_ids = request.data.get('remove_building_ids')
        if remove_ids is not None:
            if not isinstance(remove_ids, list) or not all(isinstance(x, str) for x in remove_ids):
                return Response(
                    {'detail': 'remove_building_ids must be a list of strings'},
                    status=status.HTTP_400_BAD_REQUEST,
                )

        # Strip non-schema keys before entering the atomic block.
        schema_data = {k: v for k, v in request.data.items() if k != 'remove_building_ids'}

        with transaction.atomic():
            # Fold ownership into the locked queryset (Defect 3 fix).
            # select_for_update().filter(user=profile) means the lock is only
            # granted when the row belongs to the requesting user — a non-owner
            # request sees 404 without ever acquiring a row lock.
            project = get_object_or_404(
                Project.objects.select_for_update().filter(user=profile),
                project_id=pk,
            )

            serializer = None
            if schema_data:
                serializer = ProjectSelfUpdateSerializer(project, data=schema_data, partial=True)
                serializer.is_valid(raise_exception=True)

            if remove_ids is not None:
                remove_set = set(remove_ids)
                project.liked_ids = [item for item in project.liked_ids if item.get('id') not in remove_set]
                project.saved_ids = [item for item in project.saved_ids if item.get('id') not in remove_set]
                project.save(update_fields=['liked_ids', 'saved_ids'])
                evict_taste(profile.id)
                evict_discovery_feed(profile.id)
            if serializer is not None:
                serializer.save()

        project.refresh_from_db()
        evict_projects_list(profile.id)
        evict_user_profile_detail(profile.user.id)
        evict_project_detail(str(pk))
        return Response(ProjectSerializer(project, context={'request': request}).data)

    def delete(self, request, pk):
        profile = _get_profile(request)
        if not profile:
            return Response({'detail': 'Authentication required'}, status=status.HTTP_401_UNAUTHORIZED)
        # Filter by user=profile so non-owner requests get 404, not 403,
        # matching the security-manager recommendation and ProjectBookmarkView pattern.
        project = get_object_or_404(Project.objects.filter(user=profile), project_id=pk)
        project.delete()
        # Evict AFTER delete: a concurrent GET arriving between the version bump
        # and the row delete would see the live row and cache a phantom payload
        # under the freshly-bumped key (60s phantom-read). Code-review fix-loop.
        evict_project_detail(str(pk))
        evict_projects_list(profile.id)
        evict_user_profile_detail(profile.user.id)
        logger.info('Project deleted: %s', pk)
        return Response(status=status.HTTP_204_NO_CONTENT)


class UserProjectsListView(APIView):
    """GET /api/v1/users/{user_id}/projects/ — BOARD1 Phase 13.

    Non-owner: public projects only.
    Owner: public + private.
    """
    permission_classes = [AllowAny]

    def get(self, request, user_id):
        from apps.accounts.models import UserProfile
        target_profile = get_object_or_404(UserProfile, user__id=user_id)
        requester_profile = _get_profile(request)
        is_owner = requester_profile and requester_profile.pk == target_profile.pk
        try:
            page      = max(1, int(request.query_params.get('page', 1)))
            page_size = min(max(1, int(request.query_params.get('page_size', 50))), 50)
        except (ValueError, TypeError):
            page, page_size = 1, 50
        _latest_sid_sq = Subquery(
            AnalysisSession.objects.filter(project=OuterRef('pk'))
            .order_by('-created_at').values('session_id')[:1]
        )
        # PERF-1 change A: like-count annotation instead of full vector fetch.
        _latest_lc_sq = Subquery(
            AnalysisSession.objects
            .filter(project=OuterRef('pk'))
            .order_by('-created_at')
            .annotate(_lc=RawSQL('jsonb_array_length(like_vectors)', []))
            .values('_lc')[:1],
            output_field=IntegerField(),
        )
        _latest_ca_sq = Subquery(
            AnalysisSession.objects.filter(project=OuterRef('pk'))
            .order_by('-created_at').values('created_at')[:1]
        )
        qs = (
            Project.objects
            .filter(user=target_profile)
            .select_related('user__user')
            # PERF-1 change C: heavy LLM JSON not consumed by list view.
            .defer('analysis_report')
            .annotate(
                _latest_session_id=_latest_sid_sq,
                _latest_like_count=_latest_lc_sq,
                _latest_session_created_at=_latest_ca_sq,
            )
            .order_by('-created_at')
        )
        if not is_owner:
            qs = qs.filter(visibility='public')
        start = (page - 1) * page_size
        # PERF-1 change C: page_size+1 trick eliminates the separate COUNT query.
        chunk_plus_one = list(qs[start:start + page_size + 1])
        has_more = len(chunk_plus_one) > page_size
        chunk = chunk_plus_one[:page_size]
        return Response({
            'results':  ProjectListSerializer(chunk, many=True, context={'request': request}).data,
            'total':    None,   # deprecated — frontend uses has_more
            'page':     page,
            'has_more': has_more,
        })
