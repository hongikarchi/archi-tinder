"""Tests for apps.messaging (FULL-MESSAGING-1)."""
from datetime import timedelta

import pytest
from django.utils import timezone

from apps.messaging.models import (
    Block, ContactRequest, Conversation, Message, Report,
)
from apps.notifications.models import Notification

from .conftest import client_for, make_user

pytestmark = pytest.mark.django_db


def send(client, target, greeting=None):
    body = {'recipient_id': target[0].id}
    if greeting is not None:
        body['greeting'] = greeting
    return client.post('/api/v1/contact-requests/', body, format='json')


def unread(client):
    return client.get('/api/v1/messages/unread-count/').data['count']


def connect_pair(ca, cb, a, b, greeting='hi'):
    """a requests, b accepts. Returns conversation."""
    assert send(ca, b, greeting).status_code == 201
    cr = ContactRequest.objects.get(sender=a[1], recipient=b[1])
    r = cb.post(f'/api/v1/contact-requests/{cr.id}/accept/')
    assert r.status_code == 200
    return Conversation.objects.get(pk=r.data['conversation_id'])


# -- Feature flag ------------------------------------------------------------

ALL_ENDPOINTS = [
    ('post', '/api/v1/contact-requests/'),
    ('get', '/api/v1/contact-requests/received/'),
    ('get', '/api/v1/contact-requests/status/?user_id=1'),
    ('post', '/api/v1/contact-requests/1/accept/'),
    ('post', '/api/v1/contact-requests/1/ignore/'),
    ('get', '/api/v1/conversations/'),
    ('get', '/api/v1/conversations/1/messages/'),
    ('post', '/api/v1/conversations/1/messages/'),
    ('post', '/api/v1/conversations/1/read/'),
    ('get', '/api/v1/messages/unread-count/'),
    ('post', '/api/v1/users/1/block/'),
    ('delete', '/api/v1/users/1/block/'),
    ('post', '/api/v1/reports/'),
]


class TestFeatureFlag:
    def test_default_is_off(self):
        """Settings default (env unset) is OFF — checked in a clean subprocess."""
        import os
        import subprocess
        import sys
        env = {k: v for k, v in os.environ.items() if k != 'MESSAGING_ENABLED'}
        out = subprocess.run(
            [sys.executable, '-c',
             'import django.conf; from django.conf import settings; print(settings.MESSAGING_ENABLED)'],
            env=env, capture_output=True, text=True, check=True,
        )
        assert out.stdout.strip().splitlines()[-1] == 'False'

    @pytest.mark.parametrize('method,url', ALL_ENDPOINTS)
    def test_flag_off_all_404(self, settings, ca, method, url):
        settings.MESSAGING_ENABLED = False
        assert getattr(ca, method)(url, {}, format='json').status_code == 404

    def test_flag_off_404_even_anonymous(self, settings):
        from rest_framework.test import APIClient
        settings.MESSAGING_ENABLED = False
        assert APIClient().get('/api/v1/conversations/').status_code == 404

    def test_me_features_flag(self, settings, ca):
        settings.MESSAGING_ENABLED = False
        r = ca.get('/api/v1/auth/me/')
        assert r.status_code == 200
        assert r.data['features'] == {'messaging': False}
        assert 'display_name' in r.data and 'user_id' in r.data
        settings.MESSAGING_ENABLED = True
        assert ca.get('/api/v1/auth/me/').data['features'] == {'messaging': True}


# -- Requests ----------------------------------------------------------------

