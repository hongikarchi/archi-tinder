"""Tests for the one-way user follow (SNS-FOLLOW-1)."""
import pytest
from django.contrib.auth.models import User
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from apps.accounts.models import PersonalityProfile, UserProfile
from apps.messaging.models import Block
from apps.social import services
from apps.social.models import UserFollow

pytestmark = pytest.mark.django_db


def make_user(username, personality=True, opt_in=True, guest=False):
    user = User.objects.create_user(
        username=username, email=f'{username}@example.com', password='testpass123',
    )
    profile = UserProfile.objects.create(
        user=user, display_name=username.capitalize(), is_guest=guest,
    )
    if personality:
        PersonalityProfile.objects.create(
            user=profile, axis_1=0.1, axis_2=0.2, axis_3=0.3, axis_4=0.4, axis_5=0.5,
            type_code='CLON', discovery_opt_in=opt_in,
        )
    return user, profile


def client_for(user):
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f'Bearer {RefreshToken.for_user(user).access_token}')
    return client


def url(target):
    return f'/api/v1/users/{target[0].id}/follow/'


@pytest.fixture(autouse=True)
def flags(settings):
    settings.FOLLOW_ENABLED = True
    settings.MESSAGING_ENABLED = False
    from django.core.cache import cache
    cache.clear()
    yield
    cache.clear()


@pytest.fixture
def alice():
    return make_user('alice')


@pytest.fixture
def bob():
    return make_user('bob')


@pytest.fixture
def ca(alice):
    return client_for(alice[0])


@pytest.fixture
def cb(bob):
    return client_for(bob[0])


class TestFlag:
    @pytest.mark.parametrize('method', ['get', 'post', 'delete'])
    def test_flag_off_404(self, settings, ca, bob, method):
        settings.FOLLOW_ENABLED = False
        assert getattr(ca, method)(url(bob)).status_code == 404

    def test_flag_off_404_even_anonymous(self, settings, bob):
        settings.FOLLOW_ENABLED = False
        assert APIClient().get(url(bob)).status_code == 404

    def test_flag_on_anonymous_401(self, bob):
        assert APIClient().get(url(bob)).status_code == 401

    def test_default_is_off(self):
        import os
        import subprocess
        import sys
        env = {k: v for k, v in os.environ.items() if k != 'FOLLOW_ENABLED'}
        script = (
            'import dotenv; dotenv.load_dotenv = lambda *a, **k: False; '
            'from django.conf import settings; print(settings.FOLLOW_ENABLED)'
        )
        out = subprocess.run(
            [sys.executable, '-c', script], env=env, capture_output=True, text=True, check=True,
        )
        assert out.stdout.strip().splitlines()[-1] == 'False'

    def test_independent_of_messaging_flag(self, settings, ca, bob):
        settings.MESSAGING_ENABLED = True
        settings.FOLLOW_ENABLED = False
        assert ca.get(url(bob)).status_code == 404


class TestStatus:
    def test_defaults(self, ca, bob):
        r = ca.get(url(bob))
        assert r.status_code == 200
        assert r.data == {
            'is_following': False, 'is_followed_by': False,
            'can_follow': True, 'blocked_by_me': False,
        }

    def test_unassessed_target_can_be_followed(self, ca):
        t = make_user('nopers', personality=False)
        assert ca.get(url(t)).data['can_follow'] is True
        assert ca.post(url(t)).status_code == 201

    def test_opt_out_target_cannot_no_reason(self, ca):
        t = make_user('optout', opt_in=False)
        r = ca.get(url(t))
        assert r.data['can_follow'] is False and 'reason' not in r.data

    def test_guest_target_cannot_no_reason(self, ca):
        t = make_user('guestt', guest=True)
        r = ca.get(url(t))
        assert r.data['can_follow'] is False and 'reason' not in r.data

    def test_self(self, ca, alice):
        r = ca.get(url(alice))
        assert r.data == {
            'is_following': False, 'is_followed_by': False,
            'can_follow': False, 'blocked_by_me': False,
        }

    def test_is_followed_by(self, ca, alice, bob):
        UserFollow.objects.create(follower=bob[1], following=alice[1])
        r = ca.get(url(bob))
        assert r.data['is_followed_by'] is True and r.data['is_following'] is False

    def test_blocked_by_me_true_only_for_my_block(self, ca, alice, bob):
        Block.objects.create(blocker=alice[1], blocked=bob[1])
        r = ca.get(url(bob))
        assert r.data['blocked_by_me'] is True and r.data['can_follow'] is False
        assert 'reason' not in r.data

    def test_never_reveals_target_blocked_me(self, ca, alice, bob):
        Block.objects.create(blocker=bob[1], blocked=alice[1])
        r = ca.get(url(bob))
        assert r.status_code == 200
        assert r.data == {
            'is_following': False, 'is_followed_by': False,
            'can_follow': False, 'blocked_by_me': False,
        }

    def test_target_blocked_me_indistinguishable_from_optout(self, ca, alice, bob):
        Block.objects.create(blocker=bob[1], blocked=alice[1])
        blocked_body = ca.get(url(bob)).data
        optout = make_user('optout2', opt_in=False)
        assert ca.get(url(optout)).data == blocked_body

    def test_guest_requester_reason_verify_required(self, bob):
        g = make_user('guesty', guest=True)
        r = client_for(g[0]).get(url(bob))
        assert r.status_code == 200
        assert r.data['can_follow'] is False and r.data['reason'] == 'verify_required'

    def test_unknown_and_out_of_range_404(self, ca):
        assert ca.get('/api/v1/users/999999/follow/').status_code == 404
        assert ca.get(f'/api/v1/users/{2**31}/follow/').status_code == 404
        assert ca.get('/api/v1/users/99999999999999999999/follow/').status_code == 404


