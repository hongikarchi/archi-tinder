import logging
import math

from django.conf import settings
from django.core.exceptions import ValidationError
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.throttling import AnonRateThrottle, UserRateThrottle
from rest_framework.views import APIView

from ..models import AnalysisSession, SessionEvent
from ._shared import _get_profile

logger = logging.getLogger('apps.recommendation')
RC = settings.RECOMMENDATION


# ── Telemetry ─────────────────────────────────────────────────────────────────

class ImageLoadTelemetryThrottle(AnonRateThrottle):
    """Scoped anon throttle for the image-load telemetry endpoint.

    Uses the 'image_load_telemetry' scope defined in REST_FRAMEWORK DEFAULT_THROTTLE_RATES
    (120/min). Applied alongside UserRateThrottle so authenticated users are capped too.
    """
    scope = 'image_load_telemetry'


class ImageLoadTelemetryView(APIView):
    """POST /api/v1/telemetry/image-load/ — frontend image load success/failure beacon.

    Accepts anonymous requests (broken images can happen to unauthenticated users too).
    Records a SessionEvent with event_type='image_load' for observability.
    """
    permission_classes = [AllowAny]
    throttle_classes = [ImageLoadTelemetryThrottle, UserRateThrottle]

    def post(self, request):
        from urllib.parse import urlparse
        data = request.data

        url = data.get('url', '')
        outcome = data.get('outcome', '')
        if outcome not in ('success', 'failure', 'timeout'):
            return Response({'detail': 'invalid outcome'}, status=status.HTTP_400_BAD_REQUEST)
        if not url or len(url) > 2048:
            return Response({'detail': 'invalid url'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            domain = urlparse(url).netloc or 'unknown'
        except Exception:
            domain = 'unknown'

        profile = _get_profile(request) if request.user.is_authenticated else None

        # Fix 3: filter session by user to prevent cross-user session injection.
        # Anonymous users (profile=None) never get session linkage.
        session_id = data.get('session_id')
        session = None
        if session_id and profile:
            try:
                session = AnalysisSession.objects.filter(
                    session_id=session_id, user=profile,
                ).first()
            except (ValueError, ValidationError):
                session = None

        # Fix 4: guard against NaN, Infinity, negative, and implausibly large values.
        # bool is a subclass of int in Python; reject it explicitly to avoid True->1.
        raw_ms = data.get('load_ms')
        if (
            isinstance(raw_ms, (int, float))
            and not isinstance(raw_ms, bool)
            and math.isfinite(raw_ms)
            and 0 <= raw_ms <= 60_000
        ):
            load_ms = int(raw_ms)
        else:
            load_ms = None

        SessionEvent.objects.create(
            user=profile,
            session=session,
            event_type='image_load',
            payload={
                'url': url[:2048],
                'outcome': outcome,
                'domain': domain[:128],
                'building_id': str(data.get('building_id', ''))[:32] or None,
                'context': str(data.get('context', ''))[:32] or None,
                'load_ms': load_ms,
            },
        )
        return Response({'ok': True}, status=status.HTTP_201_CREATED)
