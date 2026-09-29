"""
test_full_privacy_1_discovery_optout.py -- FULL-PRIVACY-1 backend coverage.

Discovery opt-out write path (PATCH /api/v1/personality/me/) + public-profile
personality gating (UserProfileDetailView).

Coverage:
  TestPersonalityMePatch          -- write-path contract (round-trip, auth,
                                      validation, field-scoping, 404, cache evict)
  TestProfilePersonalityGating    -- non-owner/owner/anonymous visibility
  TestFeedIntegration             -- opted-out user disappears from the
                                      PeopleDiscoveryView candidate pool
"""
import pytest
from django.contrib.auth.models import User
from django.core.cache import cache
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from apps.accounts.models import PersonalityProfile, UserProfile
from apps.recommendation.models import Project


# ---------------------------------------------------------------------------
# Helpers / Fixtures
# ---------------------------------------------------------------------------

def _make_user_with_personality(username, discovery_opt_in=True, **axis_kwargs):
    user = User.objects.create_user(
        username=username, email=f'{username}@example.com', password='pass123',
    )
    profile = UserProfile.objects.create(user=user, display_name=username)
    defaults = dict(axis_1=0.5, axis_2=0.5, axis_3=0.5, axis_4=0.5, axis_5=0.5,
                    type_code='CLOT')
    defaults.update(axis_kwargs)
    personality = PersonalityProfile.objects.create(
        user=profile, discovery_opt_in=discovery_opt_in, **defaults,
    )
    return user, profile, personality


def _auth_client(user):
    client = APIClient()
    refresh = RefreshToken.for_user(user)
    client.credentials(HTTP_AUTHORIZATION=f'Bearer {refresh.access_token}')
    return client


def _feed_candidate_ids():
    """Mirrors the two-gate queryset shape in views_people.PeopleDiscoveryView.get
    (style: apps/social/tests/test_seed_discovery.py:34-45)."""
    report_image_owner_ids = set(
        Project.objects
        .filter(visibility='public')
        .exclude(report_image__isnull=True)
        .exclude(report_image='')
        .values_list('user_id', flat=True)
        .distinct()
    )
    return set(
        PersonalityProfile.objects
        .filter(discovery_opt_in=True)
        .filter(user_id__in=report_image_owner_ids)
        .values_list('user_id', flat=True)
    )


# ---------------------------------------------------------------------------
# TestPersonalityMePatch
# ---------------------------------------------------------------------------

