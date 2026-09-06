"""
test_liked_buildings.py -- Tests for LikedBuildingsView (SNS-LIKED-PROJECTS).

Coverage:
  TestLikedBuildingsPost    (5 tests) -- POST add, dedup, validation, 401
  TestLikedBuildingsGet     (3 tests) -- GET list, empty, 401
  TestLikedBuildingsCap     (1 test)  -- cap at 200 enforced silently
  TestGuestLikeLimit        (4 tests) -- BACK-AUTH-3 guest gate at 50 likes
"""
import pytest
from unittest.mock import MagicMock, patch
from django.contrib.auth.models import User
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from apps.accounts.models import UserProfile


def _make_buildings_cursor_mock(exists=True):
    """Return a mock cursor context-manager that simulates the buildings DB.

    When exists=True the cursor's fetchone() returns a truthy row (building
    found + publishable); when False it returns None (404 path).
    """
    cur = MagicMock()
    cur.fetchone.return_value = (1,) if exists else None
    cm = MagicMock()
    cm.__enter__ = MagicMock(return_value=cur)
    cm.__exit__ = MagicMock(return_value=False)
    conn = MagicMock()
    conn.cursor.return_value = cm
    return conn


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def lb_user_and_profile(db):
    """Fresh User + UserProfile for liked-buildings tests."""
    user = User.objects.create_user(
        username='lbuser', email='lb@example.com', password='pass123',
    )
    profile = UserProfile.objects.create(user=user, display_name='LB User')
    return user, profile


@pytest.fixture
def lb_auth_client(lb_user_and_profile):
    """Authenticated APIClient for the lb user."""
    user, _ = lb_user_and_profile
    client = APIClient()
    refresh = RefreshToken.for_user(user)
    client.credentials(HTTP_AUTHORIZATION=f'Bearer {refresh.access_token}')
    return client


@pytest.fixture
def anon_client():
    return APIClient()


_FAKE_CARD = {
    'canonical_bld_id': 'bld_000123',
    'name': 'Test Building',
    'image_url': 'https://example.com/img.jpg',
}

_LIKED_URL = '/api/v1/liked-buildings/'


# ---------------------------------------------------------------------------
# TestLikedBuildingsPost
# ---------------------------------------------------------------------------

class TestLikedBuildingsPost:

    @pytest.mark.django_db
    def test_post_adds_building(self, lb_user_and_profile, lb_auth_client):
        """POST with valid canonical_bld_id returns 200 with liked_count=1."""
        _, profile = lb_user_and_profile
        conn_mock = _make_buildings_cursor_mock(exists=True)
        with patch('apps.accounts.views.profile._dj_connections', {'buildings': conn_mock}):
            response = lb_auth_client.post(
                _LIKED_URL,
                {'canonical_bld_id': 'bld_000123'},
                format='json',
            )
        assert response.status_code == 200
        data = response.json()
        assert data['liked_count'] == 1
        profile.refresh_from_db()
        assert profile.liked_building_ids == ['bld_000123']

    @pytest.mark.django_db
    def test_post_deduplicates(self, lb_user_and_profile, lb_auth_client):
        """Posting the same bld_id twice does not duplicate the entry."""
        _, profile = lb_user_and_profile
        conn_mock = _make_buildings_cursor_mock(exists=True)
        with patch('apps.accounts.views.profile._dj_connections', {'buildings': conn_mock}):
            lb_auth_client.post(_LIKED_URL, {'canonical_bld_id': 'bld_000123'}, format='json')
            response = lb_auth_client.post(_LIKED_URL, {'canonical_bld_id': 'bld_000123'}, format='json')
        assert response.status_code == 200
        assert response.json()['liked_count'] == 1
        profile.refresh_from_db()
        assert profile.liked_building_ids.count('bld_000123') == 1

    @pytest.mark.django_db
    def test_post_prepends_newest_first(self, lb_user_and_profile, lb_auth_client):
        """Second distinct building is prepended so newest appears first."""
        _, profile = lb_user_and_profile
        conn_mock = _make_buildings_cursor_mock(exists=True)
        with patch('apps.accounts.views.profile._dj_connections', {'buildings': conn_mock}):
            lb_auth_client.post(_LIKED_URL, {'canonical_bld_id': 'bld_000001'}, format='json')
            lb_auth_client.post(_LIKED_URL, {'canonical_bld_id': 'bld_000002'}, format='json')
        profile.refresh_from_db()
        assert profile.liked_building_ids[0] == 'bld_000002'
        assert profile.liked_building_ids[1] == 'bld_000001'

    @pytest.mark.django_db
    def test_post_missing_field_returns_400(self, lb_auth_client):
        """POST without canonical_bld_id returns 400."""
        response = lb_auth_client.post(_LIKED_URL, {}, format='json')
        assert response.status_code == 400
        assert 'canonical_bld_id' in response.json().get('detail', '')

    @pytest.mark.django_db
    def test_post_too_long_id_returns_400(self, lb_auth_client):
        """POST with canonical_bld_id longer than 20 chars returns 400."""
        response = lb_auth_client.post(
            _LIKED_URL,
            {'canonical_bld_id': 'b' * 21},
            format='json',
        )
        assert response.status_code == 400

    @pytest.mark.django_db
    def test_post_unauthenticated_returns_401(self, anon_client):
        """POST without token returns 401."""
        response = anon_client.post(
            _LIKED_URL,
            {'canonical_bld_id': 'bld_000123'},
            format='json',
        )
        assert response.status_code == 401


