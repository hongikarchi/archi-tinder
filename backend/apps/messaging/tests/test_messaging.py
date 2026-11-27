"""Tests for apps.messaging (FULL-MESSAGING-1)."""
import pytest

from apps.messaging.models import Block, Conversation, Message, Report
from apps.social.models import UserFollow

from .conftest import client_for, make_user

pytestmark = pytest.mark.django_db


def unread(client):
    return client.get('/api/v1/messages/unread-count/').data['count']


def follow(a, b):
    """a follows b (direct row; the follow API has its own tests in apps/social)."""
    return UserFollow.objects.get_or_create(follower=a[1], following=b[1])[0]


def connect_pair(ca, cb, a, b):
    """a follows b and opens the conversation. Returns the Conversation."""
    follow(a, b)
    r = ca.post('/api/v1/conversations/', {'peer_user_id': b[0].id}, format='json')
    assert r.status_code == 201, r.data
    return Conversation.objects.get(pk=r.data['id'])


# -- Feature flag ------------------------------------------------------------

# Block / Report are reachable with EITHER flag on, so they are not listed here
# (see TestBlockReportFlag); everything below is gated by MESSAGING_ENABLED alone,
# except POST conversations/ which also needs FOLLOW_ENABLED (TestOpenConversation).
ALL_ENDPOINTS = [
    ('get', '/api/v1/conversations/'),
    ('post', '/api/v1/conversations/'),
    ('get', '/api/v1/conversations/1/messages/'),
    ('post', '/api/v1/conversations/1/messages/'),
    ('post', '/api/v1/conversations/1/read/'),
    ('get', '/api/v1/messages/unread-count/'),
]


class TestFeatureFlag:
    def test_default_is_off(self):
        """Settings default (env unset) is OFF — checked in a clean subprocess.

        The subprocess has no `pytest` in sys.modules, so settings.py's guard
        would load backend/.env (a local MESSAGING_ENABLED=true would leak in).
        Stub dotenv.load_dotenv before settings import so only the env passed
        here is seen.
        """
        import os
        import subprocess
        import sys
        env = {k: v for k, v in os.environ.items() if k != 'MESSAGING_ENABLED'}
        script = (
            'import dotenv; dotenv.load_dotenv = lambda *a, **k: False; '
            'from django.conf import settings; print(settings.MESSAGING_ENABLED)'
        )
        out = subprocess.run(
            [sys.executable, '-c', script],
            env=env, capture_output=True, text=True, check=True,
        )
        assert out.stdout.strip().splitlines()[-1] == 'False'

    @pytest.mark.parametrize('method,url', ALL_ENDPOINTS)
    def test_flag_off_all_404(self, settings, ca, method, url):
        settings.MESSAGING_ENABLED = False
        assert getattr(ca, method)(url, {}, format='json').status_code == 404

    def test_flag_off_block_report_404_when_both_off(self, settings, ca):
        settings.MESSAGING_ENABLED = False
        settings.FOLLOW_ENABLED = False
        assert ca.post('/api/v1/users/1/block/').status_code == 404
        assert ca.delete('/api/v1/users/1/block/').status_code == 404
        assert ca.post('/api/v1/reports/', {}, format='json').status_code == 404

    def test_flag_off_404_even_anonymous(self, settings):
        from rest_framework.test import APIClient
        settings.MESSAGING_ENABLED = False
        assert APIClient().get('/api/v1/conversations/').status_code == 404

    def test_me_features_flag(self, settings, ca):
        settings.MESSAGING_ENABLED = False
        settings.FOLLOW_ENABLED = False
        r = ca.get('/api/v1/auth/me/')
        assert r.status_code == 200
        assert r.data['features'] == {'messaging': False, 'follow': False}
        assert 'display_name' in r.data and 'user_id' in r.data
        settings.MESSAGING_ENABLED = True
        assert ca.get('/api/v1/auth/me/').data['features'] == {'messaging': True, 'follow': False}
        settings.FOLLOW_ENABLED = True
        assert ca.get('/api/v1/auth/me/').data['features'] == {'messaging': True, 'follow': True}