class TestFollow:
    def test_follow_201_then_200_duplicate(self, ca, alice, bob):
        r = ca.post(url(bob))
        assert r.status_code == 201
        assert r.data['is_following'] is True and r.data['can_follow'] is True
        r2 = ca.post(url(bob))
        assert r2.status_code == 200 and r2.data['is_following'] is True
        assert UserFollow.objects.count() == 1

    def test_self_unavailable(self, ca, alice):
        r = ca.post(url(alice))
        assert r.status_code == 400 and r.data == {'detail': 'unavailable'}

    def test_unavailable_bodies_identical(self, ca, alice, bob):
        optout = make_user('optout3', opt_in=False)
        guest = make_user('guestt2', guest=True)
        blocked_me = make_user('blockedme')
        Block.objects.create(blocker=blocked_me[1], blocked=alice[1])
        blocked_by_me = make_user('byme')
        Block.objects.create(blocker=alice[1], blocked=blocked_by_me[1])
        bodies = []
        for t in (alice, optout, guest, blocked_me, blocked_by_me):
            r = ca.post(url(t))
            assert r.status_code == 400
            bodies.append(r.data)
        assert all(b == {'detail': 'unavailable'} for b in bodies)
        assert not UserFollow.objects.exists()

    def test_guest_requester_verify_required_on_write(self, bob):
        g = make_user('guesty2', guest=True)
        c = client_for(g[0])
        for method in ('post', 'delete'):
            r = getattr(c, method)(url(bob))
            assert r.status_code == 403 and r.data['detail'] == 'verify_required'
        assert not UserFollow.objects.exists()

    def test_existing_follow_survives_optout(self, ca, alice, bob):
        assert ca.post(url(bob)).status_code == 201
        PersonalityProfile.objects.filter(user=bob[1]).update(discovery_opt_in=False)
        r = ca.get(url(bob))
        assert r.data['is_following'] is True and r.data['can_follow'] is False
        assert 'reason' not in r.data
        r2 = ca.post(url(bob))
        assert r2.status_code == 200 and r2.data['is_following'] is True

    def test_existing_follow_survives_target_becoming_guest(self, ca, bob):
        ca.post(url(bob))
        UserProfile.objects.filter(pk=bob[1].pk).update(is_guest=True)
        assert ca.post(url(bob)).status_code == 200

    def test_new_follow_blocked_after_optout(self, ca, bob):
        PersonalityProfile.objects.filter(user=bob[1]).update(discovery_opt_in=False)
        assert ca.post(url(bob)).status_code == 400

    def test_delete_204_twice(self, ca, bob):
        ca.post(url(bob))
        assert ca.delete(url(bob)).status_code == 204
        assert not UserFollow.objects.exists()
        assert ca.delete(url(bob)).status_code == 204

    def test_unfollow_allowed_when_blocked(self, ca, alice, bob):
        ca.post(url(bob))
        Block.objects.create(blocker=bob[1], blocked=alice[1])
        assert ca.delete(url(bob)).status_code == 204

    def test_delete_self_and_unknown(self, ca, alice):
        assert ca.delete(url(alice)).status_code == 204
        assert ca.delete('/api/v1/users/999999/follow/').status_code == 404

    def test_throttle_scope_and_rate(self, ca, bob):
        from apps.social.throttling import FollowWriteThrottle
        assert FollowWriteThrottle.scope == 'follow' and FollowWriteThrottle.rate == '200/day'
        FollowWriteThrottle.rate = '3/day'
        try:
            from django.core.cache import cache
            cache.clear()
            codes = [ca.delete(url(bob)).status_code for _ in range(4)]
            assert codes == [204, 204, 204, 429]
            assert ca.get(url(bob)).status_code == 200  # GET not throttled
        finally:
            FollowWriteThrottle.rate = '200/day'

    def test_model_constraints(self, alice, bob):
        from django.db import IntegrityError, transaction
        UserFollow.objects.create(follower=alice[1], following=bob[1])
        with pytest.raises(IntegrityError), transaction.atomic():
            UserFollow.objects.create(follower=alice[1], following=bob[1])
        with pytest.raises(IntegrityError), transaction.atomic():
            UserFollow.objects.create(follower=alice[1], following=alice[1])

    def test_account_deletion_cascades_both_directions(self, alice, bob):
        UserFollow.objects.create(follower=alice[1], following=bob[1])
        UserFollow.objects.create(follower=bob[1], following=alice[1])
        alice[0].delete()
        assert not UserFollow.objects.exists()