# ---------------------------------------------------------------------------
# TestLikedBuildingsGet
# ---------------------------------------------------------------------------

class TestLikedBuildingsGet:

    @pytest.mark.django_db
    def test_get_returns_cards(self, lb_user_and_profile, lb_auth_client):
        """GET returns buildings list with total count."""
        _, profile = lb_user_and_profile
        profile.liked_building_ids = ['bld_000123']
        profile.save(update_fields=['liked_building_ids'])

        with patch('apps.recommendation.engine.get_buildings_by_ids', return_value=[_FAKE_CARD]):
            response = lb_auth_client.get(_LIKED_URL)

        assert response.status_code == 200
        data = response.json()
        assert data['total'] == 1
        assert len(data['buildings']) == 1
        assert data['buildings'][0]['canonical_bld_id'] == 'bld_000123'

    @pytest.mark.django_db
    def test_get_empty_list(self, lb_auth_client):
        """GET for a user with no liked buildings returns empty list."""
        with patch('apps.recommendation.engine.get_buildings_by_ids', return_value=[]):
            response = lb_auth_client.get(_LIKED_URL)

        assert response.status_code == 200
        data = response.json()
        assert data['total'] == 0
        assert data['buildings'] == []

    @pytest.mark.django_db
    def test_get_filters_none_cards(self, lb_user_and_profile, lb_auth_client):
        """GET silently drops non-publishable buildings (get_buildings_by_ids filters them)."""
        _, profile = lb_user_and_profile
        # 'bld_unpub001' is in the list but the batch function returns only the
        # publishable building — simulating is_publishable filtering in the engine.
        profile.liked_building_ids = ['bld_000123', 'bld_unpub001']
        profile.save(update_fields=['liked_building_ids'])

        with patch('apps.recommendation.engine.get_buildings_by_ids', return_value=[_FAKE_CARD]):
            response = lb_auth_client.get(_LIKED_URL)

        assert response.status_code == 200
        data = response.json()
        assert data['total'] == 1

    @pytest.mark.django_db
    def test_get_unauthenticated_returns_401(self, anon_client):
        """GET without token returns 401."""
        response = anon_client.get(_LIKED_URL)
        assert response.status_code == 401


# ---------------------------------------------------------------------------
# TestLikedBuildingsOtherUser — design-parity public-profile Liked tab
# ---------------------------------------------------------------------------