# -- Open conversation -------------------------------------------------------

def open_conv(client, peer_user_id):
    return client.post('/api/v1/conversations/', {'peer_user_id': peer_user_id}, format='json')


class TestOpenConversation:
    def test_not_following_403(self, ca, bob):
        r = open_conv(ca, bob[0].id)
        assert r.status_code == 403 and r.data == {'detail': 'not_allowed'}
        assert not Conversation.objects.exists()

    def test_follow_then_201_then_200_same_id(self, ca, alice, bob):
        follow(alice, bob)
        r1 = open_conv(ca, bob[0].id)
        assert r1.status_code == 201
        assert r1.data['closed'] is False
        assert r1.data['other']['user_id'] == bob[0].id
        r2 = open_conv(ca, bob[0].id)
        assert r2.status_code == 200 and r2.data['id'] == r1.data['id']
        assert Conversation.objects.count() == 1

    def test_no_system_message_and_actor_read(self, ca, alice, bob):
        follow(alice, bob)
        r = open_conv(ca, bob[0].id)
        conv = Conversation.objects.get(pk=r.data['id'])
        assert not conv.messages.exists()
        assert conv.last_message_at is None
        assert getattr(conv, conv.last_read_field(alice[1])) is not None
        assert getattr(conv, conv.last_read_field(bob[1])) is None
        assert unread(ca) == 0

    def test_follower_must_be_the_opener(self, cb, alice, bob):
        follow(alice, bob)  # alice follows bob; bob does NOT follow alice
        assert open_conv(cb, alice[0].id).status_code == 403

    def test_blocked_either_direction_403(self, ca, cb, alice, bob):
        follow(alice, bob)
        Block.objects.create(blocker=bob[1], blocked=alice[1])
        assert open_conv(ca, bob[0].id).status_code == 403
        Block.objects.all().delete()
        follow(bob, alice)
        Block.objects.create(blocker=alice[1], blocked=bob[1])
        r = open_conv(ca, bob[0].id)
        assert r.status_code == 403 and r.data == {'detail': 'not_allowed'}

    def test_closed_conversation_reopened_after_unblock_and_follow(self, ca, cb, alice, bob):
        conv = connect_pair(ca, cb, alice, bob)
        assert cb.post(f'/api/v1/users/{alice[0].id}/block/').status_code == 201
        conv.refresh_from_db()
        assert conv.closed_at is not None
        assert not UserFollow.objects.exists()  # block removed the follow edges
        assert open_conv(ca, bob[0].id).status_code == 403
        cb.delete(f'/api/v1/users/{alice[0].id}/block/')
        assert open_conv(ca, bob[0].id).status_code == 403  # unblock does not restore follows
        follow(alice, bob)
        r = open_conv(ca, bob[0].id)
        assert r.status_code == 200 and r.data['id'] == conv.id and r.data['closed'] is False
        conv.refresh_from_db()
        assert conv.closed_at is None

    def test_peer_who_does_not_follow_can_reply(self, ca, cb, alice, bob):
        conv = connect_pair(ca, cb, alice, bob)  # only alice follows bob
        url = f'/api/v1/conversations/{conv.id}/messages/'
        assert ca.post(url, {'body': 'hello'}, format='json').status_code == 201
        assert not UserFollow.objects.filter(follower=bob[1]).exists()
        r = cb.post(url, {'body': 'hi back'}, format='json')
        assert r.status_code == 201

    def test_follow_flag_off_404(self, settings, ca, alice, bob):
        follow(alice, bob)
        settings.FOLLOW_ENABLED = False
        assert open_conv(ca, bob[0].id).status_code == 404
        assert not Conversation.objects.exists()

    def test_messaging_flag_off_404(self, settings, ca, alice, bob):
        follow(alice, bob)
        settings.MESSAGING_ENABLED = False
        assert open_conv(ca, bob[0].id).status_code == 404

    def test_get_list_needs_only_messaging_flag(self, settings, ca):
        settings.FOLLOW_ENABLED = False
        assert ca.get('/api/v1/conversations/').status_code == 200

    def test_anonymous_follow_off_404_on_on_401(self, settings):
        from rest_framework.test import APIClient
        settings.FOLLOW_ENABLED = False
        assert APIClient().post('/api/v1/conversations/', {}, format='json').status_code == 404
        settings.FOLLOW_ENABLED = True
        assert APIClient().post('/api/v1/conversations/', {}, format='json').status_code == 401

    def test_guest_requester_verify_required(self, db, bob):
        g = make_user('guesty3', guest=True)
        r = open_conv(client_for(g[0]), bob[0].id)
        assert r.status_code == 403 and r.data['detail'] == 'verify_required'

    def test_validation(self, ca, alice):
        assert open_conv(ca, alice[0].id).status_code == 400  # self
        assert open_conv(ca, 2**31).status_code == 400  # out of int4 range
        assert open_conv(ca, 0).status_code == 400
        assert open_conv(ca, -3).status_code == 400
        assert open_conv(ca, int(HUGE)).status_code == 400
        assert ca.post('/api/v1/conversations/', {}, format='json').status_code == 400
        assert ca.post('/api/v1/conversations/', {'peer_user_id': 'x'}, format='json').status_code == 400
        assert open_conv(ca, 999999).status_code == 404  # in range, no such user

    def test_open_throttle_60_per_day(self, ca, alice):
        from apps.messaging.throttling import ConversationOpenThrottle
        assert ConversationOpenThrottle.rate == '60/day'
        codes = [open_conv(ca, 999999).status_code for _ in range(61)]
        assert codes[:60] == [404] * 60 and codes[60] == 429
        # GET keeps its own (read) throttle
        assert ca.get('/api/v1/conversations/').status_code == 200

    def test_conversation_list_after_open(self, ca, cb, alice, bob):
        conv = connect_pair(ca, cb, alice, bob)
        rows = ca.get('/api/v1/conversations/').data['results']
        assert [r['id'] for r in rows] == [conv.id]
        assert rows[0]['other']['user_id'] == bob[0].id
        assert rows[0]['last_message'] is None and rows[0]['closed'] is False
        assert [r['id'] for r in cb.get('/api/v1/conversations/').data['results']] == [conv.id]