class TestBlockInteraction:
    def test_block_deletes_follows_both_ways_with_only_follow_flag(self, settings, ca, alice, bob):
        settings.MESSAGING_ENABLED = False
        UserFollow.objects.create(follower=alice[1], following=bob[1])
        UserFollow.objects.create(follower=bob[1], following=alice[1])
        assert ca.post(f'/api/v1/users/{bob[0].id}/block/').status_code == 201
        assert not UserFollow.objects.exists()
        ca.delete(f'/api/v1/users/{bob[0].id}/block/')
        assert not UserFollow.objects.exists()  # unblock does not restore

    def test_report_reachable_with_only_follow_flag(self, ca, bob):
        r = ca.post('/api/v1/reports/', {
            'target_type': 'user', 'target_id': str(bob[0].id)}, format='json')
        assert r.status_code == 201


class TestServices:
    def test_accepts_new_followers(self):
        assert services.accepts_new_followers(make_user('s1')[1]) is True
        assert services.accepts_new_followers(make_user('s2', personality=False)[1]) is True
        assert services.accepts_new_followers(make_user('s3', opt_in=False)[1]) is False
        assert services.accepts_new_followers(make_user('s4', guest=True)[1]) is False

    def test_counts(self, alice, bob):
        c = make_user('carol')
        UserFollow.objects.create(follower=bob[1], following=alice[1])
        UserFollow.objects.create(follower=c[1], following=alice[1])
        UserFollow.objects.create(follower=alice[1], following=bob[1])
        assert services.follower_count(alice[1]) == 2
        assert services.following_count(alice[1]) == 1
        assert services.is_following(alice[1], bob[1]) is True
        assert services.is_following(alice[1], c[1]) is False

    def test_only_is_guest_account_reads_is_guest(self):
        """`.is_guest` is read in exactly one place in the follow/messaging code."""
        import pathlib
        import re
        apps_dir = pathlib.Path(services.__file__).resolve().parents[1]
        hits = []
        for rel in ('social/services.py', 'social/views_follow.py', 'social/permissions.py',
                    'messaging/services.py', 'messaging/views.py', 'messaging/permissions.py',
                    'messaging/serializers.py'):
            for line in (apps_dir / rel).read_text().splitlines():
                code = line.split('#')[0]
                if re.search(r'\b\w+\.is_guest\b(?!`)', code) and '`' not in code:
                    hits.append((rel, code.strip()))
        assert hits == [('social/services.py', 'return bool(profile.is_guest)')]


class TestProfileCounts:
    def test_detail_includes_counts_and_cache_evicted(self, ca, cb, alice, bob):
        c = client_for(make_user('carol')[0])
        r = c.get(f'/api/v1/users/{bob[0].id}/')
        assert r.status_code == 200
        assert r.data['follower_count'] == 0 and r.data['following_count'] == 0
        ca.post(url(bob))
        r = c.get(f'/api/v1/users/{bob[0].id}/')
        assert r.data['follower_count'] == 1 and r.data['following_count'] == 0
        r = c.get(f'/api/v1/users/{alice[0].id}/')
        assert r.data['follower_count'] == 0 and r.data['following_count'] == 1
        ca.delete(url(bob))
        assert c.get(f'/api/v1/users/{bob[0].id}/').data['follower_count'] == 0

    def test_counts_present_when_flag_off(self, settings, bob):
        settings.FOLLOW_ENABLED = False
        r = APIClient().get(f'/api/v1/users/{bob[0].id}/')
        assert r.status_code == 200
        assert r.data['follower_count'] == 0

    def test_counts_not_in_serializer_for_lists(self):
        from apps.accounts.serializers import UserProfileSerializer
        assert 'follower_count' not in UserProfileSerializer.Meta.fields
