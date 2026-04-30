"""
test_phase13_userprofile.py -- Phase 13 PROF2 UserProfile extension backend tests.

Tests: UserProfile model (6 new fields + defaults), UserProfileDetailView
       (GET /api/v1/users/{user_id}/), and UserProfileSelfUpdateView
       (PATCH /api/v1/users/me/).

Coverage:
  TestUserProfileExtensionModel (3 tests)  -- model defaults, __str__, existing fields
  TestUserProfileDetailView     (5 tests)  -- public GET shape, 404, excluded fields, no-auth
  TestUserProfileSelfUpdateView (7 tests)  -- 401 unauth, bio/mbti/links PATCH, validation,
                                             read-only fields ignored
"""
import pytest
from django.contrib.auth.models import User
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from apps.accounts.models import UserProfile


# ---------------------------------------------------------------------------
# Helpers / Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def user_and_profile(db):
    """Create a fresh User + UserProfile (clean slate, no pre-existing social accounts)."""
    user = User.objects.create_user(
        username='profuser', email='prof@example.com', password='pass123',
    )
    profile = UserProfile.objects.create(user=user, display_name='Prof User')
    return user, profile


@pytest.fixture
def auth_client_for(user_and_profile):
    """Authenticated APIClient for the user_and_profile fixture user."""
    user, _ = user_and_profile
    client = APIClient()
    refresh = RefreshToken.for_user(user)
    client.credentials(HTTP_AUTHORIZATION=f'Bearer {refresh.access_token}')
    return client


# ---------------------------------------------------------------------------
# TestUserProfileExtensionModel
# ---------------------------------------------------------------------------

class TestUserProfileExtensionModel:

    @pytest.mark.django_db
    def test_userprofile_create_with_default_extension_fields(self, user_and_profile):
        """New PROF2 fields all have correct defaults after plain create()."""
        _, profile = user_and_profile
        assert profile.bio == ''
        assert profile.mbti == ''
        assert profile.external_links == {}
        assert profile.persona_summary == {}
        assert profile.follower_count == 0
        assert profile.following_count == 0

    @pytest.mark.django_db
    def test_userprofile_str_repr_unchanged(self, user_and_profile):
        """__str__ still returns display_name (unchanged by PROF2)."""
        _, profile = user_and_profile
        assert str(profile) == 'Prof User'

    @pytest.mark.django_db
    def test_userprofile_existing_fields_preserved(self, user_and_profile):
        """Original fields (user, display_name, avatar_url, timestamps) still present."""
        user, profile = user_and_profile
        assert profile.user == user
        assert profile.display_name == 'Prof User'
        assert profile.avatar_url is None
        assert profile.created_at is not None
        assert profile.updated_at is not None


# ---------------------------------------------------------------------------
# TestUserProfileDetailView
# ---------------------------------------------------------------------------