class TestSendRequest:
    def test_send_and_received_list(self, ca, cb, alice, bob):
        r = send(ca, bob, 'hello')
        assert r.status_code == 201 and r.data == {'status': 'sent'}
        recv = cb.get('/api/v1/contact-requests/received/').data['results']
        assert len(recv) == 1
        assert recv[0]['greeting'] == 'hello'
        assert recv[0]['sender']['user_id'] == alice[0].id
        assert ca.get('/api/v1/contact-requests/received/').data['results'] == []

    def test_self_rejected(self, ca, alice):
        assert send(ca, alice).status_code == 400

    def test_guest_sender_rejected(self, db, bob):
        g = make_user('guesty', guest=True)
        assert send(client_for(g[0]), bob).status_code == 403

    def test_d11_no_personality(self, ca):
        t = make_user('nopers', personality=False)
        assert send(ca, t).status_code == 400

    def test_d11_opt_out(self, ca):
        t = make_user('hidden', opt_in=False)
        assert send(ca, t).status_code == 400

    def test_unknown_recipient(self, ca):
        r = ca.post('/api/v1/contact-requests/', {'recipient_id': 999999}, format='json')
        assert r.status_code == 400

    def test_greeting_too_long(self, ca, bob):
        assert send(ca, bob, 'x' * 101).status_code == 400

    def test_duplicate_pending_is_silent(self, ca, bob, alice):
        assert send(ca, bob).data == {'status': 'sent'}
        assert send(ca, bob).data == {'status': 'sent'}
        assert ContactRequest.objects.filter(sender=alice[1]).count() == 1

    def test_blocked_either_direction(self, ca, cb, alice, bob):
        cb.post(f'/api/v1/users/{alice[0].id}/block/')
        assert send(ca, bob).status_code == 400  # blocked by recipient
        cb.delete(f'/api/v1/users/{alice[0].id}/block/')
        ca.post(f'/api/v1/users/{bob[0].id}/block/')
        assert send(ca, bob).status_code == 400  # blocker themselves

    def test_no_notification_rows(self, ca, cb, alice, bob):
        connect_pair(ca, cb, alice, bob)
        assert Notification.objects.count() == 0


class TestIgnoreAndCooldown:
    def test_ignore_then_cooldown_silent(self, ca, cb, alice, bob):
        send(ca, bob)
        cr = ContactRequest.objects.get()
        assert cb.post(f'/api/v1/contact-requests/{cr.id}/ignore/').status_code == 200
        cr.refresh_from_db()
        assert cr.status == 'ignored'
        assert cb.get('/api/v1/contact-requests/received/').data['results'] == []
        # re-request: identical success shape, no new row
        r = send(ca, bob)
        assert r.status_code == 201 and r.data == {'status': 'sent'}
        assert ContactRequest.objects.count() == 1
        st = ca.get(f'/api/v1/contact-requests/status/?user_id={bob[0].id}').data
        assert st['state'] == 'sent'

    def test_cooldown_expires_after_30_days(self, ca, cb, alice, bob):
        send(ca, bob)
        cr = ContactRequest.objects.get()
        cb.post(f'/api/v1/contact-requests/{cr.id}/ignore/')
        ContactRequest.objects.filter(pk=cr.pk).update(
            responded_at=timezone.now() - timedelta(days=31))
        st = ca.get(f'/api/v1/contact-requests/status/?user_id={bob[0].id}').data
        assert st['state'] == 'none'
        send(ca, bob)
        assert ContactRequest.objects.filter(status='pending').count() == 1

    def test_only_recipient_can_respond(self, ca, cb, cc, alice, bob):
        send(ca, bob)
        cr = ContactRequest.objects.get()
        assert cc.post(f'/api/v1/contact-requests/{cr.id}/accept/').status_code == 404
        assert ca.post(f'/api/v1/contact-requests/{cr.id}/ignore/').status_code == 404
        cb.post(f'/api/v1/contact-requests/{cr.id}/ignore/')
        assert cb.post(f'/api/v1/contact-requests/{cr.id}/accept/').status_code == 409


