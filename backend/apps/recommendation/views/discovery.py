import logging

from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from ..models import Project
from .. import engine
from ._shared import _get_profile, _liked_id_only

logger = logging.getLogger('apps.recommendation')


class DiscoveryFeedView(APIView):
    """
    GET /api/v1/discovery/?cursor=&limit=

    Returns a taste-ranked or cold-start-random page of buildings for the
    Discovery tab. Cursor is integer offset; stable within a single tab visit
    but may reshuffle if the user likes new buildings via the Swipe tab in
    parallel (documented limitation).
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        profile = _get_profile(request)
        if profile is None:
            return Response({'detail': 'unauthenticated'}, status=status.HTTP_401_UNAUTHORIZED)

        # --- Parse and validate request params ---
        try:
            cursor = int(request.query_params.get('cursor', 0))
            if cursor < 0:
                raise ValueError
        except (TypeError, ValueError):
            return Response({'detail': 'cursor must be an integer >= 0'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            limit = int(request.query_params.get('limit', 12))
            if not 1 <= limit <= 30:
                raise ValueError
        except (TypeError, ValueError):
            return Response({'detail': 'limit must be an integer in [1, 30]'}, status=status.HTTP_400_BAD_REQUEST)

        # --- Build exclusion set from profile's signed projects ---
        projects = Project.objects.filter(user=profile).values('liked_ids', 'disliked_ids', 'saved_ids')
        liked_ids = []
        disliked_ids = []
        saved_ids = []
        for project in projects:
            liked_ids.extend(_liked_id_only(project.get('liked_ids')))
            disliked_ids.extend(project.get('disliked_ids') or [])
            saved_ids.extend(
                e.get('id')
                for e in (project.get('saved_ids') or [])
                if isinstance(e, dict) and e.get('id')
            )

        exclude_ids = []
        seen = set()
        for bid in liked_ids + disliked_ids + saved_ids:
            if isinstance(bid, str) and bid not in seen:
                exclude_ids.append(bid)
                seen.add(bid)
        exclude_set = set(exclude_ids)

        # --- Compute taste vector and serve cold or warm path ---
        v_taste = engine.compute_user_taste_vector(profile)
        if v_taste is None:
            cards = engine.get_diverse_random(n=limit, filters=None)
            cards = [card for card in cards if card.get('building_id') not in exclude_set]
            return Response({
                'cards': cards,
                'next_cursor': None,
                'has_more': False,
                'taste_state': 'cold',
            })

        cards = engine.taste_ranked_page(v_taste, exclude_ids, limit=limit, offset=cursor)
        has_more = len(cards) == limit
        return Response({
            'cards': cards,
            'next_cursor': cursor + len(cards) if has_more else None,
            'has_more': has_more,
            'taste_state': 'warm',
        })


class BoardSurpriseView(APIView):
    """
    GET /api/v1/recommendations/board-surprise/

    Returns up to 10 curated or cold-start-random buildings for the Surprise
    Board modal. Read-only: no persistence side-effects. The frontend modal
    handles project creation and bulk-bookmark calls separately.

    Cold start (v_taste is None):
        cards = diverse random 10 minus excluded IDs
        title = "Discover something new"
        rationale = "A diverse starter pack"

    Warm (v_taste exists):
        cards = taste_ranked_page at offset 0, limit 10
        title = "Curated for you"
        rationale = "Based on your taste so far"
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        profile = _get_profile(request)
        if profile is None:
            return Response({'detail': 'unauthenticated'}, status=status.HTTP_401_UNAUTHORIZED)

        # --- Build exclusion set (same union as DiscoveryFeedView) ---
        projects = Project.objects.filter(user=profile).values('liked_ids', 'disliked_ids', 'saved_ids')
        liked_ids = []
        disliked_ids = []
        saved_ids = []
        for project in projects:
            liked_ids.extend(_liked_id_only(project.get('liked_ids')))
            disliked_ids.extend(project.get('disliked_ids') or [])
            saved_ids.extend(
                e.get('id')
                for e in (project.get('saved_ids') or [])
                if isinstance(e, dict) and e.get('id')
            )

        exclude_ids = []
        seen = set()
        for bid in liked_ids + disliked_ids + saved_ids:
            if isinstance(bid, str) and bid not in seen:
                exclude_ids.append(bid)
                seen.add(bid)
        exclude_set = set(exclude_ids)

        # --- Compute taste vector and serve cold or warm path ---
        v_taste = engine.compute_user_taste_vector(profile)
        if v_taste is None:
            cards = engine.get_diverse_random(n=10, filters=None)
            cards = [card for card in cards if card.get('building_id') not in exclude_set]
            return Response({
                'cards': cards,
                'title': 'Discover something new',
                'rationale': 'A diverse starter pack',
            })

        cards = engine.taste_ranked_page(v_taste, exclude_ids, limit=10, offset=0)
        return Response({
            'cards': cards,
            'title': 'Curated for you',
            'rationale': 'Based on your taste so far',
        })