class TestUserProfileDetailView:

    @pytest.mark.django_db
    def test_get_userprofile_returns_mock_user_shape(self, user_and_profile):
        """GET /api/v1/users/{user_id}/ returns all MOCK_USER fields in scope for PROF2."""
        user, profile = user_and_profile
        client = APIClient()
        response = client.get(f'/api/v1/users/{user.id}/')
        assert response.status_code == 200
        data = response.json()
        # Required MOCK_USER keys (boards + is_following deferred)
        for key in ['user_id', 'display_name', 'avatar_url', 'bio', 'mbti',
                    'external_links', 'persona_summary', 'follower_count', 'following_count']:
            assert key in data, f'Expected key "{key}" in response'
        assert data['user_id'] == user.id
        assert data['display_name'] == 'Prof User'

    @pytest.mark.django_db
    def test_get_userprofile_404_on_missing_user(self):
        """GET /api/v1/users/99999/ returns 404 when no such user exists."""
        client = APIClient()
        response = client.get('/api/v1/users/99999/')
        assert response.status_code == 404

    @pytest.mark.django_db
    def test_get_userprofile_includes_is_following(self, user_and_profile):
        """Response includes is_following (SOC1 shipped: always present, false for unauthenticated)."""
        user, _ = user_and_profile
        client = APIClient()
        response = client.get(f'/api/v1/users/{user.id}/')
        data = response.json()
        assert 'is_following' in data
        assert data['is_following'] is False  # unauthenticated => always false

    @pytest.mark.django_db
    def test_get_userprofile_includes_boards(self, user_and_profile):
        """Response includes boards[] (BOARD1 contract)."""
        user, _ = user_and_profile
        client = APIClient()
        response = client.get(f'/api/v1/users/{user.id}/')
        body = response.json()
        assert 'boards' in body
        assert isinstance(body['boards'], list)

    @pytest.mark.django_db
    def test_get_userprofile_no_auth_required(self, user_and_profile):
        """Unauthenticated request returns 200 (AllowAny)."""
        user, _ = user_and_profile
        client = APIClient()  # no credentials set
        response = client.get(f'/api/v1/users/{user.id}/')
        assert response.status_code == 200


# ---------------------------------------------------------------------------
# TestUserProfileSelfUpdateView
# ---------------------------------------------------------------------------

