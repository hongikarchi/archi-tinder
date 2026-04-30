"""
test_follow.py -- Phase 15 SOC1 follow/unfollow backend tests.

Coverage:
  TestFollowCreate           (5)  -- 201, idempotent 200, self-follow 400, counter, shape
  TestFollowDelete           (4)  -- 204 + counter decrement, not-following 404, user 404 x2
  TestFollowersList          (2)  -- AllowAny list, pagination meta present
  TestFollowingList          (2)  -- AllowAny list, pagination meta present
  TestIsFollowingInjection   (4)  -- unauthenticated, own profile, following, not-following
  TestFollowModel            (2)  -- unique_together, self-follow via clean()
  TestFollowEdgeCases        (5)  -- follow nonexistent user 404, DB-level self-follow,
                                     cascade counter decrement, concurrent unfollow safety,
                                     signal fires on create only
  TestFollowThrottle         (1)  -- throttle scope + class configured
"""
import pytest
from django.core.exceptions import ValidationError


# ---------------------------------------------------------------------------
# TestFollowCreate
# ---------------------------------------------------------------------------

class TestFollowCreate:

    @pytest.mark.django_db
    def test_follow_creates_201(self, user_a, user_b, auth_client_a):
        """POST /users/{b}/follow/ by A returns 201 and correct shape."""
        _, b_profile = user_b
        response = auth_client_a.post(f'/api/v1/users/{b_profile.user.id}/follow/')
        assert response.status_code == 201
        data = response.json()
        assert data['following'] is True
        assert 'follower_count' in data

    @pytest.mark.django_db
    def test_follow_increments_counters(self, user_a, user_b, auth_client_a):
        """Following B increments B.follower_count and A.following_count by 1."""
        _, a_profile = user_a
        _, b_profile = user_b
        auth_client_a.post(f'/api/v1/users/{b_profile.user.id}/follow/')
        a_profile.refresh_from_db()
        b_profile.refresh_from_db()
        assert a_profile.following_count == 1
        assert b_profile.follower_count == 1

    @pytest.mark.django_db
    def test_follow_twice_idempotent_200(self, user_a, user_b, auth_client_a):
        """Second POST to follow same user returns 200, counts stay at 1."""
        _, a_profile = user_a
        _, b_profile = user_b
        auth_client_a.post(f'/api/v1/users/{b_profile.user.id}/follow/')
        response = auth_client_a.post(f'/api/v1/users/{b_profile.user.id}/follow/')
        assert response.status_code == 200
        a_profile.refresh_from_db()
        b_profile.refresh_from_db()
        # Counts must NOT be incremented a second time
        assert a_profile.following_count == 1
        assert b_profile.follower_count == 1

    @pytest.mark.django_db
    def test_follow_self_returns_400(self, user_a, auth_client_a):
        """POST to follow own user_id returns 400."""
        user, _ = user_a
        response = auth_client_a.post(f'/api/v1/users/{user.id}/follow/')
        assert response.status_code == 400
        assert 'detail' in response.json()

    @pytest.mark.django_db
    def test_follow_response_follower_count_matches_db(self, user_a, user_b, auth_client_a):
        """follower_count in POST 201 response matches the DB value."""
        _, b_profile = user_b
        response = auth_client_a.post(f'/api/v1/users/{b_profile.user.id}/follow/')
        assert response.status_code == 201
        b_profile.refresh_from_db()
        assert response.json()['follower_count'] == b_profile.follower_count


# ---------------------------------------------------------------------------
# TestFollowDelete
# ---------------------------------------------------------------------------

class TestFollowDelete:

    @pytest.mark.django_db
    def test_unfollow_returns_204(self, user_a, user_b, auth_client_a):
        """DELETE after follow returns 204 and decrements counters."""
        _, a_profile = user_a
        _, b_profile = user_b
        auth_client_a.post(f'/api/v1/users/{b_profile.user.id}/follow/')
        response = auth_client_a.delete(f'/api/v1/users/{b_profile.user.id}/follow/')
        assert response.status_code == 204
        a_profile.refresh_from_db()
        b_profile.refresh_from_db()
        assert a_profile.following_count == 0
        assert b_profile.follower_count == 0

    @pytest.mark.django_db
    def test_unfollow_not_following_returns_404(self, user_a, user_b, auth_client_a):
        """DELETE when not following returns 404 (not idempotent per spec)."""
        _, b_profile = user_b
        response = auth_client_a.delete(f'/api/v1/users/{b_profile.user.id}/follow/')
        assert response.status_code == 404

    @pytest.mark.django_db
    def test_follow_nonexistent_user_returns_404(self, auth_client_a):
        """POST /users/99999/follow/ returns 404 when user doesn't exist."""
        response = auth_client_a.post('/api/v1/users/99999/follow/')
        assert response.status_code == 404

    @pytest.mark.django_db
    def test_unfollow_nonexistent_user_returns_404(self, auth_client_a):
        """DELETE /users/99999/follow/ returns 404 when user doesn't exist."""
        response = auth_client_a.delete('/api/v1/users/99999/follow/')
        assert response.status_code == 404