class TestLikedBuildingsOtherUser:
    """?user_id=<id> lets any AUTHENTICATED user view another user's liked
    buildings (taste-sharing product decision). No anonymous access."""

    @pytest.mark.django_db
    def test_get_other_user_liked_buildings(self, lb_user_and_profile, lb_auth_client):
        """?user_id=<other> returns that user's liked buildings, not the caller's."""
        from django.contrib.auth.models import User

        other_user = User.objects.create_user(
            username='targetlbuser', email='targetlb@example.com', password='pass123',
        )
        other_profile = UserProfile.objects.create(user=other_user, display_name='Target LB User')
        other_profile.liked_building_ids = ['bld_000123']
        other_profile.save(update_fields=['liked_building_ids'])

        with patch('apps.recommendation.engine.get_buildings_by_ids', return_value=[_FAKE_CARD]):
            response = lb_auth_client.get(_LIKED_URL, {'user_id': other_user.id})

        assert response.status_code == 200
        data = response.json()
        assert data['total'] == 1
        assert data['buildings'][0]['canonical_bld_id'] == 'bld_000123'

    @pytest.mark.django_db
    def test_get_self_user_id_matches_no_param_path(self, lb_user_and_profile, lb_auth_client):
        """?user_id=<self> behaves the same as omitting user_id."""
        _, profile = lb_user_and_profile
        profile.liked_building_ids = ['bld_000123']
        profile.save(update_fields=['liked_building_ids'])

        with patch('apps.recommendation.engine.get_buildings_by_ids', return_value=[_FAKE_CARD]):
            response = lb_auth_client.get(_LIKED_URL, {'user_id': profile.user.id})

        assert response.status_code == 200
        assert response.json()['total'] == 1

    @pytest.mark.django_db
    def test_get_unknown_user_id_404(self, lb_auth_client):
        """A user_id with no matching UserProfile -> 404."""
        response = lb_auth_client.get(_LIKED_URL, {'user_id': 999999})
        assert response.status_code == 404

    @pytest.mark.django_db
    def test_get_non_integer_user_id_400(self, lb_auth_client):
        """A non-integer user_id -> 400."""
        response = lb_auth_client.get(_LIKED_URL, {'user_id': 'abc'})
        assert response.status_code == 400

    @pytest.mark.django_db
    def test_get_other_user_unauthenticated_401(self, anon_client, lb_user_and_profile):
        """No anonymous access, even with ?user_id= set."""
        _, profile = lb_user_and_profile
        response = anon_client.get(_LIKED_URL, {'user_id': profile.user.id})
        assert response.status_code == 401


# ---------------------------------------------------------------------------
# TestLikedBuildingsCap
# ---------------------------------------------------------------------------

class TestLikedBuildingsCap:

    @pytest.mark.django_db
    def test_cap_enforced_on_post(self, lb_user_and_profile, lb_auth_client):
        """After 200 entries, adding one more keeps list at 200 (oldest dropped)."""
        _, profile = lb_user_and_profile
        # Pre-fill 200 entries directly
        profile.liked_building_ids = [f'bld_{i:06d}' for i in range(200)]
        profile.save(update_fields=['liked_building_ids'])

        # Post one more unique entry
        conn_mock = _make_buildings_cursor_mock(exists=True)
        with patch('apps.accounts.views.profile._dj_connections', {'buildings': conn_mock}):
            response = lb_auth_client.post(
                _LIKED_URL,
                {'canonical_bld_id': 'bld_999999'},
                format='json',
            )
        assert response.status_code == 200
        profile.refresh_from_db()
        assert len(profile.liked_building_ids) == 200
        assert profile.liked_building_ids[0] == 'bld_999999'


# ---------------------------------------------------------------------------
# TestGuestLikeLimit — BACK-AUTH-3: guest users gated at 50 likes
# ---------------------------------------------------------------------------

@pytest.fixture
def guest_user_and_profile(db):
    """Fresh User + guest UserProfile (is_guest=True) for guest-gate tests."""
    user = User.objects.create_user(
        username='guestlbuser', email='', password='',
    )
    profile = UserProfile.objects.create(user=user, display_name='Guest LB', is_guest=True)
    return user, profile