class TestUnread:
    def test_unread_counts_messages_only(self, ca, cb, alice, bob):
        conv = connect_pair(ca, cb, alice, bob)
        assert unread(ca) == 0 and unread(cb) == 0
        ca.post(f'/api/v1/conversations/{conv.id}/messages/', {'body': 'yo'}, format='json')
        assert unread(ca) == 0
        assert unread(cb) == 1
        cb.post(f'/api/v1/conversations/{conv.id}/read/')
        assert unread(cb) == 0

    def test_legacy_system_rows_do_not_count(self, ca, cb, alice, bob):
        # Old 'connected' system rows are hidden in the UI, so they must not
        # light the TabBar dot or the inbox badge (#506).
        conv = connect_pair(ca, cb, alice, bob)
        Message.objects.create(conversation=conv, sender=None, kind=Message.KIND_SYSTEM, body='connected')
        assert unread(ca) == 0 and unread(cb) == 0
        assert cb.get('/api/v1/conversations/').data['results'][0]['unread_count'] == 0
        ca.post(f'/api/v1/conversations/{conv.id}/messages/', {'body': 'yo'}, format='json')
        assert unread(cb) == 1
        assert cb.get('/api/v1/conversations/').data['results'][0]['unread_count'] == 1

    def test_message_from_deleted_author_still_counts(self, ca, cb, alice, bob):
        conv = connect_pair(ca, cb, alice, bob)
        Message.objects.create(conversation=conv, sender=None, kind=Message.KIND_USER, body='hi')
        assert unread(cb) == 1 and unread(ca) == 1

    def test_follow_does_not_count(self, ca, cb, alice, bob):
        follow(alice, bob)
        assert unread(cb) == 0
        assert set(cb.get('/api/v1/messages/unread-count/').data) == {'count'}


