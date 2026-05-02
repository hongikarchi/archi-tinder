import logging

from django.conf import settings
from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from ..models import Project
from ..serializers import ProjectSerializer, ProjectSelfUpdateSerializer
from ._shared import _get_profile

logger = logging.getLogger('apps.recommendation')
RC = settings.RECOMMENDATION


# ── Projects ──────────────────────────────────────────────────────────────────

class ProjectListCreateView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        profile = _get_profile(request)
        if not profile:
            return Response({'results': [], 'total': 0, 'has_more': False})
        try:
            page      = max(1, int(request.query_params.get('page', 1)))
            page_size = min(max(1, int(request.query_params.get('page_size', 50))), 50)
        except (ValueError, TypeError):
            page, page_size = 1, 50
        qs     = Project.objects.filter(user=profile).order_by('-created_at')
        total  = qs.count()
        start  = (page - 1) * page_size
        chunk  = qs[start:start + page_size]
        return Response({
            'results':  ProjectSerializer(chunk, many=True).data,
            'total':    total,
            'page':     page,
            'has_more': (page * page_size) < total,
        })

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
    """GET/PATCH/DELETE /api/v1/projects/{project_id}/ — BOARD1 Phase 13.

    GET:   AllowAny — returns 200 for own or public; 403 for private non-owner.
    PATCH: owner-only — name + visibility only (ProjectSelfUpdateSerializer).
    DELETE: owner-only — cascade rules TBD (Phase 15); plain delete for now.
    """
    permission_classes = [AllowAny]

    def get(self, request, pk):
        project = get_object_or_404(Project.objects.select_related('user__user'), project_id=pk)
        profile = _get_profile(request)
        is_owner = profile and project.user_id == profile.pk
        if not is_owner and project.visibility != 'public':
            return Response({'detail': 'Forbidden'}, status=status.HTTP_403_FORBIDDEN)
        data = ProjectSerializer(project).data
        if request.user.is_authenticated and profile:
            from apps.social.models import Reaction
            data['is_reacted'] = Reaction.objects.filter(user=profile, project=project).exists()
        else:
            data['is_reacted'] = False
        return Response(data)

    def patch(self, request, pk):
        profile = _get_profile(request)
        if not profile:
            return Response({'detail': 'Authentication required'}, status=status.HTTP_401_UNAUTHORIZED)
        project = get_object_or_404(Project, project_id=pk)
        if project.user_id != profile.pk:
            return Response({'detail': 'Forbidden'}, status=status.HTTP_403_FORBIDDEN)
        serializer = ProjectSelfUpdateSerializer(project, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        project.refresh_from_db()  # updated_at is auto_now=True (DB-set); refresh to avoid stale in-memory value
        return Response(ProjectSerializer(project).data)

    def delete(self, request, pk):
        profile = _get_profile(request)
        if not profile:
            return Response({'detail': 'Authentication required'}, status=status.HTTP_401_UNAUTHORIZED)
        project = get_object_or_404(Project, project_id=pk)
        if project.user_id != profile.pk:
            return Response({'detail': 'Forbidden'}, status=status.HTTP_403_FORBIDDEN)
        project.delete()
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
        qs = Project.objects.filter(user=target_profile).select_related('user__user').order_by('-created_at')
        if not is_owner:
            qs = qs.filter(visibility='public')
        total = qs.count()
        start = (page - 1) * page_size
        chunk = list(qs[start:start + page_size])
        return Response({
            'results':  ProjectSerializer(chunk, many=True).data,
            'total':    total,
            'page':     page,
            'has_more': (page * page_size) < total,
        })