@pytest.fixture
def guest_auth_client(guest_user_and_profile):
    """Authenticated APIClient for the guest user."""
    user, _ = guest_user_and_profile
    client = APIClient()
    refresh = RefreshToken.for_user(user)
    client.credentials(HTTP_AUTHORIZATION=f'Bearer {refresh.access_token}')
    return client


class TestGuestLikeLimit:
    """BACK-AUTH-3: guest users capped at 50 liked buildings.

    Mirrors the board-gate precedent: 403 with detail='verify_required',
    reason='liked_limit_reached', limit=50.  Verified users are never gated.
    Re-liking an already-present id is a no-op and must not 403 even when the
    guest is at the limit.
    """

    @pytest.mark.django_db
    def test_guest_at_49_can_add_50th(self, guest_user_and_profile, guest_auth_client):
        """A guest with 49 likes can add the 50th (200 OK)."""
        _, profile = guest_user_and_profile
        profile.liked_building_ids = [f'bld_{i:06d}' for i in range(49)]
        profile.save(update_fields=['liked_building_ids'])

        conn_mock = _make_buildings_cursor_mock(exists=True)
        with patch('apps.accounts.views.profile._dj_connections', {'buildings': conn_mock}):
            response = guest_auth_client.post(
                _LIKED_URL,
                {'canonical_bld_id': 'bld_999049'},
                format='json',
            )
        assert response.status_code == 200
        profile.refresh_from_db()
        assert len(profile.liked_building_ids) == 50

    @pytest.mark.django_db
    def test_guest_at_50_blocked_on_51st(self, guest_user_and_profile, guest_auth_client):
        """A guest already at 50 likes is blocked on the 51st (403 verify_required)."""
        _, profile = guest_user_and_profile
        profile.liked_building_ids = [f'bld_{i:06d}' for i in range(50)]
        profile.save(update_fields=['liked_building_ids'])

        conn_mock = _make_buildings_cursor_mock(exists=True)
        with patch('apps.accounts.views.profile._dj_connections', {'buildings': conn_mock}):
            response = guest_auth_client.post(
                _LIKED_URL,
                {'canonical_bld_id': 'bld_999999'},
                format='json',
            )
        assert response.status_code == 403
        data = response.json()
        assert data['detail'] == 'verify_required'
        assert data['reason'] == 'liked_limit_reached'
        assert data['limit'] == 50

    @pytest.mark.django_db
    def test_verified_user_not_blocked_at_50_plus(self, lb_user_and_profile, lb_auth_client):
        """A verified (non-guest) user at 50+ likes is NOT blocked by the gate."""
        _, profile = lb_user_and_profile
        # verified: is_guest=False (default from lb_user_and_profile fixture)
        profile.liked_building_ids = [f'bld_{i:06d}' for i in range(50)]
        profile.save(update_fields=['liked_building_ids'])

        conn_mock = _make_buildings_cursor_mock(exists=True)
        with patch('apps.accounts.views.profile._dj_connections', {'buildings': conn_mock}):
            response = lb_auth_client.post(
                _LIKED_URL,
                {'canonical_bld_id': 'bld_999999'},
                format='json',
            )
        assert response.status_code == 200

    @pytest.mark.django_db
    def test_guest_at_limit_reliking_existing_not_blocked(self, guest_user_and_profile, guest_auth_client):
        """A guest at 50 likes re-liking an already-present id is a no-op (200, not 403).

        The gate is ONLY inside `if bld_id not in current:`, so re-liking is
        short-circuited before the gate runs — the guest must not be 403'd.
        """
        _, profile = guest_user_and_profile
        ids = [f'bld_{i:06d}' for i in range(50)]
        profile.liked_building_ids = ids
        profile.save(update_fields=['liked_building_ids'])

        conn_mock = _make_buildings_cursor_mock(exists=True)
        with patch('apps.accounts.views.profile._dj_connections', {'buildings': conn_mock}):
            response = guest_auth_client.post(
                _LIKED_URL,
                {'canonical_bld_id': ids[0]},  # already in the list
                format='json',
            )
        assert response.status_code == 200
        assert response.json()['liked_count'] == 50
