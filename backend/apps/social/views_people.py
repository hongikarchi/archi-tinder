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
  1. Filter:  discovery_opt_in=True. Nothing else — FRONT-PEOPLE-FEED-1
              (2026-09-03) removed the self-exclusion, the guest exclusion and
              the publishable-Work requirement. discovery_opt_in survives
              because it is the user's own hide-me switch, not a completeness
              gate.
  2. Report-image filter: restrict to users who have at least one
              visibility='public' Project carrying a report_image. The feed
              card's front face IS that image, so this is the one hard
              requirement; visibility='public' keeps private taste reports
              from leaking.
  3. Safety cap: [:500] applied BEFORE any Python-side calculation.
  4. Distance:   Euclidean distance computed in Python for each candidate.
  5. Sort:       ascending distance ('inspired') or descending ('opposite').
  6. Top 15:     slice, then random.shuffle() for feed freshness.

403 is returned when the requester has no PersonalityProfile yet.

GET /api/v1/people/<user_id>/report-image/

Serves one candidate's taste-report image. Split off the feed response on
purpose: Project.report_image is base64 TEXT in the DB, and inlining ~15 of
them would balloon a single feed payload into megabytes. The feed returns a
`report_image_url` pointer instead and each card fetches lazily.

Only `visibility='public'` projects are eligible — private taste reports never
leave their owner.
"""
import math
import random
import logging

from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.models import PersonalityProfile, UserProfile
from apps.recommendation.models import Project

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

        # -- Step 1: candidate pool — opt-in only -----------------------------
        # FRONT-PEOPLE-FEED-1 (2026-09-03, product decision): a generated
        # persona report image is now the ONLY gate that matters. The
        # self-exclusion and the guest exclusion are both gone — if someone has
        # an image, they appear, themselves included.
        #
        # discovery_opt_in is DELIBERATELY still honoured: it is the user's own
        # "hide me from discovery" switch, not a completeness requirement, so
        # overriding it would publish someone against their stated choice. It
        # currently filters nobody out (0 users have it False), so keeping it
        # costs no candidates today while preserving the opt-out.
        base_qs = (
            PersonalityProfile.objects
            .filter(discovery_opt_in=True)
            .select_related('user')
        )

        # Optional type_code filter.
        if type_code_filter is not None:
            base_qs = base_qs.filter(type_code=type_code_filter)

        # -- Step 2: restrict to users with a public taste-report image -------
        # The card's front face is this image, so it is the one hard
        # requirement. The former "must own a publishable Work" gate was
        # dropped with the same decision — a portfolio upload has nothing to do
        # with whether a taste profile is worth discovering.
        #
        # visibility='public' stays: report_image lives on Project alongside
        # private taste reports, and serving those would leak them.
        report_image_owner_ids = set(
            Project.objects
            .filter(visibility='public')
            .exclude(report_image__isnull=True)
            .exclude(report_image='')
            .values_list('user_id', flat=True)
            .distinct()
        )
        base_qs = base_qs.filter(user_id__in=report_image_owner_ids)

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
            # The requester now appears in their own feed (FRONT-PEOPLE-FEED-1).
            # Their distance to themselves is 0, so a similarity reason would
            # read "작업 방식 측면에서 가장 닮았어요" about the viewer — label the
            # card instead, and let the client mark it via is_me.
            is_me = p.user_id == requester_profile.id
            results.append({
                'user_id': user_profile.user_id,
                'display_name': user_profile.display_name,
                'handle': user_profile.handle,
                'avatar_url': user_profile.avatar_url,
                'type_code': p.type_code,
                'vector': their_vec,
                'highlight_axis': None if is_me else h_axis,
                'reason': '나의 카드예요' if is_me else _reason_copy(my_vec, their_vec),
                'is_me': is_me,
                'distance': round(dist, 4),
                # Pointer, not payload — see module docstring.
                'report_image_url': f'/api/v1/people/{user_profile.user_id}/report-image/',
            })

        return Response({
            'results': results,
            'my_vector': my_vec,
        })


class PeopleReportImageView(APIView):
    """GET /api/v1/people/<user_id>/report-image/ — one candidate's report image.

    Returns the most recently updated PUBLIC project's report image for that
    user. 404 when the user has none public — callers treat that as "no image"
    and fall back, they do not retry.

    `user_id` is the auth User id — the same id `/api/v1/users/<user_id>/`
    takes and the feed emits. Project.user points at UserProfile, whose OWN
    `user_id` column is the auth User FK, hence the `user__user_id` traversal.
    Filtering on Project.user_id directly would silently match the wrong
    person (that column holds UserProfile.id).
    """
    permission_classes = [IsAuthenticated]

    def get(self, request, user_id):
        project = (
            Project.objects
            .filter(user__user_id=user_id, visibility='public')
            .exclude(report_image__isnull=True)
            .exclude(report_image='')
            .order_by('-updated_at')
            .values('report_image', 'report_image_mime')
            .first()
        )
        if project is None:
            return Response(
                {'detail': 'No public report image for this user.'},
                status=status.HTTP_404_NOT_FOUND,
            )
        return Response({
            'image_data': project['report_image'],
            'mime_type': project['report_image_mime'] or 'image/png',
        })
