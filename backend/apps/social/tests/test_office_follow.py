"""
test_office_follow.py -- Phase 15 SOC3 Office follow backend tests.

Coverage:
  TestOfficeFollowCreate       (3) -- 201, idempotent 200, missing office 404
  TestOfficeFollowDelete       (2) -- 204 + counter decrement, not-following 404
  TestOfficeFollowAuth         (2) -- unauthenticated POST/DELETE 401
  TestOfficeIsFollowing        (2) -- OfficeDetailView is_following true/false
  TestOfficeFollowThrottle     (1) -- shared follow_write throttle cap smoke
"""
import uuid

import pytest


@pytest.fixture(autouse=True)
def clear_throttle_cache():
    """Keep UserRateThrottle cache state isolated across office-follow tests."""
    from django.core.cache import cache
    cache.clear()
    yield
    cache.clear()


@pytest.fixture
def office(db):
    from apps.profiles.models import Office
    return Office.objects.create(
        name='Office for Metropolitan Architecture',
        description='Rotterdam-based architecture office',
        website='https://oma.com',
        contact_email='info@oma.com',
    )


def _office_follow_url(office_id):
    return f'/api/v1/offices/{office_id}/follow/'


def _office_url(office_id):
    return f'/api/v1/offices/{office_id}/'


class TestOfficeFollowCreate:

    @pytest.mark.django_db
    def test_follow_office_creates_row_and_increments_count(self, user_a, auth_client_a, office):
        """POST /offices/{office}/follow/ creates OfficeFollow and increments follower_count."""
        from apps.social.models import OfficeFollow
        _, a_profile = user_a

        response = auth_client_a.post(_office_follow_url(office.office_id))

        assert response.status_code == 201
        assert response.json() == {'follower_count': 1, 'following': True}
        office.refresh_from_db()
        assert office.follower_count == 1
        assert OfficeFollow.objects.filter(follower=a_profile, followee=office).exists()

    @pytest.mark.django_db
    def test_follow_office_twice_is_idempotent(self, auth_client_a, office):
        """Second POST returns 200 and does not double-increment follower_count."""
        first = auth_client_a.post(_office_follow_url(office.office_id))
        second = auth_client_a.post(_office_follow_url(office.office_id))

        assert first.status_code == 201
        assert second.status_code == 200
        assert second.json() == {'follower_count': 1, 'following': True}
        office.refresh_from_db()
        assert office.follower_count == 1

    @pytest.mark.django_db
    def test_follow_missing_office_returns_404(self, auth_client_a):
        """POST on a missing office UUID returns 404."""
        response = auth_client_a.post(_office_follow_url(uuid.uuid4()))
        assert response.status_code == 404


class TestOfficeFollowDelete:

    @pytest.mark.django_db
    def test_unfollow_office_removes_row_and_decrements_count(self, user_a, auth_client_a, office):
        """DELETE after POST removes OfficeFollow and decrements follower_count."""
        from apps.social.models import OfficeFollow
        _, a_profile = user_a

        response = auth_client_a.post(_office_follow_url(office.office_id))
        assert response.status_code == 201
        office.refresh_from_db()
        assert office.follower_count == 1

        response = auth_client_a.delete(_office_follow_url(office.office_id))

        assert response.status_code == 204
        office.refresh_from_db()
        assert office.follower_count == 0
        assert not OfficeFollow.objects.filter(follower=a_profile, followee=office).exists()

    @pytest.mark.django_db
    def test_unfollow_office_not_following_returns_404(self, auth_client_a, office):
        """DELETE when no OfficeFollow exists returns 404."""
        response = auth_client_a.delete(_office_follow_url(office.office_id))
        assert response.status_code == 404
        assert response.json()['detail'] == 'Not following.'


class TestOfficeFollowAuth:

    @pytest.mark.django_db
    def test_follow_office_unauthenticated_returns_401(self, anon_client, office):
        """Anonymous POST is rejected by IsAuthenticated."""
        response = anon_client.post(_office_follow_url(office.office_id))
        assert response.status_code == 401

    @pytest.mark.django_db
    def test_unfollow_office_unauthenticated_returns_401(self, anon_client, office):
        """Anonymous DELETE is rejected by IsAuthenticated."""
        response = anon_client.delete(_office_follow_url(office.office_id))
        assert response.status_code == 401


class TestOfficeIsFollowing:

    @pytest.mark.django_db
    def test_office_detail_is_following_true_after_post(self, auth_client_a, office):
        """GET /offices/{id}/ reports is_following=true after authenticated follow."""
        response = auth_client_a.post(_office_follow_url(office.office_id))
        assert response.status_code == 201

        response = auth_client_a.get(_office_url(office.office_id))

        assert response.status_code == 200
        assert response.json()['is_following'] is True

    @pytest.mark.django_db
    def test_office_detail_is_following_false_after_delete(self, auth_client_a, office):
        """GET /offices/{id}/ returns is_following=false after unfollow."""
        response = auth_client_a.post(_office_follow_url(office.office_id))
        assert response.status_code == 201
        response = auth_client_a.delete(_office_follow_url(office.office_id))
        assert response.status_code == 204

        response = auth_client_a.get(_office_url(office.office_id))

        assert response.status_code == 200
        assert response.json()['is_following'] is False


class TestOfficeFollowThrottle:

    @pytest.mark.django_db
    def test_office_follow_uses_shared_follow_write_throttle_cap(self, auth_client_a, office):
        """OfficeFollowView reuses follow_write; 61st write in one minute is throttled."""
        from apps.social.views import FollowWriteThrottle, OfficeFollowView

        assert FollowWriteThrottle in OfficeFollowView.throttle_classes
        assert FollowWriteThrottle.scope == 'follow_write'

        url = _office_follow_url(office.office_id)
        for _ in range(60):
            response = auth_client_a.post(url)
            assert response.status_code in (200, 201)

        response = auth_client_a.post(url)
        assert response.status_code == 429
