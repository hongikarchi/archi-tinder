import logging
from datetime import timedelta

from django.conf import settings
from django.utils import timezone  # noqa: kept here for mock.patch('apps.recommendation.views.sessions.timezone')
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from ..models import AnalysisSession  # noqa: kept here for mock.patch('apps.recommendation.views.sessions.AnalysisSession.objects.create')
from ..perf_timing import endpoint
from ._shared import _get_profile
from ..services import session_service

logger = logging.getLogger('apps.recommendation')
RC = settings.RECOMMENDATION

# Known filter keys kept here for backwards-compat symbol access (any code
# that does `from apps.recommendation.views.sessions import _VALID_FILTER_KEYS`
# will still find them).
_VALID_FILTER_KEYS = frozenset([
    'program', 'location_country', 'location_city', 'style', 'material',
    'year_min', 'year_max',
])
_VALID_IMAGE_FOCUS = frozenset(['exterior', 'interior', 'drawing', 'aerial', 'detail'])


# ── Analysis Sessions ─────────────────────────────────────────────────────────

class SessionCreateView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        with endpoint('session_create'):
            profile = _get_profile(request)
            if not profile:
                return Response({'detail': 'Profile not found'}, status=status.HTTP_404_NOT_FOUND)

            # Compute recent_cutoff here so that mock.patch(
            #   'apps.recommendation.views.sessions.timezone'
            # ) in test_session_create_dedupe.py remains effective.
            recent_cutoff = timezone.now() - timedelta(seconds=30)
            return session_service.create_session(request, profile, recent_cutoff)


class SessionStateView(APIView):
    """
    Return the current resumable state of an active session without creating
    a new one. Used by the frontend on page refresh to restore the swipe
    session where the user left off.

    Response shape matches SwipeView so the frontend can reuse normalization.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request, session_id):
        profile = _get_profile(request)
        if not profile:
            return Response({'detail': 'Profile not found'}, status=status.HTTP_404_NOT_FOUND)

        session = AnalysisSession.objects.filter(session_id=session_id, user=profile).first()
        if not session:
            return Response({'detail': 'Session not found'}, status=status.HTTP_404_NOT_FOUND)

        return session_service.get_session_state(request, session)


class SessionResultView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, session_id):
        profile = _get_profile(request)
        if not profile:
            return Response({'detail': 'Profile not found'}, status=status.HTTP_404_NOT_FOUND)
        session = AnalysisSession.objects.filter(session_id=session_id, user=profile).first()
        if not session:
            return Response({'detail': 'Session not found'}, status=status.HTTP_404_NOT_FOUND)

        return session_service.get_session_result(session)
