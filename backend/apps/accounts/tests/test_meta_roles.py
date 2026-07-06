"""
test_meta_roles.py -- Backend tests for SETTINGS-POLISH-1 role list single-source.

Coverage:
  TestRolesEndpoint       (3 tests) -- unauthenticated 200 with 5 roles in order,
                                       first is student/학생, shape has value/label_en/label_ko
  TestOnboardingRolePublic (2 tests) -- onboarding_role in public /users/{id}/ response,
                                        self PATCH of onboarding_role still validates choices
"""
import pytest
from django.contrib.auth.models import User
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from apps.accounts.models import UserProfile


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def user_and_profile(db):
    user = User.objects.create_user(
        username='metaroleuser', email='metarole@example.com', password='pass123',
    )
    profile = UserProfile.objects.create(user=user, display_name='Meta Role User')
    return user, profile


@pytest.fixture
def auth_client(user_and_profile):
    user, _ = user_and_profile
    client = APIClient()
    refresh = RefreshToken.for_user(user)
    client.credentials(HTTP_AUTHORIZATION=f'Bearer {refresh.access_token}')
    return client


# ---------------------------------------------------------------------------
# TestRolesEndpoint
# ---------------------------------------------------------------------------

class TestRolesEndpoint:

    @pytest.mark.django_db
    def test_unauthenticated_returns_200_with_five_roles(self):
        """GET /api/v1/meta/roles/ requires no auth and returns exactly 5 roles."""
        client = APIClient()
        response = client.get('/api/v1/meta/roles/')
        assert response.status_code == 200
        data = response.json()
        assert 'roles' in data
        assert len(data['roles']) == 5

    @pytest.mark.django_db
    def test_first_role_is_student_with_korean_label(self):
        """First role in order is student with label_ko 학생."""
        client = APIClient()
        response = client.get('/api/v1/meta/roles/')
        data = response.json()
        first = data['roles'][0]
        assert first['value'] == 'student'
        assert first['label_en'] == 'Student'
        assert first['label_ko'] == '학생'

    @pytest.mark.django_db
    def test_roles_shape_and_order_matches_choices(self):
        """Each role dict has value/label_en/label_ko; order matches model choices."""
        client = APIClient()
        response = client.get('/api/v1/meta/roles/')
        data = response.json()
        expected_values = ['student', 'architect', 'designer', 'enthusiast', 'other']
        assert [r['value'] for r in data['roles']] == expected_values
        for role in data['roles']:
            assert set(role.keys()) == {'value', 'label_en', 'label_ko'}
            assert role['label_ko']  # non-empty for all 5 known roles


# ---------------------------------------------------------------------------
# TestOnboardingRolePublic
# ---------------------------------------------------------------------------

class TestOnboardingRolePublic:

    @pytest.mark.django_db
    def test_onboarding_role_in_public_profile(self, user_and_profile, auth_client):
        """GET /api/v1/users/{user_id}/ includes onboarding_role."""
        user, _ = user_and_profile
        auth_client.patch(
            '/api/v1/users/me/', {'onboarding_role': 'architect'}, format='json',
        )
        client = APIClient()
        response = client.get(f'/api/v1/users/{user.id}/')
        assert response.status_code == 200
        data = response.json()
        assert 'onboarding_role' in data
        assert data['onboarding_role'] == 'architect'

    @pytest.mark.django_db
    def test_self_patch_onboarding_role_invalid_choice_rejected(self, auth_client):
        """PATCH onboarding_role with a value outside choices returns 400."""
        response = auth_client.patch(
            '/api/v1/users/me/', {'onboarding_role': 'not_a_real_role'}, format='json',
        )
        assert response.status_code == 400
        assert 'onboarding_role' in response.json()