# ---------------------------------------------------------------------------
# TestFollowersList
# ---------------------------------------------------------------------------

class TestFollowersList:

    @pytest.mark.django_db
    def test_followers_list_allows_any(self, user_a, user_b, user_c, auth_client_a, anon_client):
        """GET /users/{b}/followers/ works without auth (AllowAny)."""
        _, b_profile = user_b
        # A follows B
        auth_client_a.post(f'/api/v1/users/{b_profile.user.id}/follow/')
        response = anon_client.get(f'/api/v1/users/{b_profile.user.id}/followers/')
        assert response.status_code == 200
        data = response.json()
        assert 'results' in data
        assert 'total' in data
        assert 'has_more' in data
        assert data['total'] == 1
        # Follower should be A
        assert data['results'][0]['user_id'] == user_a[0].id

    @pytest.mark.django_db
    def test_followers_list_pagination_meta(self, user_b, anon_client):
        """GET /users/{b}/followers/ with no followers returns expected pagination shape."""
        _, b_profile = user_b
        response = anon_client.get(f'/api/v1/users/{b_profile.user.id}/followers/')
        assert response.status_code == 200
        data = response.json()
        for key in ['results', 'page', 'page_size', 'has_more', 'total']:
            assert key in data, f'Expected key "{key}" in response'
        assert data['total'] == 0
        assert data['results'] == []


# ---------------------------------------------------------------------------
# TestFollowingList
# ---------------------------------------------------------------------------

class TestFollowingList:

    @pytest.mark.django_db
    def test_following_list_allows_any(self, user_a, user_b, auth_client_a, anon_client):
        """GET /users/{a}/following/ works without auth and returns B."""
        _, a_profile = user_a
        _, b_profile = user_b
        auth_client_a.post(f'/api/v1/users/{b_profile.user.id}/follow/')
        response = anon_client.get(f'/api/v1/users/{a_profile.user.id}/following/')
        assert response.status_code == 200
        data = response.json()
        assert data['total'] == 1
        assert data['results'][0]['user_id'] == b_profile.user.id

    @pytest.mark.django_db
    def test_following_list_pagination_meta(self, user_a, anon_client):
        """GET /users/{a}/following/ with no follows returns expected pagination shape."""
        _, a_profile = user_a
        response = anon_client.get(f'/api/v1/users/{a_profile.user.id}/following/')
        assert response.status_code == 200
        data = response.json()
        for key in ['results', 'page', 'page_size', 'has_more', 'total']:
            assert key in data


# ---------------------------------------------------------------------------
# TestIsFollowingInjection
# ---------------------------------------------------------------------------

class TestIsFollowingInjection:

    @pytest.mark.django_db
    def test_is_following_false_for_unauthenticated(self, user_b, anon_client):
        """GET /users/{b}/ without auth → is_following: false."""
        _, b_profile = user_b
        response = anon_client.get(f'/api/v1/users/{b_profile.user.id}/')
        assert response.status_code == 200
        data = response.json()
        assert 'is_following' in data
        assert data['is_following'] is False

    @pytest.mark.django_db
    def test_is_following_false_for_own_profile(self, user_a, auth_client_a):
        """GET /users/{a}/ by A (own profile) → is_following: false."""
        user, _ = user_a
        response = auth_client_a.get(f'/api/v1/users/{user.id}/')
        assert response.status_code == 200
        assert response.json()['is_following'] is False

    @pytest.mark.django_db
    def test_is_following_true_when_following(self, user_a, user_b, auth_client_a):
        """GET /users/{b}/ by A after A follows B → is_following: true."""
        _, b_profile = user_b
        auth_client_a.post(f'/api/v1/users/{b_profile.user.id}/follow/')
        response = auth_client_a.get(f'/api/v1/users/{b_profile.user.id}/')
        assert response.status_code == 200
        assert response.json()['is_following'] is True

    @pytest.mark.django_db
    def test_is_following_false_when_not_following(self, user_a, user_b, auth_client_a):
        """GET /users/{b}/ by A when A does NOT follow B → is_following: false."""
        _, b_profile = user_b
        response = auth_client_a.get(f'/api/v1/users/{b_profile.user.id}/')
        assert response.status_code == 200
        assert response.json()['is_following'] is False


# ---------------------------------------------------------------------------
# TestFollowModel
# ---------------------------------------------------------------------------