class TestBlockReportFlag:
    @pytest.mark.parametrize('messaging,follow_on,expected_404', [
        (True, False, False), (False, True, False), (True, True, False), (False, False, True),
    ])
    def test_block_report_reachable_when_either_flag_on(
        self, settings, ca, bob, messaging, follow_on, expected_404,
    ):
        settings.MESSAGING_ENABLED = messaging
        settings.FOLLOW_ENABLED = follow_on
        r_block = ca.post(f'/api/v1/users/{bob[0].id}/block/')
        r_report = ca.post('/api/v1/reports/', {
            'target_type': 'user', 'target_id': str(bob[0].id)}, format='json')
        if expected_404:
            assert r_block.status_code == 404 and r_report.status_code == 404
        else:
            assert r_block.status_code == 201 and r_report.status_code == 201

    def test_other_messaging_views_stay_messaging_gated(self, settings, ca):
        settings.MESSAGING_ENABLED = False
        settings.FOLLOW_ENABLED = True
        assert ca.get('/api/v1/conversations/').status_code == 404
        assert ca.get('/api/v1/messages/unread-count/').status_code == 404
        assert ca.post('/api/v1/conversations/1/messages/', {'body': 'x'}, format='json').status_code == 404


# -- Messages ----------------------------------------------------------------

class TestMessages:
    def test_send_and_incremental(self, ca, cb, alice, bob):
        conv = connect_pair(ca, cb, alice, bob)
        url = f'/api/v1/conversations/{conv.id}/messages/'
        r = cb.post(url, {'body': '  hello  '}, format='json')
        assert r.status_code == 201 and r.data['body'] == 'hello' and r.data['is_mine'] is True
        first_id = r.data['id']
        cb.post(url, {'body': 'second'}, format='json')

        full = ca.get(url).data['results']
        assert [m['kind'] for m in full] == ['user', 'user']
        assert [m['id'] for m in full] == sorted(m['id'] for m in full)
        inc = ca.get(url + f'?after={first_id}').data['results']
        assert [m['body'] for m in inc] == ['second']
        assert ca.get(url + '?limit=2').data['results'][-1]['body'] == 'second'
        assert len(ca.get(url + '?limit=2').data['results']) == 2
        assert ca.get(url + '?after=x').status_code == 400

    def test_send_advances_own_read_and_unread_for_other(self, ca, cb, alice, bob):
        conv = connect_pair(ca, cb, alice, bob)
        ca.post(f'/api/v1/conversations/{conv.id}/messages/', {'body': 'yo'}, format='json')
        assert unread(ca) == 0  # own messages never count as unread
        assert unread(cb) == 1
        conv.refresh_from_db()
        assert conv.last_message_at is not None

    def test_body_validation(self, ca, cb, alice, bob):
        conv = connect_pair(ca, cb, alice, bob)
        url = f'/api/v1/conversations/{conv.id}/messages/'
        assert ca.post(url, {'body': '   '}, format='json').status_code == 400
        assert ca.post(url, {'body': ''}, format='json').status_code == 400
        assert ca.post(url, {'body': 'x' * 1001}, format='json').status_code == 400
        assert ca.post(url, {'body': 'x' * 1000}, format='json').status_code == 201

    def test_non_participant_404(self, ca, cb, cc, alice, bob):
        conv = connect_pair(ca, cb, alice, bob)
        url = f'/api/v1/conversations/{conv.id}/messages/'
        assert cc.get(url).status_code == 404
        assert cc.post(url, {'body': 'x'}, format='json').status_code == 404
        assert cc.post(f'/api/v1/conversations/{conv.id}/read/').status_code == 404
        assert cc.get('/api/v1/conversations/').data['results'] == []

    def test_guest_cannot_send(self, db):
        g = make_user('guesty2', guest=True)
        assert client_for(g[0]).post(
            '/api/v1/conversations/1/messages/', {'body': 'x'}, format='json',
        ).status_code == 403

    def test_throttle(self, ca, cb, alice, bob):
        conv = connect_pair(ca, cb, alice, bob)
        url = f'/api/v1/conversations/{conv.id}/messages/'
        codes = [ca.post(url, {'body': 'm'}, format='json').status_code for _ in range(31)]
        assert codes[:30] == [201] * 30
        assert codes[30] == 429
        # GET is not throttled
        assert ca.get(url).status_code == 200

    def test_report_throttle(self, ca, bob):
        codes = [
            ca.post('/api/v1/reports/', {'target_type': 'user', 'target_id': str(bob[0].id)},
                    format='json').status_code
            for _ in range(11)
        ]
        assert codes[:10] == [201] * 10 and codes[10] == 429


