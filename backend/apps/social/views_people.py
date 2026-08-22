"""apps.social.views_people — People Discovery feed.

GET /api/v1/people/

Returns a ranked + shuffled list of users whose personality vectors are
closest (or most opposite) to the requester's own vector.

Query params:
  filter — 'inspired' (closest), 'opposite' (furthest), or a 4-letter
            type code (e.g. 'CLON') to see that specific type.
  axis   — 0..4 integer; when supplied, sort by distance on that axis only
            instead of the full 5-D Euclidean distance.

Candidate pool construction (ORDER MATTERS — do not reorder):
  1. Filter:  discovery_opt_in=True, exclude requester, exclude is_guest=True.
  2. Work filter: further restrict to users who have at least one
                  is_publishable=True Work (owner_id set intersection).
  3. Safety cap: [:500] applied BEFORE any Python-side calculation.
  4. Distance:   Euclidean distance computed in Python for each candidate.
  5. Sort:       ascending distance ('inspired') or descending ('opposite').
  6. Top 15:     slice, then random.shuffle() for feed freshness.

403 is returned when the requester has no PersonalityProfile yet.
"""
import math
import random
import logging

from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.models import PersonalityProfile, UserProfile
from apps.works.models import Work

logger = logging.getLogger('apps.social')

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_FEED_SHUFFLE_TOP_N = 15
_CANDIDATE_CAP = 500

_AXIS_LABELS = ['작업 방식', '역할 성향', '협업 방식', '접근 태도', '결정 속도']

# Valid explicit type codes (16 types from 4 binary axes).
_VALID_TYPE_CODES = frozenset({
    'CLON', 'CLOT', 'CLDN', 'CLDT',
    'CSON', 'CSOT', 'CSDN', 'CSDT',
    'RLON', 'RLOT', 'RLDN', 'RLDT',
    'RSON', 'RSOT', 'RSDN', 'RSDT',
})

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _get_vector(p):
    """Return the 5-D personality vector for a PersonalityProfile instance."""
    return [p.axis_1, p.axis_2, p.axis_3, p.axis_4, p.axis_5]


def _euclidean(v1, v2):
    """5-D Euclidean distance between two vectors."""
    return math.sqrt(sum((a - b) ** 2 for a, b in zip(v1, v2)))


def _axis_distance(v1, v2, axis_index):
    """Absolute distance on a single axis (0-based index)."""
    return abs(v1[axis_index] - v2[axis_index])


def _reason_copy(my_vec, their_vec):
    """Generate a one-line reason string comparing two vectors.

    If the maximum axis distance >= 1.5, reports the most-divergent axis.
    Otherwise reports the most-similar axis.
    """
    diffs = [abs(m - t) for m, t in zip(my_vec, their_vec)]
    max_i = diffs.index(max(diffs))
    min_i = diffs.index(min(diffs))
    if max(diffs) >= 1.5:
        return f'{_AXIS_LABELS[max_i]} 축에서 정반대예요'
    return f'{_AXIS_LABELS[min_i]} 측면에서 가장 닮았어요'


def _highlight_axis(my_vec, their_vec):
    """Return the 0-based index of the most divergent axis."""
    diffs = [abs(m - t) for m, t in zip(my_vec, their_vec)]
    return diffs.index(max(diffs))


# ---------------------------------------------------------------------------
# View
# ---------------------------------------------------------------------------

class PeopleDiscoveryView(APIView):
    """GET /api/v1/people/ — personality-based user discovery feed."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        # -- Guard: requester must have completed assessment ------------------
        try:
            requester_profile = request.user.profile
        except UserProfile.DoesNotExist:
            return Response(
                {'detail': 'UserProfile not found.'},
                status=status.HTTP_404_NOT_FOUND,
            )

        try:
            my_personality = requester_profile.personality
        except PersonalityProfile.DoesNotExist:
            return Response(
                {'detail': 'assessment_required'},
                status=status.HTTP_403_FORBIDDEN,
            )

        my_vec = _get_vector(my_personality)

        # -- Parse query params -----------------------------------------------
        filter_param = request.query_params.get('filter', 'inspired')
        axis_param = request.query_params.get('axis', None)

        # Validate axis param.
        axis_index = None
        if axis_param is not None:
            try:
                axis_index = int(axis_param)
                if axis_index < 0 or axis_index > 4:
                    return Response(
                        {'detail': 'axis must be 0-4.'},
                        status=status.HTTP_400_BAD_REQUEST,
                    )
            except (ValueError, TypeError):
                return Response(
                    {'detail': 'axis must be an integer 0-4.'},
                    status=status.HTTP_400_BAD_REQUEST,
                )

        # Validate filter param.
        type_code_filter = None
        if filter_param not in ('inspired', 'opposite'):
            upper_filter = filter_param.upper()
            if upper_filter not in _VALID_TYPE_CODES:
                return Response(
                    {'detail': (
                        'filter must be "inspired", "opposite", '
                        'or a valid 4-letter type code.'
                    )},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            type_code_filter = upper_filter

        # -- Step 1: candidate pool — opt-in, non-self, non-guest -------------
        base_qs = (
            PersonalityProfile.objects
            .filter(discovery_opt_in=True)
            .exclude(user=requester_profile)
            .exclude(user__is_guest=True)
            .select_related('user')
        )

        # Optional type_code filter.
        if type_code_filter is not None:
            base_qs = base_qs.filter(type_code=type_code_filter)

        # -- Step 2: restrict to users with at least one publishable Work -----
        publishable_owner_ids = set(
            Work.objects
            .filter(is_publishable=True)
            .values_list('owner_id', flat=True)
            .distinct()
        )
        base_qs = base_qs.filter(user_id__in=publishable_owner_ids)

        # -- Step 3: safety cap BEFORE distance calculation -------------------
        candidates = list(base_qs[:_CANDIDATE_CAP])

        # -- Step 4 & 5: distance calculation + sort --------------------------
        def _dist(p):
            their_vec = _get_vector(p)
            if axis_index is not None:
                return _axis_distance(my_vec, their_vec, axis_index)
            return _euclidean(my_vec, their_vec)

        candidates.sort(key=_dist, reverse=(filter_param == 'opposite'))

        # -- Step 6: top N then shuffle ---------------------------------------
        top = candidates[:_FEED_SHUFFLE_TOP_N]
        random.shuffle(top)

        # -- Build response items ---------------------------------------------
        results = []
        for p in top:
            their_vec = _get_vector(p)
            dist = _euclidean(my_vec, their_vec)
            h_axis = _highlight_axis(my_vec, their_vec)
            user_profile = p.user
            results.append({
                'user_id': user_profile.user_id,
                'display_name': user_profile.display_name,
                'handle': user_profile.handle,
                'avatar_url': user_profile.avatar_url,
                'type_code': p.type_code,
                'vector': their_vec,
                'highlight_axis': h_axis,
                'reason': _reason_copy(my_vec, their_vec),
                'distance': round(dist, 4),
            })

        return Response({
            'results': results,
            'my_vector': my_vec,
        })
