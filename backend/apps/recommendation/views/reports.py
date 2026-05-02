import logging

from django.conf import settings
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from ..models import Project
from .. import services
from ._shared import _get_profile, _liked_id_only

logger = logging.getLogger('apps.recommendation')
RC = settings.RECOMMENDATION


# ── Reports ───────────────────────────────────────────────────────────────────

class ProjectReportGenerateView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        profile = _get_profile(request)
        project = Project.objects.filter(project_id=pk, user=profile).first() if profile else None
        if not project:
            return Response({'detail': 'Not found'}, status=status.HTTP_404_NOT_FOUND)

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

        project.final_report = report
        project.save(update_fields=['final_report'])
        logger.info('Persona report generated for project %s', pk)
        return Response({'final_report': report})


class ProjectReportImageView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        profile = _get_profile(request)
        project = Project.objects.filter(project_id=pk, user=profile).first() if profile else None
        if not project:
            return Response({'detail': 'Not found'}, status=status.HTTP_404_NOT_FOUND)

        if not project.final_report:
            return Response({'detail': 'Generate persona report first'}, status=status.HTTP_400_BAD_REQUEST)

        result = services.generate_persona_image(project.final_report)
        if not result:
            return Response({'detail': 'Image generation failed. The Imagen API may not be enabled for your API key.'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        project.report_image = result['image_data']
        project.save(update_fields=['report_image'])
        logger.info('Persona image generated for project %s', pk)
        return Response({
            'image_data': result['image_data'],
            'mime_type': result['mime_type'],
            'prompt': result['prompt'],
        })