class TestStatus:
    def test_transitions(self, ca, cb, alice, bob):
        url = f'/api/v1/contact-requests/status/?user_id={bob[0].id}'
        assert ca.get(url).data == {'state': 'none', 'can_request': True}
        send(ca, bob)
        assert ca.get(url).data['state'] == 'sent'
        cr = ContactRequest.objects.get()
        cb.post(f'/api/v1/contact-requests/{cr.id}/accept/')
        assert ca.get(url).data['state'] == 'connected'
        assert cb.get(f'/api/v1/contact-requests/status/?user_id={alice[0].id}').data['state'] == 'connected'

    def test_can_request_false_cases(self, ca, alice, bob):
        assert ca.get(f'/api/v1/contact-requests/status/?user_id={alice[0].id}').data['can_request'] is False
        t = make_user('optout', opt_in=False)
        assert ca.get(f'/api/v1/contact-requests/status/?user_id={t[0].id}').data['can_request'] is False
        ca.post(f'/api/v1/users/{bob[0].id}/block/')
        assert ca.get(f'/api/v1/contact-requests/status/?user_id={bob[0].id}').data['can_request'] is False

    def test_bad_param(self, ca):
        assert ca.get('/api/v1/contact-requests/status/').status_code == 400


# -- Accept / unread ---------------------------------------------------------

class TestAccept:
    def test_accept_creates_conversation_greeting_and_system(self, ca, cb, alice, bob):
        conv = connect_pair(ca, cb, alice, bob, greeting='nice taste')
        msgs = list(conv.messages.order_by('id'))
        assert [m.kind for m in msgs] == ['user', 'system']
        assert msgs[0].sender_id == alice[1].pk and msgs[0].body == 'nice taste'
        assert msgs[1].sender_id is None
        assert msgs[1].system_type == 'connected' and msgs[1].body == ''
        assert conv.user_a_id < conv.user_b_id

    def test_unread_requester_1_acceptor_0(self, ca, cb, alice, bob):
        send(ca, bob, 'hi')
        assert unread(cb) == 1  # pending request
        assert unread(ca) == 0
        cr = ContactRequest.objects.get()
        cb.post(f'/api/v1/contact-requests/{cr.id}/accept/')
        assert unread(ca) == 1  # system 'connected' only; own greeting excluded
        assert unread(cb) == 0

    def test_unread_without_greeting(self, ca, cb, alice, bob):
        connect_pair(ca, cb, alice, bob, greeting='')
        assert Message.objects.count() == 1
        assert unread(ca) == 1
        assert unread(cb) == 0

    def test_read_clears_unread(self, ca, cb, alice, bob):
        conv = connect_pair(ca, cb, alice, bob)
        assert unread(ca) == 1
        assert ca.post(f'/api/v1/conversations/{conv.id}/read/').status_code == 200
        assert unread(ca) == 0

    def test_conversation_list(self, ca, cb, alice, bob):
        conv = connect_pair(ca, cb, alice, bob)
        res = ca.get('/api/v1/conversations/').data['results']
        assert len(res) == 1
        item = res[0]
        assert item['id'] == conv.id
        assert item['other']['user_id'] == bob[0].id
        assert item['unread_count'] == 1
        assert item['last_message']['kind'] == 'system'
        assert item['last_message']['system_type'] == 'connected'
        assert cb.get('/api/v1/conversations/').data['results'][0]['unread_count'] == 0


