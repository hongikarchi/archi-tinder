import logging

from django.conf import settings
from django.db import DatabaseError, connections, transaction
from django.db.models import IntegerField, OuterRef, Subquery
from django.db.models.expressions import RawSQL
from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from ..models import AnalysisSession, Project
from ..serializers import (
    ProjectListSerializer,
    ProjectPatchResponseSerializer,
    ProjectSerializer,
    ProjectSelfUpdateSerializer,
    PublicProjectListSerializer,
)
from ..caches import (
    evict_taste,
    get_or_build_projects_list,
    evict_projects_list,
    evict_discovery_feed,
    evict_user_profile_detail,
    evict_project_detail,
    get_project_detail_cache_key,
    PROJECT_DETAIL_TTL,
    PROJECT_RECOMMENDATIONS_TTL,
    get_project_recommendations_cache_key,
)
from ..report_signature import liked_signature
from ..services import session_service
from ..throttles import ProjectRecommendationsThrottle
from ..perf_timing import endpoint, stage
from ._shared import _get_profile

logger = logging.getLogger('apps.recommendation')
RC = settings.RECOMMENDATION


def _entry_id(item):
    """Building id of a liked_ids/saved_ids entry; tolerates legacy plain strings."""
    if isinstance(item, dict):
        return item.get('id')
    if isinstance(item, str):
        return item
    return None


def _count_renderable(building_ids):
    """Number of ids that exist and are publishable in the buildings DB.

    Liked ids that are missing / unpublishable never render, so they must not
    keep the last-liked guard open. If the buildings DB is unreachable, fall
    back to the raw id count (fail open: do not block the user's edit).
    """
    ids = list(dict.fromkeys(building_ids))
    if not ids:
        return 0
    try:
        with connections['buildings'].cursor() as cur:
            cur.execute(
                'SELECT count(*) FROM canonical_v2_buildings'
                ' WHERE is_publishable = true AND canonical_bld_id = ANY(%s)',
                [ids],
            )
            return cur.fetchone()[0]
    except DatabaseError:
        logger.warning('last_liked guard: buildings lookup failed; using raw count', exc_info=True)
        return len(ids)


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
                        .filter(user=profile, is_temp=False)
                        .select_related('user__user')
                        # PERF-1 change C: heavy LLM JSON not consumed by list view.
                        # BACK-LLM-2: conversation_history can be up to 64 KB — defer it too.
                        .defer('analysis_report', 'conversation_history', 'axis_scores')
                        .annotate(
                            _latest_session_id=_latest_sid_sq,
                            _latest_like_count=_latest_lc_sq,
                            _latest_session_created_at=_latest_ca_sq,
                        )
                        .order_by('-updated_at')
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

        # FULL-LOGIN-REDESIGN-1: guest users may create up to 3 boards.
        # The 4th attempt triggers the verify-gate — frontend catches this 403
        # and opens VerifyGateModal to prompt Google OAuth promotion.
        # Gate is on post() only; get() (list) is not restricted.
        if profile.is_guest and Project.objects.filter(user=profile).count() >= 3:
            return Response(
                {'detail': 'verify_required', 'reason': 'board_limit_reached', 'limit': 3},
                status=status.HTTP_403_FORBIDDEN,
            )

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
        if not is_owner and (project.visibility != 'public' or project.is_temp):
            return Response({'detail': 'Forbidden'}, status=status.HTTP_403_FORBIDDEN)
        # 2026-09-28: stop recomputing axis_scores on read. Detail GET must not
        # touch connections['buildings'] or write -- a legacy-format stored
        # axis_scores is shown as-is; it is only upgraded to the new
        # embedding-projection shape on report generate/regenerate.
        data = ProjectSerializer(project, context={'request': request}).data
        if not is_owner:
            data.pop('conversation_history', None)
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
            # Defer the heavy blobs the PATCH never reads (report_image is
            # ~270 KB base64); save() then writes only the loaded fields.
            project = get_object_or_404(
                Project.objects.select_for_update().filter(user=profile)
                .defer('report_image', 'report_image_mime', 'analysis_report', 'conversation_history'),
                project_id=pk,
            )
            # Ownership is already enforced by the filter above; reuse the
            # request's profile instead of lazy-loading project.user(.user).
            project.user = profile

            # A board must keep at least one liked building: the persona report
            # is generated from liked_ids. Reject before any mutation/eviction.
            if remove_ids is not None and project.liked_ids:
                remove_set_guard = set(remove_ids)
                liked_entry_ids = (_entry_id(item) for item in project.liked_ids)
                remaining = [
                    i for i in liked_entry_ids
                    if i is not None and i not in remove_set_guard
                ]
                if not _count_renderable(remaining):
                    return Response(
                        {'detail': 'last_liked_building'},
                        status=status.HTTP_400_BAD_REQUEST,
                    )

            serializer = None
            if schema_data:
                serializer = ProjectSelfUpdateSerializer(project, data=schema_data, partial=True)
                serializer.is_valid(raise_exception=True)
                # Guest promote-limit: a temp→permanent transition must not let a
                # guest bypass the 3-board cap by hoarding temp boards.
                promoting = (
                    serializer.validated_data.get('is_temp') is False
                    and project.is_temp
                )
                if promoting and profile.is_guest:
                    permanent_count = Project.objects.filter(
                        user=profile, is_temp=False,
                    ).count()
                    if permanent_count >= 3:
                        return Response(
                            {'detail': 'verify_required', 'reason': 'board_limit_reached', 'limit': 3},
                            status=status.HTTP_403_FORBIDDEN,
                        )
                if promoting:
                    evict_taste(profile.id)
                    evict_discovery_feed(profile.id)

            if remove_ids is not None:
                remove_set = set(remove_ids)
                update_fields = ['liked_ids', 'saved_ids', 'updated_at']
                # FULL-REPORT-UI-1: a legacy report has no source_signature, so
                # it could never be flagged stale. Stamp it with the liked set
                # as it is BEFORE this removal so the removal makes it stale.
                if (
                    isinstance(project.final_report, dict)
                    and project.final_report
                    and not project.final_report.get('source_signature')
                ):
                    project.final_report = {
                        **project.final_report,
                        'source_signature': liked_signature(project.liked_ids),
                    }
                    update_fields.append('final_report')
                project.liked_ids = [item for item in project.liked_ids if _entry_id(item) not in remove_set]
                project.saved_ids = [item for item in project.saved_ids if _entry_id(item) not in remove_set]
                project.save(update_fields=update_fields)
                evict_taste(profile.id)
                evict_discovery_feed(profile.id)
            if serializer is not None:
                serializer.save()

        # No refresh_from_db(): the locked instance was mutated and saved in
        # this transaction, so it is already current (updated_at set by save()).
        evict_projects_list(profile.id)
        evict_user_profile_detail(profile.user.id)
        evict_project_detail(str(pk))
        return Response(ProjectPatchResponseSerializer(project, context={'request': request}).data)

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