# -- Block -------------------------------------------------------------------

class TestBlock:
    def test_block_closes_conversation_and_rejects_send(self, ca, cb, alice, bob):
        conv = connect_pair(ca, cb, alice, bob)
        r = cb.post(f'/api/v1/users/{alice[0].id}/block/')
        assert r.status_code == 201
        conv.refresh_from_db()
        assert conv.closed_at is not None
        url = f'/api/v1/conversations/{conv.id}/messages/'
        assert ca.post(url, {'body': 'x'}, format='json').status_code == 403
        assert cb.post(url, {'body': 'x'}, format='json').status_code == 403
        # history still readable
        assert ca.get(url).status_code == 200
        # closed conversation does not keep the unread dot on
        assert unread(ca) == 0

    def test_unblock_keeps_closed(self, ca, cb, alice, bob):
        conv = connect_pair(ca, cb, alice, bob)
        cb.post(f'/api/v1/users/{alice[0].id}/block/')
        assert cb.delete(f'/api/v1/users/{alice[0].id}/block/').status_code == 204
        assert not Block.objects.exists()
        conv.refresh_from_db()
        assert conv.closed_at is not None
        assert ca.post(f'/api/v1/conversations/{conv.id}/messages/', {'body': 'x'},
                       format='json').status_code == 403

    def test_block_idempotent_and_self(self, ca, bob, alice):
        assert ca.post(f'/api/v1/users/{bob[0].id}/block/').status_code == 201
        assert ca.post(f'/api/v1/users/{bob[0].id}/block/').status_code == 201
        assert Block.objects.count() == 1
        assert ca.post(f'/api/v1/users/{alice[0].id}/block/').status_code == 400
        assert ca.post('/api/v1/users/999999/block/').status_code == 404

    def test_block_deletes_follows_both_directions(self, ca, cb, cc, alice, bob, carol):
        follow(alice, bob)
        follow(bob, alice)
        follow(alice, carol)
        assert ca.post(f'/api/v1/users/{bob[0].id}/block/').status_code == 201
        assert not UserFollow.objects.filter(follower=alice[1], following=bob[1]).exists()
        assert not UserFollow.objects.filter(follower=bob[1], following=alice[1]).exists()
        assert UserFollow.objects.filter(follower=alice[1], following=carol[1]).exists()
        # unblock does not restore
        ca.delete(f'/api/v1/users/{bob[0].id}/block/')
        assert UserFollow.objects.count() == 1

    def test_block_by_either_side_deletes_follows(self, cb, alice, bob):
        follow(alice, bob)
        assert cb.post(f'/api/v1/users/{alice[0].id}/block/').status_code == 201
        assert not UserFollow.objects.exists()

    def test_reopen_after_unblock_and_refollow(self, ca, cb, alice, bob):
        conv = connect_pair(ca, cb, alice, bob)
        cb.post(f'/api/v1/users/{alice[0].id}/block/')
        cb.delete(f'/api/v1/users/{alice[0].id}/block/')
        follow(alice, bob)
        r = open_conv(ca, bob[0].id)
        assert r.status_code == 200 and r.data['id'] == conv.id
        conv.refresh_from_db()
        assert conv.closed_at is None