class TestMutual:
    def test_mutual_auto_accept(self, ca, cb, alice, bob):
        send(ca, bob, 'from alice')
        r = send(cb, alice, 'from bob')
        assert r.status_code == 201
        assert r.data['status'] == 'connected'
        conv = Conversation.objects.get(pk=r.data['conversation_id'])
        msgs = list(conv.messages.order_by('id'))
        assert [(m.kind, m.body) for m in msgs] == [
            ('user', 'from alice'), ('user', 'from bob'), ('system', ''),
        ]
        assert msgs[0].sender_id == alice[1].pk and msgs[1].sender_id == bob[1].pk
        assert msgs[0].created_at <= msgs[1].created_at <= msgs[2].created_at
        assert not ContactRequest.objects.filter(status='pending').exists()
        # earlier requester (alice): system message unread; actor (bob): 0
        assert unread(ca) == 1
        assert unread(cb) == 0

    def test_mutual_without_greetings(self, ca, cb, alice, bob):
        send(ca, bob)
        send(cb, alice)
        assert unread(ca) == 1
        assert unread(cb) == 0

    def test_race_reverse_pending_swept_on_accept(self, ca, cb, alice, bob):
        r1 = ContactRequest.objects.create(sender=alice[1], recipient=bob[1], greeting='a')
        r2 = ContactRequest.objects.create(sender=bob[1], recipient=alice[1], greeting='b')
        res = cb.post(f'/api/v1/contact-requests/{r1.id}/accept/')
        assert res.status_code == 200
        r2.refresh_from_db()
        assert r2.status == ContactRequest.STATUS_ACCEPTED and r2.responded_at is not None
        assert ca.get('/api/v1/contact-requests/received/').data['results'] == []
        assert not ContactRequest.objects.filter(status='pending').exists()

    def test_connect_idempotent_on_open_conversation(self, ca, cb, alice, bob):
        from apps.messaging import services
        conv = connect_pair(ca, cb, alice, bob)
        cr = ContactRequest.objects.get(sender=alice[1], recipient=bob[1])
        services.connect([cr], actor=bob[1])
        assert conv.messages.filter(kind='system', system_type='connected').count() == 1
        assert conv.messages.count() == 2
        assert unread(ca) == 1
        assert unread(cb) == 0


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
        assert [m['kind'] for m in full][:2] == ['user', 'system']
        assert [m['id'] for m in full] == sorted(m['id'] for m in full)
        inc = ca.get(url + f'?after={first_id}').data['results']
        assert [m['body'] for m in inc] == ['second']
        assert ca.get(url + '?limit=2').data['results'][-1]['body'] == 'second'
        assert len(ca.get(url + '?limit=2').data['results']) == 2
        assert ca.get(url + '?after=x').status_code == 400

    def test_send_advances_own_read_and_unread_for_other(self, ca, cb, alice, bob):
        conv = connect_pair(ca, cb, alice, bob)
        ca.post(f'/api/v1/conversations/{conv.id}/messages/', {'body': 'yo'}, format='json')
        assert unread(ca) == 0  # own send advanced last_read past the system message
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

    def test_contact_request_throttle(self, ca, alice):
        codes = []
        for i in range(21):
            t = make_user(f'target{i}')
            codes.append(send(ca, t).status_code)
        assert codes[:20] == [201] * 20 and codes[20] == 429

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

    def test_blocked_pending_request_hidden(self, ca, cb, alice, bob):
        send(ca, bob)
        assert unread(cb) == 1
        cb.post(f'/api/v1/users/{alice[0].id}/block/')
        assert cb.get('/api/v1/contact-requests/received/').data['results'] == []
        assert unread(cb) == 0
        cr = ContactRequest.objects.get()
        assert cb.post(f'/api/v1/contact-requests/{cr.id}/accept/').status_code == 400

    def test_reconnect_after_unblock_reopens(self, ca, cb, alice, bob):
        conv = connect_pair(ca, cb, alice, bob)
        cb.post(f'/api/v1/users/{alice[0].id}/block/')
        cb.delete(f'/api/v1/users/{alice[0].id}/block/')
        assert send(ca, bob).status_code == 201
        cr = ContactRequest.objects.get(status='pending')
        r = cb.post(f'/api/v1/contact-requests/{cr.id}/accept/')
        assert r.data['conversation_id'] == conv.id
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
        conv = connect_pair(ca, cb, alice, bob, greeting='rude')
        user_msg = conv.messages.filter(kind='user').get()
        payload = {'target_type': 'message', 'target_id': str(user_msg.id)}
        assert cb.post('/api/v1/reports/', payload, format='json').status_code == 201
        assert cc.post('/api/v1/reports/', payload, format='json').status_code == 404

    def test_report_system_message_rejected(self, ca, cb, alice, bob):
        conv = connect_pair(ca, cb, alice, bob)
        sys_msg = conv.messages.filter(kind='system').get()
        r = cb.post('/api/v1/reports/', {
            'target_type': 'message', 'target_id': str(sys_msg.id)}, format='json')
        assert r.status_code == 400
        assert not Report.objects.exists()

    def test_invalid_target_type(self, ca):
        assert ca.post('/api/v1/reports/', {
            'target_type': 'bogus', 'target_id': '1'}, format='json').status_code == 400
