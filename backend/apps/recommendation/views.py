import logging
from django.conf import settings
from django.db import transaction
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Project, AnalysisSession, SwipeEvent
from .serializers import ProjectSerializer
from . import engine, services

logger = logging.getLogger('apps.recommendation')
RC = settings.RECOMMENDATION


def _get_profile(request):
    return getattr(request.user, 'profile', None)


def _progress(session):
    like_count    = session.swipes.filter(action='like').count()
    dislike_count = session.swipes.filter(action='dislike').count()
    return {
        'current_round': session.current_round,
        'total_rounds':  session.total_rounds,
        'like_count':    like_count,
        'dislike_count': dislike_count,
    }


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


# ── Analysis Sessions ─────────────────────────────────────────────────────────

class SessionCreateView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        profile = _get_profile(request)
        if not profile:
            return Response({'detail': 'Profile not found'}, status=status.HTTP_404_NOT_FOUND)

        project_id = request.data.get('project_id')
        filters    = request.data.get('filters') or {}

        # Resolve project (project_id may be a local ID like 'proj_xxx' — ignore gracefully)
        project = None
        if project_id:
            try:
                project = Project.objects.filter(project_id=project_id, user=profile).first()
            except Exception:
                project = None
        if not project:
            project = Project.objects.create(user=profile, name='Untitled', filters=filters)

        # Select initial diverse batch
        initial_cards = engine.get_diverse_random(n=RC['initial_explore_rounds'], filters=filters or project.filters or None)
        if not initial_cards:
            return Response({'detail': 'No buildings found for given filters'}, status=status.HTTP_404_NOT_FOUND)

        initial_ids  = [c['building_id'] for c in initial_cards]
        first_card   = initial_cards[0]

        session = AnalysisSession.objects.create(
            user              = profile,
            project           = project,
            total_rounds      = RC['total_rounds'],
            current_round     = 0,
            preference_vector = [],
            exposed_ids       = [first_card['building_id']],
            initial_batch     = initial_ids,
        )

        logger.info('Session created: %s', session.session_id)
        return Response({
            'session_id':     str(session.session_id),
            'project_id':     str(project.project_id),
            'session_status': session.status,
            'total_rounds':   session.total_rounds,
            'next_image':     first_card,
            'progress':       _progress(session),
        }, status=status.HTTP_201_CREATED)


class SwipeView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, session_id):
        profile = _get_profile(request)
        if not profile:
            return Response({'detail': 'Profile not found'}, status=status.HTTP_404_NOT_FOUND)

        session = AnalysisSession.objects.filter(session_id=session_id, user=profile).first()
        if not session:
            return Response({'detail': 'Session not found'}, status=status.HTTP_404_NOT_FOUND)
        if session.status == 'completed':
            return Response({'detail': 'Session already completed'}, status=status.HTTP_400_BAD_REQUEST)

        building_id     = request.data.get('building_id')
        action          = request.data.get('action')
        idempotency_key = request.data.get('idempotency_key', '')

        if action not in ('like', 'dislike'):
            return Response({'detail': 'action must be like or dislike'}, status=status.HTTP_400_BAD_REQUEST)

        # Idempotency check — if already processed, return accepted so frontend treats it as success
        if SwipeEvent.objects.filter(idempotency_key=idempotency_key).exists():
            logger.info('Duplicate swipe ignored: %s', idempotency_key)
            return Response({'accepted': True, 'detail': 'duplicate'}, status=status.HTTP_200_OK)

        with transaction.atomic():
            # Get embedding and update preference vector
            embedding = engine.get_building_embedding(building_id)
            if embedding:
                session.preference_vector = engine.update_preference_vector(
                    session.preference_vector, embedding, action
                )

            # Record swipe
            SwipeEvent.objects.create(
                session         = session,
                building_id     = building_id,
                action          = action,
                idempotency_key = idempotency_key,
            )

            # Update project liked/disliked lists
            project = session.project
            if action == 'like':
                if building_id not in project.liked_ids:
                    project.liked_ids = project.liked_ids + [building_id]
            else:
                if building_id not in project.disliked_ids:
                    project.disliked_ids = project.disliked_ids + [building_id]
            project.save(update_fields=['liked_ids', 'disliked_ids'])

            session.current_round += 1

            # Check completion
            if session.current_round >= session.total_rounds:
                session.status = 'completed'
                session.save(update_fields=['preference_vector', 'current_round', 'status'])
                return Response({
                    'accepted':             True,
                    'session_status':       'completed',
                    'progress':             _progress(session),
                    'next_image':           None,
                    'is_analysis_completed': True,
                })

            # Select next image
            filters   = project.filters or None
            next_card = engine.select_next_image(
                session.preference_vector,
                session.exposed_ids,
                session.current_round,
                filters,
            )

            if next_card:
                session.exposed_ids = session.exposed_ids + [next_card['building_id']]

            session.save(update_fields=['preference_vector', 'current_round', 'exposed_ids'])

        return Response({
            'accepted':              True,
            'session_status':        session.status,
            'progress':              _progress(session),
            'next_image':            next_card,
            'is_analysis_completed': False,
        })


