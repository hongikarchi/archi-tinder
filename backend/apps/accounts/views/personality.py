"""accounts.views.personality — Personality assessment endpoints.

POST /api/v1/personality/assessment/
  body: {"responses": [int × 20]}  each value -2..+2
  Creates or updates the caller's PersonalityProfile.
  Returns 201 (created) or 200 (updated) with the PersonalityProfileSerializer shape.

GET /api/v1/personality/me/
  Returns the caller's PersonalityProfile (404 if none exists yet).
"""
import logging

from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from ..models import PersonalityProfile, UserProfile
from ..serializers import PersonalityAssessmentSerializer, PersonalityProfileSerializer

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
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        try:
            profile = request.user.profile
        except UserProfile.DoesNotExist:
            return Response(
                {'detail': 'UserProfile not found for current user.'},
                status=status.HTTP_404_NOT_FOUND,
            )

        try:
            personality = profile.personality
        except PersonalityProfile.DoesNotExist:
            return Response(
                {'detail': 'No personality assessment found. Complete the assessment first.'},
                status=status.HTTP_404_NOT_FOUND,
            )

        return Response(PersonalityProfileSerializer(personality).data)
