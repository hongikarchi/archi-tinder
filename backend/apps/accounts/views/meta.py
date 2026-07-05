"""SETTINGS-POLISH-1: public metadata endpoints (no auth, no DB query).

Currently just the onboarding-role list, consumed pre-auth by the signup
ProfileStep and by the profile-edit Role dropdown.
"""
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from ..models import UserProfile


class RolesView(APIView):
    """GET /api/v1/meta/roles/ — public role list (value + en/ko labels).

    AllowAny: the login/signup page needs this pre-auth. Pure constant
    serialization off UserProfile.ONBOARDING_ROLE_CHOICES /
    ONBOARDING_ROLE_LABELS_KO — no DB query.

    Response 200:
        {"roles": [{"value": "student", "label_en": "Student", "label_ko": "학생"}, ...]}

    Order matches ONBOARDING_ROLE_CHOICES (5 entries). label_ko falls back
    to label_en if a key is missing from ONBOARDING_ROLE_LABELS_KO, so a
    role added to CHOICES without its ko label degrades gracefully instead
    of 500ing.
    """
    permission_classes = [AllowAny]

    def get(self, request):
        roles = [
            {
                'value': value,
                'label_en': label_en,
                'label_ko': UserProfile.ONBOARDING_ROLE_LABELS_KO.get(value, label_en),
            }
            for value, label_en in UserProfile.ONBOARDING_ROLE_CHOICES
        ]
        return Response({'roles': roles})