class TestFollowModel:

    @pytest.mark.django_db
    def test_unique_together_enforced_at_orm(self, user_a, user_b):
        """Creating duplicate Follow row via ORM raises IntegrityError."""
        from django.db import IntegrityError
        from apps.social.models import Follow
        _, a_profile = user_a
        _, b_profile = user_b
        Follow.objects.create(follower=a_profile, followee=b_profile)
        with pytest.raises(IntegrityError):
            Follow.objects.create(follower=a_profile, followee=b_profile)

    @pytest.mark.django_db
    def test_self_follow_clean_raises_validation_error(self, user_a):
        """Follow.clean() raises ValidationError when follower == followee."""
        from apps.social.models import Follow
        _, a_profile = user_a
        follow = Follow(follower=a_profile, followee=a_profile)
        with pytest.raises(ValidationError):
            follow.clean()


# ---------------------------------------------------------------------------
# TestFollowEdgeCases
# ---------------------------------------------------------------------------

class TestFollowEdgeCases:

    @pytest.mark.django_db
    def test_self_follow_blocked_at_db_level(self, user_a):
        """Follow.objects.create(follower=u, followee=u) hits CHECK constraint → IntegrityError.

        This bypasses clean() and tests the DB-level enforcement added in
        migration 0002 (social_follow_no_self_follow CHECK constraint).
        """
        from django.db import IntegrityError
        from apps.social.models import Follow
        _, a_profile = user_a
        with pytest.raises(IntegrityError):
            Follow.objects.create(follower=a_profile, followee=a_profile)

    @pytest.mark.django_db
    def test_cascade_delete_decrements_counters(self, user_a, user_b, django_user_model):
        """Deleting user A (who follows B) triggers CASCADE on Follow rows.

        The post_delete signal fires per deleted Follow instance, decrementing
        B.follower_count and A.following_count via Greatest(..., 0).
        """
        from apps.social.models import Follow
        user_a_obj, a_profile = user_a
        _, b_profile = user_b

        Follow.objects.create(follower=a_profile, followee=b_profile)
        b_profile.refresh_from_db()
        assert b_profile.follower_count == 1

        # Delete A's auth user — cascades to UserProfile → Follow rows.
        user_a_obj.delete()

        b_profile.refresh_from_db()
        assert b_profile.follower_count == 0

    @pytest.mark.django_db
    def test_concurrent_unfollow_no_negative_count(self, user_a, user_b):
        """Simulated double-delete: second filter().delete() is a no-op, count stays >= 0.

        In production, filter().delete() is atomic; the second call deletes 0 rows
        and no post_delete signal fires, so counter is never decremented below 0.
        """
        from apps.social.models import Follow
        _, a_profile = user_a
        _, b_profile = user_b

        Follow.objects.create(follower=a_profile, followee=b_profile)
        b_profile.refresh_from_db()
        assert b_profile.follower_count == 1

        # First delete — should decrement
        deleted_count, _ = Follow.objects.filter(
            follower=a_profile, followee=b_profile
        ).delete()
        assert deleted_count == 1

        b_profile.refresh_from_db()
        assert b_profile.follower_count == 0

        # Second delete — no rows, no signal, count unchanged
        deleted_count2, _ = Follow.objects.filter(
            follower=a_profile, followee=b_profile
        ).delete()
        assert deleted_count2 == 0

        b_profile.refresh_from_db()
        assert b_profile.follower_count == 0

    @pytest.mark.django_db
    def test_signal_increments_on_first_save_only(self, user_a, user_b):
        """post_save signal only increments counters when created=True.

        Calling follow.save() again (update path, created=False) must NOT
        increment counters a second time.
        """
        from apps.social.models import Follow
        _, a_profile = user_a
        _, b_profile = user_b

        follow = Follow.objects.create(follower=a_profile, followee=b_profile)
        b_profile.refresh_from_db()
        a_profile.refresh_from_db()
        assert b_profile.follower_count == 1
        assert a_profile.following_count == 1

        # Force an update-save (created=False path in signal)
        follow.save()

        b_profile.refresh_from_db()
        a_profile.refresh_from_db()
        assert b_profile.follower_count == 1, 'Counter must not double-increment on re-save'
        assert a_profile.following_count == 1, 'Counter must not double-increment on re-save'


# ---------------------------------------------------------------------------
# TestFollowThrottle
# ---------------------------------------------------------------------------

class TestFollowThrottle:

    def test_follow_write_throttle_configured(self):
        """FollowView uses FollowWriteThrottle and the scope is registered in settings."""
        from django.conf import settings
        from apps.social.views import FollowView, FollowWriteThrottle
        from rest_framework.throttling import UserRateThrottle

        # Check throttle class is a UserRateThrottle subclass with correct scope
        assert issubclass(FollowWriteThrottle, UserRateThrottle)
        assert FollowWriteThrottle.scope == 'follow_write'

        # Check throttle class is wired into FollowView
        assert FollowWriteThrottle in FollowView.throttle_classes

        # Check the scope rate is registered in settings (structural assertion)
        throttle_rates = settings.REST_FRAMEWORK.get('DEFAULT_THROTTLE_RATES', {})
        assert 'follow_write' in throttle_rates, (
            "'follow_write' scope missing from REST_FRAMEWORK DEFAULT_THROTTLE_RATES"
        )