class TestPeopleFeedBlock:
    def _feed_ids(self, client):
        r = client.get('/api/v1/people/')
        assert r.status_code == 200, r.data
        return {p['user_id'] for p in r.data['results']}

    def _public_report(self, profile):
        from apps.recommendation.models import Project
        Project.objects.create(
            user=profile, name='p', visibility='public', report_image='abc', report_image_mime='image/png',
        )

    @pytest.mark.parametrize('flag', [True, False])
    def test_block_excludes_both_directions_regardless_of_flag(
        self, settings, ca, cb, cc, alice, bob, carol, flag,
    ):
        for u in (alice, bob, carol):
            self._public_report(u[1])
        assert {bob[0].id, carol[0].id} <= self._feed_ids(ca)
        ca.post(f'/api/v1/users/{bob[0].id}/block/')  # alice blocks bob
        settings.MESSAGING_ENABLED = flag
        assert bob[0].id not in self._feed_ids(ca)
        assert carol[0].id in self._feed_ids(ca)
        assert alice[0].id not in self._feed_ids(cb)  # reverse direction
        assert alice[0].id in self._feed_ids(cc)


# -- Reports -----------------------------------------------------------------

class TestReports:
    def test_report_user(self, ca, bob):
        r = ca.post('/api/v1/reports/', {
            'target_type': 'user', 'target_id': str(bob[0].id), 'reason': 'spam',
        }, format='json')
        assert r.status_code == 201
        assert Report.objects.get().reason == 'spam'

    def test_report_user_self_and_missing(self, ca, alice):
        assert ca.post('/api/v1/reports/', {
            'target_type': 'user', 'target_id': str(alice[0].id)}, format='json').status_code == 400
        assert ca.post('/api/v1/reports/', {
            'target_type': 'user', 'target_id': '999999'}, format='json').status_code == 404

    def test_report_message_participant_only(self, ca, cb, cc, alice, bob):
        conv = connect_pair(ca, cb, alice, bob)
        user_msg = Message.objects.create(
            conversation=conv, sender=alice[1], kind=Message.KIND_USER, body='rude',
        )
        payload = {'target_type': 'message', 'target_id': str(user_msg.id)}
        assert cb.post('/api/v1/reports/', payload, format='json').status_code == 201
        assert cc.post('/api/v1/reports/', payload, format='json').status_code == 404

    def test_report_system_message_rejected(self, ca, cb, alice, bob):
        conv = connect_pair(ca, cb, alice, bob)
        sys_msg = Message.objects.create(
            conversation=conv, sender=None, kind=Message.KIND_SYSTEM,
            system_type=Message.SYSTEM_CONNECTED,
        )
        r = cb.post('/api/v1/reports/', {
            'target_type': 'message', 'target_id': str(sys_msg.id)}, format='json')
        assert r.status_code == 400
        assert not Report.objects.exists()

    def test_invalid_target_type(self, ca):
        assert ca.post('/api/v1/reports/', {
            'target_type': 'bogus', 'target_id': '1'}, format='json').status_code == 400


# -- GET read throttle (#410) -------------------------------------------------

class TestReadThrottle:
    READ_URLS = [
        '/api/v1/conversations/',
        '/api/v1/conversations/1/messages/',
        '/api/v1/messages/unread-count/',
    ]

    @pytest.fixture
    def small_rate(self, monkeypatch):
        from apps.messaging.throttling import MessageReadThrottle
        monkeypatch.setattr(MessageReadThrottle, 'rate', '3/min')

    def test_rate_is_code_pinned_120_per_min(self):
        from apps.messaging.throttling import MessageReadThrottle
        assert MessageReadThrottle.rate == '120/min'

    @pytest.mark.parametrize('url', READ_URLS)
    def test_get_429_after_rate(self, small_rate, ca, url):
        codes = [ca.get(url).status_code for _ in range(4)]
        assert 429 not in codes[:3]
        assert codes[3] == 429

    def test_scope_is_per_user(self, small_rate, ca, cb):
        for _ in range(3):
            assert ca.get('/api/v1/messages/unread-count/').status_code == 200
        assert ca.get('/api/v1/messages/unread-count/').status_code == 429
        assert cb.get('/api/v1/messages/unread-count/').status_code == 200

    def test_writes_not_counted_against_read_throttle(self, small_rate, ca):
        for _ in range(3):
            assert ca.get('/api/v1/messages/unread-count/').status_code == 200
        # Non-GET messaging endpoints keep their own (or no) throttle.
        assert ca.post('/api/v1/conversations/1/read/').status_code == 404

    def test_normal_polling_not_throttled(self, ca):
        codes = [ca.get('/api/v1/messages/unread-count/').status_code for _ in range(30)]
        assert set(codes) == {200}


