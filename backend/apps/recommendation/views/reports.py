import logging

from django.conf import settings
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from ..models import Project
from .. import services
from ..caches import evict_projects_list, evict_project_detail
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
            return Response({'final_report': project.final_report, 'axis_scores': project.axis_scores})

        liked_id_strings = _liked_id_only(project.liked_ids)
        if not liked_id_strings:
            return Response({'detail': 'No liked buildings yet'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            report = services.generate_persona_report(liked_id_strings)
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


class ProjectReportImageView(APIView):
    permission_classes = [IsAuthenticated]
    throttle_classes   = [ReportImageThrottle]

    def post(self, request, pk):
        profile = _get_profile(request)
        project = Project.objects.filter(project_id=pk, user=profile).first() if profile else None
        if not project:
            return Response({'detail': 'Not found'}, status=status.HTTP_404_NOT_FOUND)

        if not project.final_report:
            return Response({'detail': 'Generate persona report first'}, status=status.HTTP_400_BAD_REQUEST)

        # BACK-REPORT-CACHE-1: short-circuit on stored image unless regenerate
        # is explicitly requested (same rationale as ProjectReportGenerateView).
        if project.report_image and not request.data.get('regenerate'):
            return Response({
                'image_data': project.report_image,
                'mime_type': project.report_image_mime,
                'prompt': None,
            })

        result = services.generate_persona_image(project.final_report)
        if not result:
            return Response(
                {'detail': 'Image generation failed.'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        project.report_image = result['image_data']
        project.report_image_mime = result['mime_type']
        project.save(update_fields=['report_image', 'report_image_mime'])
        evict_projects_list(profile.id)
        evict_project_detail(str(pk))
        logger.info('Persona image generated for project %s', pk)
        return Response({
            'image_data': result['image_data'],
            'mime_type': result['mime_type'],
            'prompt': result['prompt'],
        })