class TestUserProfileSelfUpdateView:

    @pytest.mark.django_db
    def test_patch_self_unauthenticated_returns_401(self):
        """PATCH /api/v1/users/me/ without auth token returns 401."""
        client = APIClient()
        response = client.patch('/api/v1/users/me/', {'bio': 'anon'}, format='json')
        assert response.status_code == 401

    @pytest.mark.django_db
    def test_patch_self_updates_bio(self, user_and_profile, auth_client_for):
        """PATCH with bio updates the field; other fields remain unchanged."""
        user, profile = user_and_profile
        response = auth_client_for.patch(
            '/api/v1/users/me/', {'bio': 'Architecture student at SNU.'}, format='json',
        )
        assert response.status_code == 200
        data = response.json()
        assert data['bio'] == 'Architecture student at SNU.'
        # Unchanged fields
        assert data['display_name'] == 'Prof User'
        assert data['follower_count'] == 0

    @pytest.mark.django_db
    def test_patch_self_updates_mbti_uppercased(self, user_and_profile, auth_client_for):
        """PATCH with mbti='intj' stores as 'INTJ' (validator uppercases)."""
        response = auth_client_for.patch(
            '/api/v1/users/me/', {'mbti': 'intj'}, format='json',
        )
        assert response.status_code == 200
        assert response.json()['mbti'] == 'INTJ'

    @pytest.mark.django_db
    def test_patch_self_invalid_mbti_returns_400(self, user_and_profile, auth_client_for):
        """PATCH with mbti='ABC' (3 chars) returns 400 validation error."""
        response = auth_client_for.patch(
            '/api/v1/users/me/', {'mbti': 'ABC'}, format='json',
        )
        assert response.status_code == 400

    @pytest.mark.django_db
    def test_patch_self_updates_external_links(self, user_and_profile, auth_client_for):
        """PATCH with external_links stores the dict correctly."""
        payload = {'external_links': {'instagram': '@kimarch', 'email': 'kim@example.com'}}
        response = auth_client_for.patch('/api/v1/users/me/', payload, format='json')
        assert response.status_code == 200
        links = response.json()['external_links']
        assert links['instagram'] == '@kimarch'
        assert links['email'] == 'kim@example.com'

    @pytest.mark.django_db
    def test_patch_self_invalid_external_links_returns_400(self, user_and_profile, auth_client_for):
        """PATCH with external_links as a string (not dict) returns 400."""
        response = auth_client_for.patch(
            '/api/v1/users/me/', {'external_links': 'not-a-dict'}, format='json',
        )
        assert response.status_code == 400

    @pytest.mark.django_db
    def test_patch_self_does_not_update_follower_count(self, user_and_profile, auth_client_for):
        """PATCH with follower_count=999 is ignored (read-only counter cache)."""
        response = auth_client_for.patch(
            '/api/v1/users/me/', {'follower_count': 999}, format='json',
        )
        assert response.status_code == 200
        # follower_count must remain 0 — not in UserProfileSelfUpdateSerializer fields
        assert response.json()['follower_count'] == 0

    @pytest.mark.django_db
    def test_patch_self_does_not_update_persona_summary(self, user_and_profile, auth_client_for):
        """PATCH with persona_summary is silently ignored (Phase 17 LLM-derived, not in serializer)."""
        payload = {'persona_summary': {'persona_type': 'The Hacker', 'one_liner': 'test'}}
        response = auth_client_for.patch('/api/v1/users/me/', payload, format='json')
        assert response.status_code == 200
        # persona_summary should remain empty dict (not user-settable)
        assert response.json()['persona_summary'] == {}

    # --- Fix 1: MBTI alpha-only enforcement ---

    @pytest.mark.django_db
    def test_patch_self_invalid_mbti_numeric_returns_400(self, user_and_profile, auth_client_for):
        """PATCH with mbti='1234' (4 digits, no letters) returns 400."""
        response = auth_client_for.patch(
            '/api/v1/users/me/', {'mbti': '1234'}, format='json',
        )
        assert response.status_code == 400

    @pytest.mark.django_db
    def test_patch_self_mbti_whitespace_only_clears_field(self, user_and_profile, auth_client_for):
        """PATCH with mbti='    ' (4 spaces) is treated as empty by DRF CharField trim_whitespace.

        DRF strips whitespace before validate_mbti runs, so '    ' becomes '' (falsy),
        which the validator accepts as "clear the field". Returns 200, mbti=''.
        """
        response = auth_client_for.patch(
            '/api/v1/users/me/', {'mbti': '    '}, format='json',
        )
        assert response.status_code == 200
        assert response.json()['mbti'] == ''

    # --- Fix 2: external_links validator test coverage ---

    @pytest.mark.django_db
    def test_patch_self_external_links_non_string_value_returns_400(
        self, user_and_profile, auth_client_for,
    ):
        """PATCH with external_links value as integer (not string) returns 400."""
        response = auth_client_for.patch(
            '/api/v1/users/me/', {'external_links': {'instagram': 123}}, format='json',
        )
        assert response.status_code == 400

    @pytest.mark.django_db
    def test_patch_self_external_links_nested_dict_returns_400(
        self, user_and_profile, auth_client_for,
    ):
        """PATCH with external_links value as nested dict returns 400."""
        response = auth_client_for.patch(
            '/api/v1/users/me/',
            {'external_links': {'instagram': {'nested': 'value'}}},
            format='json',
        )
        assert response.status_code == 400

    @pytest.mark.django_db
    def test_patch_self_external_links_oversize_value_returns_400(
        self, user_and_profile, auth_client_for,
    ):
        """PATCH with external_links value exceeding 500 chars returns 400."""
        response = auth_client_for.patch(
            '/api/v1/users/me/', {'external_links': {'instagram': 'A' * 501}}, format='json',
        )
        assert response.status_code == 400

    # --- Fix 3: 404 when UserProfile does not exist for authenticated user ---

    @pytest.mark.django_db
    def test_patch_self_404_if_no_profile(self, db):
        """PATCH /api/v1/users/me/ when user has no UserProfile returns 404."""
        # Create a Django User without a UserProfile
        user = User.objects.create_user(
            username='noprofile', email='noprofile@example.com', password='pass123',
        )
        client = APIClient()
        refresh = RefreshToken.for_user(user)
        client.credentials(HTTP_AUTHORIZATION=f'Bearer {refresh.access_token}')
        response = client.patch('/api/v1/users/me/', {'bio': 'test'}, format='json')
        assert response.status_code == 404
        assert 'detail' in response.json()
