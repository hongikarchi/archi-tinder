"""accounts.views.personality — Personality assessment endpoints.

POST /api/v1/personality/assessment/
  body: {"responses": [int × 20]}  each value -2..+2
  Creates or updates the caller's PersonalityProfile.
  Returns 201 (created) or 200 (updated) with the PersonalityProfileSerializer shape.

GET /api/v1/personality/me/
  Returns the caller's PersonalityProfile (404 if none exists yet).

PATCH /api/v1/personality/me/
  body: {"discovery_opt_in": <bool>}  FULL-PRIVACY-1 discovery opt-out.
  Only discovery_opt_in is writable — axis/type_code fields are ignored.
  404 if no assessment has been completed yet (mirrors GET).
"""
import logging

from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from ..models import PersonalityProfile, UserProfile
from ..serializers import (
    PersonalityAssessmentSerializer,
    PersonalityDiscoveryOptInSerializer,
    PersonalityProfileSerializer,
)

logger = logging.getLogger('apps.accounts')

# ---------------------------------------------------------------------------
# Axis computation helpers
# ---------------------------------------------------------------------------

# Maps axis number (1-based) → 0-based response indices.
_AXIS_QUESTION_MAP = {
    1: [0, 1, 2, 3],      # 개념 ↔ 실무
    2: [4, 5, 6, 7],      # 리더 ↔ 서포터
    3: [8, 9, 10, 11],    # 협업 ↔ 독립
    4: [12, 13, 14, 15],  # 혁신 ↔ 전통
    5: [16, 17, 18, 19],  # 신중 ↔ 즉흥 (보너스)
}

# Positive and negative pole letters for axes 1-4 (axis_5 is bonus only).
_AXIS_LETTERS = [
    ('C', 'R'),  # axis_1: Conceptual / Real
    ('L', 'S'),  # axis_2: Leader / Supporter
    ('O', 'D'),  # axis_3: cOllaborative / inDependent
    ('N', 'T'),  # axis_4: iNnovative / Traditional
]


def _compute_axis_value(responses, indices):
    """Return the normalised axis score in [-1.0, +1.0].

    Mean of the selected Likert responses (-2..+2), divided by 2 to
    normalise into the unit interval.
    """
    mean = sum(responses[i] for i in indices) / len(indices)
    return mean / 2.0


def _compute_type_code(a1, a2, a3, a4):
    """Derive a 4-letter type code from axis scores.

    Rule: value > 0.0 → positive pole; value <= 0.0 → negative pole.
    The 0.0 tie-break goes to the negative direction (second letter).
    """
    return ''.join(
        pos if v > 0.0 else neg
        for v, (pos, neg) in zip([a1, a2, a3, a4], _AXIS_LETTERS)
    )


# ---------------------------------------------------------------------------
# Views
# ---------------------------------------------------------------------------

class PersonalityAssessmentView(APIView):
    """POST /api/v1/personality/assessment/

    Accepts a 20-item Likert response array, computes all 5 axis scores,
    derives the 4-letter type_code, and upserts the PersonalityProfile.
    Evicts the user-profile cache so GET /users/<id>/ reflects the new data.

    Returns 201 on creation, 200 on re-assessment.
    """
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = PersonalityAssessmentSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        responses = serializer.validated_data['responses']

        # Compute axis scores.
        a1 = _compute_axis_value(responses, _AXIS_QUESTION_MAP[1])
        a2 = _compute_axis_value(responses, _AXIS_QUESTION_MAP[2])
        a3 = _compute_axis_value(responses, _AXIS_QUESTION_MAP[3])
        a4 = _compute_axis_value(responses, _AXIS_QUESTION_MAP[4])
        a5 = _compute_axis_value(responses, _AXIS_QUESTION_MAP[5])

        type_code = _compute_type_code(a1, a2, a3, a4)

        try:
            profile = request.user.profile
        except UserProfile.DoesNotExist:
            return Response(
                {'detail': 'UserProfile not found for current user.'},
                status=status.HTTP_404_NOT_FOUND,
            )

        personality, created = PersonalityProfile.objects.update_or_create(
            user=profile,
            defaults={
                'axis_1': a1,
                'axis_2': a2,
                'axis_3': a3,
                'axis_4': a4,
                'axis_5': a5,
                'type_code': type_code,
            },
        )

        # Evict the profile-detail cache so GET /users/<id>/ returns fresh data.
        from apps.recommendation.caches import evict_user_profile_detail
        evict_user_profile_detail(profile.user.id)

        response_status = status.HTTP_201_CREATED if created else status.HTTP_200_OK
        return Response(
            PersonalityProfileSerializer(personality).data,
            status=response_status,
        )


class PersonalityMeView(APIView):
    """GET /api/v1/personality/me/
    Returns the authenticated user's PersonalityProfile.
    404 if no assessment has been completed yet.

    PATCH /api/v1/personality/me/
    FULL-PRIVACY-1: owner-only discovery_opt_in toggle. Body must contain
    ONLY {"discovery_opt_in": <bool>} — any other field is ignored (not
    declared on PersonalityDiscoveryOptInSerializer, so axis/type_code stay
    unwritable via this route). 404 mirrors GET when no assessment exists.
    Evicts the public-profile cache so the personality embed (C2) reflects
    the new opt-in state immediately.
    """
    permission_classes = [IsAuthenticated]

    def _get_personality_or_404(self, request):
        """Shared owner-scoped lookup for GET + PATCH. Returns (personality, None)
        or (None, error_response)."""
        try:
            profile = request.user.profile
        except UserProfile.DoesNotExist:
            return None, Response(
                {'detail': 'UserProfile not found for current user.'},
                status=status.HTTP_404_NOT_FOUND,
            )

        try:
            personality = profile.personality
        except PersonalityProfile.DoesNotExist:
            return None, Response(
                {'detail': 'No personality assessment found. Complete the assessment first.'},
                status=status.HTTP_404_NOT_FOUND,
            )

        return personality, None

    def get(self, request):
        personality, error = self._get_personality_or_404(request)
        if error is not None:
            return error
        return Response(PersonalityProfileSerializer(personality).data)

    def patch(self, request):
        personality, error = self._get_personality_or_404(request)
        if error is not None:
            return error

        serializer = PersonalityDiscoveryOptInSerializer(
            personality, data=request.data, partial=False,
        )
        serializer.is_valid(raise_exception=True)
        changed = serializer.validated_data['discovery_opt_in'] != personality.discovery_opt_in
        serializer.save()

        if changed:
            # Evict the public-profile cache so GET /users/<id>/ (C2 gate)
            # reflects the new discovery_opt_in state on the very next request.
            # personality.user is a UserProfile (OneToOne) — the cache is keyed
            # on the Django User id (the URL's <user_id>), i.e. UserProfile.user_id
            # (the FK column), NOT UserProfile.id / personality.user.id.
            from apps.recommendation.caches import evict_user_profile_detail
            evict_user_profile_detail(personality.user.user_id)

        return Response(PersonalityProfileSerializer(personality).data)
