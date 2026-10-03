import logging
import time
import uuid

from django.conf import settings
from django.core.cache import cache
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from ..models import Project
from .. import services
from ..caches import evict_projects_list, evict_project_detail, evict_user_profile_detail
from ..services.axis_scores import compute_axis_scores
from ..throttles import ReportGenerateThrottle, ReportImageThrottle
from ._shared import _get_profile, _liked_id_only

logger = logging.getLogger('apps.recommendation')
RC = settings.RECOMMENDATION


# ── Reports ───────────────────────────────────────────────────────────────────

class ProjectReportGenerateView(APIView):
    permission_classes = [IsAuthenticated]
    throttle_classes   = [ReportGenerateThrottle]

    def post(self, request, pk):
        profile = _get_profile(request)
        project = Project.objects.filter(project_id=pk, user=profile).first() if profile else None
        if not project:
            return Response({'detail': 'Not found'}, status=status.HTTP_404_NOT_FOUND)

        # BACK-REPORT-CACHE-1: short-circuit on stored report unless regenerate
        # is explicitly requested. Avoids Gemini call + DB write + cache eviction
        # on every revisit-triggered POST (was causing silent 429s + nondeterministic
        # report rewrites — reports.py regenerated+overwrote on every call).
        if project.final_report and not request.data.get('regenerate'):
            # 2026-09-28: no recompute on the cached short-circuit path -- a
            # legacy-format stored axis_scores is returned as-is (original
            # BACK-REPORT-CACHE-1 behaviour). It only upgrades to the new
            # embedding-projection shape via the generate/regenerate path below.
            return Response({'final_report': project.final_report, 'axis_scores': project.axis_scores})

        liked_id_strings = _liked_id_only(project.liked_ids)
        if not liked_id_strings:
            return Response({'detail': 'No liked buildings yet'}, status=status.HTTP_400_BAD_REQUEST)

        # BACK-LLM-5: ground the report in BOTH sides of the swipe history +
        # the requesting profile's language preference (fallback 'ko').
        disliked_id_strings = list(project.disliked_ids or [])
        language = getattr(profile, 'language', 'ko') or 'ko'

        try:
            report = services.generate_persona_report(liked_id_strings, disliked_id_strings, language)
        except (ValueError, RuntimeError) as e:
            return Response(
                {'detail': str(e), 'error_type': type(e).__name__},
                status=status.HTTP_502_BAD_GATEWAY,
            )

        if not report:
            return Response(
                {'detail': 'No building data found for report generation'},
                status=status.HTTP_404_NOT_FOUND,
            )

        axis_scores = compute_axis_scores(liked_id_strings)

        project.final_report = report
        project.axis_scores = axis_scores
        project.save(update_fields=['final_report', 'axis_scores'])
        evict_projects_list(profile.id)
        evict_project_detail(str(pk))
        logger.info('Persona report generated for project %s', pk)
        return Response({'final_report': report, 'axis_scores': axis_scores})