class ProjectRecommendationsView(APIView):
    """GET /api/v1/projects/{project_id}/recommendations/ — FULL-REPORT-UI-1.

    Recommended buildings of a board for EVERYONE who may see the board (owner
    and non-owner). SessionResultView stays owner-only; this endpoint exposes
    only the predicted cards, never the session id.

    Visibility mirrors ProjectDetailView.get exactly: owner or
    visibility == 'public'; otherwise 403 {'detail': 'Forbidden'}; unknown
    project 404. Response: {'predicted_like_images': [card, ...]} — same cards
    and order as SessionResultView's predicted images. Empty list when the
    board has no session / no like vectors. Cached per project (see
    get_project_recommendations_cache_key).
    """
    permission_classes = [IsAuthenticated]
    throttle_classes = [ProjectRecommendationsThrottle]

    def get(self, request, pk):
        from django.core.cache import cache as _cache

        profile = _get_profile(request)
        project = get_object_or_404(Project.objects.only('project_id', 'user_id', 'visibility', 'is_temp'), project_id=pk)
        is_owner = profile and project.user_id == profile.pk
        if not is_owner and (project.visibility != 'public' or project.is_temp):
            return Response({'detail': 'Forbidden'}, status=status.HTTP_403_FORBIDDEN)

        cache_key = get_project_recommendations_cache_key(str(pk))
        cached = _cache.get(cache_key)
        if cached is not None:
            return Response(cached)

        predicted = []
        session = (
            AnalysisSession.objects
            .filter(project_id=pk)
            .order_by('-created_at')
            .first()
        )
        if session is not None and session.like_vectors:
            predicted = session_service.build_predicted_cards(session)[0]

        data = {'predicted_like_images': predicted}
        _cache.set(cache_key, data, PROJECT_RECOMMENDATIONS_TTL)
        return Response(data)


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
            .filter(user=target_profile, is_temp=False)
            .select_related('user__user')
            # PERF-1 change C: heavy LLM JSON not consumed by list view.
            # BACK-LLM-2: conversation_history can be up to 64 KB — defer it too.
            # BACK-PRIVACY-1: report_image (~200KB base64) deferred as well — safe
            # only because THIS endpoint serializes with PublicProjectListSerializer
            # for every caller, which never reads the field.
            .defer('analysis_report', 'conversation_history', 'axis_scores',
                   'report_image', 'report_image_mime')
            .annotate(
                _latest_session_id=_latest_sid_sq,
                _latest_like_count=_latest_lc_sq,
                _latest_session_created_at=_latest_ca_sq,
            )
            .order_by('-updated_at')
        )
        if not is_owner:
            qs = qs.filter(visibility='public')
        start = (page - 1) * page_size
        # PERF-1 change C: page_size+1 trick eliminates the separate COUNT query.
        chunk_plus_one = list(qs[start:start + page_size + 1])
        has_more = len(chunk_plus_one) > page_size
        chunk = chunk_plus_one[:page_size]
        return Response({
            # BACK-PRIVACY-1: PublicProjectListSerializer (not ProjectListSerializer)
            # — this endpoint is AllowAny; must not leak report_image/_mime base64
            # blobs to anonymous callers. Owner GET /projects/ keeps the full
            # ProjectListSerializer (App.jsx:929 login project-sync needs it).
            'results':  PublicProjectListSerializer(chunk, many=True, context={'request': request}).data,
            'total':    None,   # deprecated — frontend uses has_more
            'page':     page,
            'has_more': has_more,
        })