class TestPersonalityMePatch:

    @pytest.mark.django_db
    def test_patch_roundtrip_false_then_true(self):
        """PATCH false -> GET reflects false -> PATCH true -> GET reflects true."""
        user, _, _ = _make_user_with_personality('optuser1', discovery_opt_in=True)
        client = _auth_client(user)

        resp = client.patch('/api/v1/personality/me/', {'discovery_opt_in': False}, format='json')
        assert resp.status_code == 200
        assert resp.json()['discovery_opt_in'] is False

        resp = client.get('/api/v1/personality/me/')
        assert resp.status_code == 200
        assert resp.json()['discovery_opt_in'] is False

        resp = client.patch('/api/v1/personality/me/', {'discovery_opt_in': True}, format='json')
        assert resp.status_code == 200
        assert resp.json()['discovery_opt_in'] is True

        resp = client.get('/api/v1/personality/me/')
        assert resp.json()['discovery_opt_in'] is True

    @pytest.mark.django_db
    def test_patch_anonymous_401(self):
        _make_user_with_personality('optuser2')
        client = APIClient()
        resp = client.patch('/api/v1/personality/me/', {'discovery_opt_in': False}, format='json')
        assert resp.status_code == 401

    @pytest.mark.django_db
    def test_patch_non_boolean_value_400(self):
        user, _, _ = _make_user_with_personality('optuser3')
        client = _auth_client(user)
        resp = client.patch('/api/v1/personality/me/', {'discovery_opt_in': 'yes'}, format='json')
        assert resp.status_code == 400

    @pytest.mark.django_db
    def test_patch_missing_key_400(self):
        user, _, _ = _make_user_with_personality('optuser4')
        client = _auth_client(user)
        resp = client.patch('/api/v1/personality/me/', {}, format='json')
        assert resp.status_code == 400

    @pytest.mark.django_db
    def test_patch_extra_fields_do_not_mutate(self):
        """Sending type_code / axis fields alongside discovery_opt_in has no effect."""
        user, _, personality = _make_user_with_personality(
            'optuser5', discovery_opt_in=True, type_code='CLOT', axis_1=0.5,
        )
        client = _auth_client(user)
        resp = client.patch(
            '/api/v1/personality/me/',
            {'discovery_opt_in': False, 'type_code': 'RSDT', 'axis_1': -0.9},
            format='json',
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body['discovery_opt_in'] is False
        assert body['type_code'] == 'CLOT'
        assert body['axis_1'] == 0.5

        personality.refresh_from_db()
        assert personality.type_code == 'CLOT'
        assert personality.axis_1 == 0.5

    @pytest.mark.django_db
    def test_patch_without_personality_profile_404(self):
        """User has a UserProfile but never took the assessment -> 404 (mirrors GET)."""
        user = User.objects.create_user(
            username='noassess', email='noassess@example.com', password='pass123',
        )
        UserProfile.objects.create(user=user, display_name='noassess')
        client = _auth_client(user)
        resp = client.patch('/api/v1/personality/me/', {'discovery_opt_in': False}, format='json')
        assert resp.status_code == 404

    @pytest.mark.django_db
    def test_patch_bumps_user_profile_version_on_change(self):
        """A value-changing PATCH evicts the public-profile cache (version bump).
        Style: backend/tests/test_profile_perf.py:176-199.
        """
        from apps.recommendation.caches import _user_profile_version

        user, profile, _ = _make_user_with_personality('optuser6', discovery_opt_in=True)
        cache.delete(f'user_profile_version:{user.id}')
        assert _user_profile_version(user.id) == 0

        client = _auth_client(user)
        resp = client.patch('/api/v1/personality/me/', {'discovery_opt_in': False}, format='json')
        assert resp.status_code == 200
        assert _user_profile_version(user.id) == 1

    @pytest.mark.django_db
    def test_patch_no_op_does_not_bump_version(self):
        """Setting the same value it already had should not evict (no change)."""
        from apps.recommendation.caches import _user_profile_version

        user, profile, _ = _make_user_with_personality('optuser7', discovery_opt_in=True)
        cache.delete(f'user_profile_version:{user.id}')
        assert _user_profile_version(user.id) == 0

        client = _auth_client(user)
        resp = client.patch('/api/v1/personality/me/', {'discovery_opt_in': True}, format='json')
        assert resp.status_code == 200
        assert _user_profile_version(user.id) == 0


# ---------------------------------------------------------------------------
# TestProfilePersonalityGating
# ---------------------------------------------------------------------------

class TestProfilePersonalityGating:

    @pytest.mark.django_db
    def test_opted_out_hidden_from_other_user(self):
        target, _, _ = _make_user_with_personality('target_out', discovery_opt_in=False)
        viewer, _, _ = _make_user_with_personality('viewer1', discovery_opt_in=True)
        client = _auth_client(viewer)
        resp = client.get(f'/api/v1/users/{target.id}/')
        assert resp.status_code == 200
        assert resp.json()['personality'] is None

    @pytest.mark.django_db
    def test_opted_out_hidden_from_anonymous(self):
        target, _, _ = _make_user_with_personality('target_out2', discovery_opt_in=False)
        client = APIClient()
        resp = client.get(f'/api/v1/users/{target.id}/')
        assert resp.status_code == 200
        assert resp.json()['personality'] is None

    @pytest.mark.django_db
    def test_opted_out_still_visible_to_owner(self):
        target, _, _ = _make_user_with_personality('target_out3', discovery_opt_in=False)
        client = _auth_client(target)
        resp = client.get(f'/api/v1/users/{target.id}/')
        assert resp.status_code == 200
        assert resp.json()['personality'] is not None
        assert resp.json()['personality']['type_code'] == 'CLOT'

    @pytest.mark.django_db
    def test_opted_in_visible_to_everyone(self):
        target, _, _ = _make_user_with_personality('target_in', discovery_opt_in=True)
        viewer, _, _ = _make_user_with_personality('viewer2', discovery_opt_in=True)

        client_anon = APIClient()
        resp = client_anon.get(f'/api/v1/users/{target.id}/')
        assert resp.json()['personality'] is not None

        client_viewer = _auth_client(viewer)
        resp = client_viewer.get(f'/api/v1/users/{target.id}/')
        assert resp.json()['personality'] is not None


# ---------------------------------------------------------------------------
# TestFeedIntegration
# ---------------------------------------------------------------------------

class TestFeedIntegration:

    @pytest.mark.django_db
    def test_opted_out_user_absent_from_feed_pool(self):
        """After PATCH discovery_opt_in=False, the user drops out of the
        PeopleDiscoveryView candidate pool (views_people.py:189 gate)."""
        user, profile, personality = _make_user_with_personality('feeduser1', discovery_opt_in=True)
        Project.objects.create(
            user=profile, name='Test Board', visibility='public',
            report_image='https://example.com/report.png',
        )

        # _feed_candidate_ids() returns PersonalityProfile.user_id values, i.e.
        # UserProfile pks (matching views_people.py's own queryset shape) — NOT
        # Django User ids. Assert against profile.id, not user.id.
        assert profile.id in _feed_candidate_ids()

        client = _auth_client(user)
        resp = client.patch('/api/v1/personality/me/', {'discovery_opt_in': False}, format='json')
        assert resp.status_code == 200

        assert profile.id not in _feed_candidate_ids()
