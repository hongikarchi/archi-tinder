import logging
import time
import uuid

from django.conf import settings
from django.core.cache import cache
from django.db import transaction
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from ..models import Project
from .. import services
from ..caches import evict_projects_list, evict_project_detail, evict_user_profile_detail
from ..report_name import followed_board_name
from ..report_signature import liked_signature
from ..services.axis_scores import compute_axis_scores
from ..throttles import ReportGenerateThrottle, ReportImageThrottle
from ._shared import _get_profile, _liked_id_only

logger = logging.getLogger('apps.recommendation')
RC = settings.RECOMMENDATION


# ── Reports ───────────────────────────────────────────────────────────────────

# Per-project report-generation lock (same scheme as the image lock below):
# a duplicate concurrent POST waits for the leader and returns its stored
# report instead of paying for a second LLM call. TTL is a crash fallback.
REPORT_LOCK_TTL = 120
# Must stay below the client fetch timeout (frontend core.js FETCH_TIMEOUT_MS=15s)
# so the follower's 202 actually reaches the browser.
REPORT_WAIT_BUDGET = 10
REPORT_WAIT_POLL = 1.0


def _report_lock_key(pk):
    return f'report_generate_lock:{pk}'


def _generation_id(report):
    """Per-generation id stamped into final_report by _generate (None if legacy)."""
    return report.get('generation_id') if isinstance(report, dict) else None


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

        # Optimistic re-POST guard: a follower that got 202 re-POSTs
        # {regenerate: true, if_generation: <based_on>}. If the stored report was
        # regenerated since (generation_id differs), hand it back -- no 2nd LLM call.
        prev_gen = _generation_id(project.final_report)
        if project.final_report and 'if_generation' in request.data:
            if request.data.get('if_generation') != prev_gen:
                return Response({'final_report': project.final_report, 'axis_scores': project.axis_scores})

        liked_id_strings = _liked_id_only(project.liked_ids)
        if not liked_id_strings:
            return Response({'detail': 'No liked buildings yet'}, status=status.HTTP_400_BAD_REQUEST)

        # Signature of the liked set this request will build from, and of the
        # report stored when the request arrived. The manual "regenerate report"
        # button (useRegeneration) deliberately asks for a fresh LLM report even
        # when the stored one is NOT stale, so equality of the two must NOT
        # short-circuit. Dedupe is instead per-project (cache lock below) plus a
        # post-lock check that only fires when ANOTHER request committed a
        # current-signature report while we were generating.
        current_sig = liked_signature(liked_id_strings)
        fr = project.final_report
        prev_sig = fr.get('source_signature') if isinstance(fr, dict) else None

        lock_key = _report_lock_key(pk)
        lock_token = uuid.uuid4().hex
        if not cache.add(lock_key, lock_token, REPORT_LOCK_TTL):
            return self._wait_for_leader(pk, lock_key, prev_sig, prev_gen)

        try:
            return self._generate(request, pk, profile, project, liked_id_strings, current_sig, prev_sig)
        finally:
            # Release only our own lock (get-then-delete race accepted, see
            # IMAGE_LOCK_TTL note).
            if cache.get(lock_key) == lock_token:
                cache.delete(lock_key)

    @staticmethod
    def _stored_response(pk):
        row = Project.objects.filter(project_id=pk).values('final_report', 'axis_scores').first()
        if row and row['final_report']:
            return Response({'final_report': row['final_report'], 'axis_scores': row['axis_scores']})
        return None

    def _wait_for_leader(self, pk, lock_key, prev_sig, prev_gen=None):
        deadline = time.monotonic() + REPORT_WAIT_BUDGET
        while cache.get(lock_key) is not None:
            if time.monotonic() >= deadline:
                return Response(
                    {'status': 'in_progress', 'detail': 'Report generation in progress.',
                     'retry_after': 5, 'based_on': prev_gen},
                    status=status.HTTP_202_ACCEPTED,
                    headers={'Retry-After': '5'},
                )
            time.sleep(REPORT_WAIT_POLL)
        # Only hand back the stored report if the leader actually committed a
        # new one (generation_id changed -- a same-signature manual regenerate
        # keeps source_signature, so the signature cannot tell); a failed leader
        # leaves the pre-request report in place.
        stored = self._stored_response(pk)
        if stored is not None:
            fr = stored.data['final_report']
            if _generation_id(fr) != prev_gen:
                return stored
        return Response({'detail': 'Report generation failed.'}, status=status.HTTP_502_BAD_GATEWAY)

    def _generate(self, request, pk, profile, project, liked_id_strings, current_sig, prev_sig):
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

        # FULL-REPORT-UI-1: stamp which liked set this report was built from so
        # ProjectSerializer.report_stale can detect later liked-building changes.
        if isinstance(report, dict):
            report['source_signature'] = current_sig
            report['generation_id'] = uuid.uuid4().hex

        # Final writes are mutually exclusive with ProjectDetailView.patch (which
        # also row-locks and may re-save final_report): take the same row lock so
        # a PATCH cannot overwrite this fresh report with its stamped older copy.
        with transaction.atomic():
            locked = (
                Project.objects.select_for_update()
                .filter(pk=project.pk, user=profile)
                .first()
            )
            if locked is None:
                return Response({'detail': 'Not found'}, status=status.HTTP_404_NOT_FOUND)

            # Another request committed a current-signature report while this
            # one was generating: keep it (no overwrite, no rename, no evict).
            stored = locked.final_report
            if (
                isinstance(stored, dict)
                and stored.get('source_signature') == current_sig
                and prev_sig != current_sig
            ):
                return Response({'final_report': stored, 'axis_scores': locked.axis_scores})

            # Board name follows the new persona name unless the user renamed it
            # (current name != OLD report's persona name). Decided from the
            # LOCKED row, so a rename committed during the LLM call wins and the
            # old report is the one actually being replaced.
            new_name = followed_board_name(locked.name, stored, report, language)

            locked.final_report = report
            locked.axis_scores = axis_scores
            update_fields = ['final_report', 'axis_scores']
            if new_name is not None:
                locked.name = new_name
                update_fields.append('name')
            # Write ONLY these columns (never a stale copy of liked_ids /
            # saved_ids loaded before the slow LLM call).
            locked.save(update_fields=update_fields)

        # Evictions run after commit so readers never re-cache pre-commit state.
        evict_projects_list(profile.id)
        evict_project_detail(str(pk))
        # final_report / report_stale appear in the profile boards serializers, so
        # always drop the cached profile card (not only when the name followed).
        evict_user_profile_detail(profile.user.id)
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