class ProjectReportImageFetchView(APIView):
    """GET /api/v1/projects/<pk>/report-image/ — serve a board's persona image.

    Split from the generating POST on purpose: board cards need to READ the
    image, and Project.report_image is base64 TEXT (~200KB). Inlining it in the
    profile's board list (page_size up to 50) would make one response megabytes
    wide, so the list ships a pointer and each card fetches lazily. Mirrors the
    /people feed's report-image endpoint.

    Visibility mirrors the board LIST exactly (accounts/views/profile.py
    `_build_boards_field`): the owner sees their own boards, everyone else only
    `visibility='public'` ones. Without this the pointer would become a way to
    read private boards' images.

    404 when absent — callers treat that as "no image" and fall back, they do
    not retry.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        project = (
            Project.objects
            .filter(project_id=pk)
            .values('report_image', 'report_image_mime', 'visibility', 'user_id')
            .first()
        )
        if not project:
            return Response({'detail': 'Not found'}, status=status.HTTP_404_NOT_FOUND)

        profile = _get_profile(request)
        is_owner = profile is not None and profile.pk == project['user_id']
        if not is_owner and project['visibility'] != 'public':
            # Same shape as "missing" so the endpoint never confirms that a
            # private board exists.
            return Response({'detail': 'Not found'}, status=status.HTTP_404_NOT_FOUND)

        if not project['report_image']:
            return Response({'detail': 'Not found'}, status=status.HTTP_404_NOT_FOUND)

        return Response({
            'image_data': project['report_image'],
            'mime_type': project['report_image_mime'] or 'image/png',
        })


# FULL-REPORT-IMG-1: per-project in-flight lock for paid image generation.
# The lock VALUE is a per-request uuid4 token; release is compare-then-delete so
# a leader whose TTL expired never deletes a LATER leader's lock. (The
# get-then-delete is not atomic -- the tiny window between the two calls is an
# accepted race; Django's cache API has no compare-and-delete.)
# TTL is a crash fallback AND must exceed the worst-case leader time: 45 s
# per-call timeout x 1 retry x 1 model fallback = ~180 s.
IMAGE_LOCK_TTL = 180
# A duplicate request waits (polling the lock) at most this long before
# answering 202 'in_progress' (client re-POSTs after retry_after) so it holds a
# request thread for less time.
IMAGE_WAIT_BUDGET = 25
IMAGE_WAIT_POLL = 1.0


def _image_lock_key(pk):
    return f'report_image_lock:{pk}'


class ProjectReportImageView(APIView):
    """POST /api/v1/projects/<pk>/report/generate-image/

    FULL-REPORT-IMG-1: works BEFORE the report exists, so the frontend fires it
    in parallel with report/generate/ the moment swipes end.

    Prompt source:
      - project.final_report present -> report-based prompt (unchanged).
      - absent -> deterministic Python taste facts of the project's liked /
        disliked buildings (services.build_image_report_from_facts) -- no LLM.

    Responses:
      200 {image_data, mime_type, prompt}  stored image (prompt null) or fresh.
      202 {status: 'in_progress', retry_after}  another request is generating
          this project's image and did not finish within IMAGE_WAIT_BUDGET s;
          NO second paid generation was started -- re-POST after retry_after.
      400 no liked buildings (and no report) | 404 not found / no building data
      500 generation failed (also returned to a waiter whose leader failed).

    Dedupe: cache.add lock per project. A concurrent request waits for the
    leader and returns the leader's stored image. Saves use update_fields, so
    they never overwrite final_report/axis_scores written concurrently by
    ProjectReportGenerateView (which likewise only writes its own columns).
    """
    permission_classes = [IsAuthenticated]
    throttle_classes   = [ReportImageThrottle]

    @staticmethod
    def _stored_response(pk):
        row = Project.objects.filter(project_id=pk).values('report_image', 'report_image_mime').first()
        if row and row['report_image']:
            return Response({
                'image_data': row['report_image'],
                'mime_type': row['report_image_mime'],
                'prompt': None,
            })
        return None

    def _wait_for_leader(self, pk, lock_key):
        deadline = time.monotonic() + IMAGE_WAIT_BUDGET
        while cache.get(lock_key) is not None:
            if time.monotonic() >= deadline:
                return Response(
                    {'status': 'in_progress', 'detail': 'Image generation in progress.',
                     'retry_after': 5},
                    status=status.HTTP_202_ACCEPTED,
                    headers={'Retry-After': '5'},
                )
            time.sleep(IMAGE_WAIT_POLL)
        stored = self._stored_response(pk)
        if stored is not None:
            return stored
        return Response({'detail': 'Image generation failed.'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    def post(self, request, pk):
        profile = _get_profile(request)
        project = Project.objects.filter(project_id=pk, user=profile).first() if profile else None
        if not project:
            return Response({'detail': 'Not found'}, status=status.HTTP_404_NOT_FOUND)

        liked_id_strings = _liked_id_only(project.liked_ids)
        if not project.final_report and not liked_id_strings:
            return Response({'detail': 'No liked buildings yet'}, status=status.HTTP_400_BAD_REQUEST)

        # BACK-REPORT-CACHE-1: short-circuit on stored image unless regenerate
        # is explicitly requested (same rationale as ProjectReportGenerateView).
        regenerate = bool(request.data.get('regenerate'))
        if project.report_image and not regenerate:
            return Response({
                'image_data': project.report_image,
                'mime_type': project.report_image_mime,
                'prompt': None,
            })

        lock_key = _image_lock_key(pk)
        lock_token = uuid.uuid4().hex
        if not cache.add(lock_key, lock_token, IMAGE_LOCK_TTL):
            return self._wait_for_leader(pk, lock_key)

        try:
            if not regenerate:
                # A leader may have stored the image between our first read
                # and acquiring the lock.
                stored = self._stored_response(pk)
                if stored is not None:
                    return stored

            if project.final_report:
                image_source = project.final_report
            else:
                image_source = services.build_image_report_from_facts(
                    liked_id_strings, list(project.disliked_ids or []),
                )
                if not image_source:
                    return Response(
                        {'detail': 'No building data found for image generation'},
                        status=status.HTTP_404_NOT_FOUND,
                    )

            result = services.generate_persona_image(image_source)
            if not result:
                return Response(
                    {'detail': 'Image generation failed.'},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR,
                )

            # update_fields: write ONLY the image columns so a report saved
            # concurrently (final_report/axis_scores) is never clobbered by
            # this request's stale in-memory Project.
            project.report_image = result['image_data']
            project.report_image_mime = result['mime_type']
            project.save(update_fields=['report_image', 'report_image_mime'])
            evict_projects_list(profile.id)
            evict_project_detail(str(pk))
            evict_user_profile_detail(profile.user.id)
            logger.info(
                'Persona image generated for project %s (%s)',
                pk, 'report' if project.final_report else 'facts',
            )
            return Response({
                'image_data': result['image_data'],
                'mime_type': result['mime_type'],
                'prompt': result['prompt'],
            })
        finally:
            # Release only our own lock (see IMAGE_LOCK_TTL note on the race).
            if cache.get(lock_key) == lock_token:
                cache.delete(lock_key)
