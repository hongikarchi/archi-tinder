import logging
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Project
from .serializers import ProjectSerializer

logger = logging.getLogger('apps.recommendation')


def _get_profile(request):
    return getattr(request.user, 'profile', None)


# ── Projects ──────────────────────────────────────────────────────────────────

class ProjectListCreateView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        profile = _get_profile(request)
        if not profile:
            return Response([], status=status.HTTP_200_OK)
        projects = Project.objects.filter(user=profile).order_by('-created_at')
        return Response(ProjectSerializer(projects, many=True).data)

    def post(self, request):
        profile = _get_profile(request)
        if not profile:
            return Response({'detail': 'Profile not found'}, status=status.HTTP_404_NOT_FOUND)
        serializer = ProjectSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        project = serializer.save(user=profile)
        logger.info('Project created: %s by user %s', project.project_id, profile.pk)
        return Response(ProjectSerializer(project).data, status=status.HTTP_201_CREATED)


class ProjectDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def _get_project(self, request, pk):
        profile = _get_profile(request)
        if not profile:
            return None
        return Project.objects.filter(project_id=pk, user=profile).first()

    def patch(self, request, pk):
        project = self._get_project(request, pk)
        if not project:
            return Response({'detail': 'Not found'}, status=status.HTTP_404_NOT_FOUND)
        serializer = ProjectSerializer(project, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(ProjectSerializer(project).data)

    def delete(self, request, pk):
        project = self._get_project(request, pk)
        if not project:
            return Response({'detail': 'Not found'}, status=status.HTTP_404_NOT_FOUND)
        project.delete()
        logger.info('Project deleted: %s', pk)
        return Response(status=status.HTTP_204_NO_CONTENT)


# ── Stubs for Phase 2 ─────────────────────────────────────────────────────────

class SessionCreateView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        return Response({'detail': 'Not implemented — coming in Phase 2'}, status=status.HTTP_501_NOT_IMPLEMENTED)


class SwipeView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, session_id):
        return Response({'detail': 'Not implemented — coming in Phase 2'}, status=status.HTTP_501_NOT_IMPLEMENTED)


class SessionResultView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, session_id):
        return Response({'detail': 'Not implemented — coming in Phase 2'}, status=status.HTTP_501_NOT_IMPLEMENTED)


class DiverseRandomView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response({'detail': 'Not implemented — coming in Phase 2'}, status=status.HTTP_501_NOT_IMPLEMENTED)


class ParseQueryView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        return Response({'detail': 'Not implemented — coming in Phase 3'}, status=status.HTTP_501_NOT_IMPLEMENTED)


class ProjectReportView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        profile = _get_profile(request)
        project = Project.objects.filter(project_id=pk, user=profile).first() if profile else None
        if not project:
            return Response({'detail': 'Not found'}, status=status.HTTP_404_NOT_FOUND)
        return Response({'analysis_report': project.analysis_report, 'final_report': project.final_report})


class ProjectReportGenerateView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        return Response({'detail': 'Not implemented — coming in Phase 3'}, status=status.HTTP_501_NOT_IMPLEMENTED)