# -- Oversized integer ids (#411) ----------------------------------------------

HUGE = '99999999999999999999'


class TestOversizedIds:
    def test_id_in_range(self):
        from apps.messaging import services
        assert services.id_in_range(1)
        assert services.id_in_range(services.BIGINT_ID_MAX)
        assert not services.id_in_range(services.BIGINT_ID_MAX + 1)
        assert services.id_in_range(services.AUTH_USER_ID_MAX, services.AUTH_USER_ID_MAX)
        assert not services.id_in_range(services.AUTH_USER_ID_MAX + 1, services.AUTH_USER_ID_MAX)
        assert not services.id_in_range(0)
        assert not services.id_in_range(-5)
        assert not services.id_in_range(True)
        assert not services.id_in_range('1')

    def test_int4_boundary_for_auth_user_id(self, ca):
        from apps.messaging import services
        assert services.get_profile_by_auth_id(services.AUTH_USER_ID_MAX + 1) is None
        # 2**31 - 1 is in range for int4 -> valid lookup (no such user -> 404, not 500).
        assert ca.get(
            f'/api/v1/users/{services.AUTH_USER_ID_MAX}/follow/'
        ).status_code == 404
        assert ca.get(
            f'/api/v1/users/{services.AUTH_USER_ID_MAX + 1}/follow/'
        ).status_code == 404
        assert open_conv(ca, services.AUTH_USER_ID_MAX).status_code == 404
        assert open_conv(ca, services.AUTH_USER_ID_MAX + 1).status_code == 400

    def test_block_404(self, ca):
        assert ca.post(f'/api/v1/users/{HUGE}/block/').status_code == 404
        assert ca.delete(f'/api/v1/users/{HUGE}/block/').status_code == 404

    def test_follow_404(self, ca):
        assert ca.get(f'/api/v1/users/{HUGE}/follow/').status_code == 404
        assert ca.post(f'/api/v1/users/{HUGE}/follow/').status_code == 404
        assert ca.delete(f'/api/v1/users/{HUGE}/follow/').status_code == 404

    @pytest.mark.parametrize('target_type', ['user', 'message', 'profile'])
    def test_report_target_id_400(self, ca, target_type):
        r = ca.post('/api/v1/reports/', {'target_type': target_type, 'target_id': HUGE}, format='json')
        assert r.status_code == 400
        assert not Report.objects.exists()

    def test_report_int4_overflow_user_400_but_message_ok_range(self, ca):
        big = str(2**31)  # > int4, valid int8
        assert ca.post('/api/v1/reports/', {'target_type': 'user', 'target_id': big},
                       format='json').status_code == 400
        # Message pks are int8: in range, just does not exist -> 404.
        assert ca.post('/api/v1/reports/', {'target_type': 'message', 'target_id': big},
                       format='json').status_code == 404

    def test_report_non_ascii_digit_400(self, ca):
        r = ca.post('/api/v1/reports/', {'target_type': 'message', 'target_id': '²'}, format='json')
        assert r.status_code == 400

    @pytest.mark.parametrize('method,path', [
        ('post', '/api/v1/conversations/{id}/read/'),
        ('get', '/api/v1/conversations/{id}/messages/'),
        ('post', '/api/v1/conversations/{id}/messages/'),
    ])
    def test_path_params_404(self, ca, method, path):
        r = getattr(ca, method)(path.format(id=HUGE), {'body': 'x'}, format='json') \
            if method == 'post' else getattr(ca, method)(path.format(id=HUGE))
        assert r.status_code == 404

    def test_after_cursor_oversized_is_empty_not_500(self, ca, alice, bob):
        conv = Conversation.objects.create(
            user_a=min(alice[1], bob[1], key=lambda p: p.pk),
            user_b=max(alice[1], bob[1], key=lambda p: p.pk),
        )
        r = ca.get(f'/api/v1/conversations/{conv.id}/messages/?after={HUGE}')
        assert r.status_code == 200
        assert r.data['results'] == []