class SessionResultView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, session_id):
        profile = _get_profile(request)
        session = AnalysisSession.objects.filter(session_id=session_id).first()
        if not session:
            return Response({'detail': 'Session not found'}, status=status.HTTP_404_NOT_FOUND)
        if session.user != profile:
            return Response({'detail': 'Forbidden'}, status=status.HTTP_403_FORBIDDEN)

        # Liked buildings
        liked_ids   = list(session.swipes.filter(action='like').values_list('building_id', flat=True))
        liked_cards = [engine.get_building_card(bid) for bid in liked_ids]
        liked_cards = [c for c in liked_cards if c]

        # Predicted (top-k by similarity, excluding already exposed)
        predicted_cards = engine.get_top_k_results(
            session.preference_vector,
            session.exposed_ids,
            k=RC['top_k_results'],
        )

        return Response({
            'session_id':          str(session.session_id),
            'session_status':      session.status,
            'liked_images':        liked_cards,
            'predicted_images':    predicted_cards,
            'predicted_like_count': len(predicted_cards),
            'analysis_report':     session.project.analysis_report,
            'generated_at':        session.created_at.isoformat(),
        })


# ── Images ────────────────────────────────────────────────────────────────────

class DiverseRandomView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        cards = engine.get_diverse_random(n=10)
        return Response(cards)


class BuildingBatchView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        ids = request.data.get('building_ids', [])
        if not ids:
            return Response([])
        cards = engine.get_buildings_by_ids(ids)
        return Response(cards)


# ── Reports ───────────────────────────────────────────────────────────────────

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
        profile = _get_profile(request)
        project = Project.objects.filter(project_id=pk, user=profile).first() if profile else None
        if not project:
            return Response({'detail': 'Not found'}, status=status.HTTP_404_NOT_FOUND)

        if not project.liked_ids:
            return Response({'detail': 'No liked buildings yet'}, status=status.HTTP_400_BAD_REQUEST)

        report = services.generate_persona_report(project.liked_ids)
        if not report:
            return Response({'detail': 'Report generation failed'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        project.final_report = report
        project.save(update_fields=['final_report'])
        logger.info('Persona report generated for project %s', pk)
        return Response({'final_report': report})


# ── LLM Query Parsing ─────────────────────────────────────────────────────────

class ParseQueryView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        query = request.data.get('query', '').strip()
        if not query:
            return Response({'detail': 'query is required'}, status=status.HTTP_400_BAD_REQUEST)

        parsed  = services.parse_query(query)
        filters = {k: v for k, v in parsed['filters'].items() if v is not None}
        results = engine.search_by_filters(filters, limit=20) if filters else []

        return Response({
            'reply':              parsed['reply'],
            'structured_filters': parsed['filters'],
            'suggestions':        [],
            'results':            results,
        })
