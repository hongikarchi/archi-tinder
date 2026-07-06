"""
test_notifications.py -- NOTIF-INAPP-1 backend test coverage.

Coverage:
  TestReactionEmission      -- creates notification for owner; self-reaction
                                skipped; prefs off skipped; absent prefs emit;
                                unread dedupe on repeated react/unreact/react
  TestSecurityEmission      -- password_changed always emitted regardless of
                                prefs; first device silent, second notifies
  TestNotificationEndpoints -- list self-only + paginated, unread-count,
                                mark-read ids + all, idempotent
  TestNotificationsValidator -- accepts in_app, rejects non-bool / unknown keys
"""
import pytest
from django.utils import timezone

from apps.notifications.models import Notification, KnownDevice
from apps.notifications.services import (
    notify_reaction, notify_security, record_device_and_maybe_notify, hash_user_agent,
)


def _make_project(owner, name='Board'):
    from apps.recommendation.models import Project
    return Project.objects.create(user=owner, name=name, visibility='public')


def _react_url(project_id):
    return f'/api/v1/projects/{project_id}/react/'


# ---------------------------------------------------------------------------
# TestReactionEmission
# ---------------------------------------------------------------------------

class TestReactionEmission:

    @pytest.mark.django_db
    def test_reaction_creates_notification_for_owner(self, user_a, user_b, auth_client_a):
        """POST react by A on B's project creates exactly one unread Notification for B."""
        _, a_profile = user_a
        _, b_profile = user_b
        project = _make_project(b_profile)

        resp = auth_client_a.post(_react_url(project.project_id))
        assert resp.status_code == 201

        notifs = Notification.objects.filter(recipient=b_profile, type='reaction')
        assert notifs.count() == 1
        notif = notifs.first()
        assert notif.actor_id == a_profile.pk
        assert notif.category == 'social'
        assert notif.read_at is None
        assert notif.payload['project_id'] == str(project.project_id)
        assert notif.payload['project_title'] == project.name

    @pytest.mark.django_db
    def test_self_reaction_skipped(self, user_a, auth_client_a):
        """Owner reacting to their own project creates no notification."""
        _, a_profile = user_a
        project = _make_project(a_profile)

        resp = auth_client_a.post(_react_url(project.project_id))
        assert resp.status_code == 201

        assert Notification.objects.filter(recipient=a_profile, type='reaction').count() == 0

    @pytest.mark.django_db
    def test_prefs_social_in_app_false_skips_notification(self, user_a, user_b, auth_client_a):
        """recipient.notifications['social']['in_app'] = False suppresses emission."""
        _, b_profile = user_b
        b_profile.notifications = {'social': {'in_app': False}}
        b_profile.save(update_fields=['notifications'])
        project = _make_project(b_profile)

        resp = auth_client_a.post(_react_url(project.project_id))
        assert resp.status_code == 201

        assert Notification.objects.filter(recipient=b_profile, type='reaction').count() == 0

    @pytest.mark.django_db
    def test_absent_prefs_emits_by_default(self, user_a, user_b, auth_client_a):
        """No 'notifications' prefs set at all -> notification still emitted (opt-out default)."""
        _, b_profile = user_b
        assert b_profile.notifications == {}
        project = _make_project(b_profile)

        resp = auth_client_a.post(_react_url(project.project_id))
        assert resp.status_code == 201

        assert Notification.objects.filter(recipient=b_profile, type='reaction').count() == 1

    @pytest.mark.django_db
    def test_repeated_react_unreact_react_no_duplicate_while_unread(self, user_a, user_b, auth_client_a):
        """react -> unreact -> react on same project while first notif unread: no 2nd row."""
        _, b_profile = user_b
        project = _make_project(b_profile)

        resp1 = auth_client_a.post(_react_url(project.project_id))
        assert resp1.status_code == 201
        assert Notification.objects.filter(recipient=b_profile, type='reaction').count() == 1

        resp2 = auth_client_a.delete(_react_url(project.project_id))
        assert resp2.status_code == 204

        resp3 = auth_client_a.post(_react_url(project.project_id))
        assert resp3.status_code == 201

        # Still just one row — dedupe checks for an UNREAD row with the same
        # (recipient, actor, type, project_id); the first row is still unread.
        assert Notification.objects.filter(recipient=b_profile, type='reaction').count() == 1

    @pytest.mark.django_db
    def test_read_notification_allows_new_one_on_re_react(self, user_a, user_b, auth_client_a):
        """Once the existing notification is marked read, a fresh react creates a new row."""
        _, a_profile = user_a
        _, b_profile = user_b
        project = _make_project(b_profile)

        auth_client_a.post(_react_url(project.project_id))
        Notification.objects.filter(recipient=b_profile, type='reaction').update(
            read_at=timezone.now()
        )
        auth_client_a.delete(_react_url(project.project_id))
        auth_client_a.post(_react_url(project.project_id))

        assert Notification.objects.filter(recipient=b_profile, type='reaction').count() == 2

    @pytest.mark.django_db
    def test_notify_reaction_service_directly(self, user_a, user_b):
        """Unit-level: calling notify_reaction(reaction) directly creates the row."""
        from apps.social.models import Reaction
        _, a_profile = user_a
        _, b_profile = user_b
        project = _make_project(b_profile)
        reaction = Reaction.objects.create(user=a_profile, project=project)

        notify_reaction(reaction)

        assert Notification.objects.filter(recipient=b_profile, type='reaction').count() == 1

    @pytest.mark.django_db
    def test_notify_reaction_never_raises_on_bad_input(self):
        """notify_reaction swallows exceptions from a malformed input object."""
        class _Bogus:
            pass
        # Should not raise even though _Bogus() has no .project/.user attrs.
        notify_reaction(_Bogus())


# ---------------------------------------------------------------------------
# TestSecurityEmission
# ---------------------------------------------------------------------------

class TestSecurityEmission:

    @pytest.mark.django_db
    def test_password_changed_always_emitted_even_with_prefs_off(self, user_a):
        """notify_security ignores prefs entirely — security is always-on."""
        _, a_profile = user_a
        a_profile.notifications = {'security': {'in_app': False}}
        a_profile.save(update_fields=['notifications'])

        notify_security(a_profile, 'password_changed')

        notif = Notification.objects.get(recipient=a_profile, type='password_changed')
        assert notif.category == 'security'
        assert notif.actor is None

    @pytest.mark.django_db
    def test_set_password_view_emits_notification(self, user_a):
        """POST /api/v1/auth/set-password/ (first-set, no current_password) emits password_changed."""
        from rest_framework.test import APIClient
        from rest_framework_simplejwt.tokens import RefreshToken
        user, profile = user_a
        user.set_unusable_password()
        user.save()
        client = APIClient()
        refresh = RefreshToken.for_user(user)
        client.credentials(HTTP_AUTHORIZATION=f'Bearer {refresh.access_token}')

        resp = client.post('/api/v1/auth/set-password/', {'password': 'S3cur3Pass!2026'})
        assert resp.status_code == 200

        assert Notification.objects.filter(recipient=profile, type='password_changed').count() == 1

    @pytest.mark.django_db
    def test_first_device_silent_second_device_notifies(self, user_a):
        """First KnownDevice row for a user is recorded without notifying;
        a 2nd distinct ua_hash triggers notify_security('new_login')."""
        _, a_profile = user_a

        record_device_and_maybe_notify(a_profile, 'UA-one')
        assert KnownDevice.objects.filter(user=a_profile).count() == 1
        assert Notification.objects.filter(recipient=a_profile, type='new_login').count() == 0

        record_device_and_maybe_notify(a_profile, 'UA-two')
        assert KnownDevice.objects.filter(user=a_profile).count() == 2
        assert Notification.objects.filter(recipient=a_profile, type='new_login').count() == 1

        # Re-using the same 2nd UA again should not create a duplicate KnownDevice
        # row nor another notification (get_or_create + created=False).
        record_device_and_maybe_notify(a_profile, 'UA-two')
        assert KnownDevice.objects.filter(user=a_profile).count() == 2
        assert Notification.objects.filter(recipient=a_profile, type='new_login').count() == 1

    @pytest.mark.django_db
    def test_missing_user_agent_hashes_empty_string(self, user_a):
        """Missing UA -> hash of empty string, still a valid stable bucket."""
        _, a_profile = user_a
        record_device_and_maybe_notify(a_profile, '')
        assert KnownDevice.objects.filter(user=a_profile, ua_hash=hash_user_agent('')).count() == 1

    @pytest.mark.django_db
    def test_password_login_view_new_device_notification(self, user_a):
        """PasswordLoginView: first login (empty UA/registration-equivalent) silent,
        a login with a DIFFERENT UA notifies new_login."""
        from rest_framework.test import APIClient
        user, profile = user_a
        profile.handle = 'alice_handle'
        profile.save(update_fields=['handle'])
        user.set_password('S3cur3Pass!2026')
        user.save()

        client = APIClient()
        resp1 = client.post(
            '/api/v1/auth/login/',
            {'handle': 'alice_handle', 'password': 'S3cur3Pass!2026'},
            HTTP_USER_AGENT='UA-device-1',
        )
        assert resp1.status_code == 200
        assert Notification.objects.filter(recipient=profile, type='new_login').count() == 0

        resp2 = client.post(
            '/api/v1/auth/login/',
            {'handle': 'alice_handle', 'password': 'S3cur3Pass!2026'},
            HTTP_USER_AGENT='UA-device-2',
        )
        assert resp2.status_code == 200
        assert Notification.objects.filter(recipient=profile, type='new_login').count() == 1


# ---------------------------------------------------------------------------
# TestNotificationEndpoints
# ---------------------------------------------------------------------------

class TestNotificationEndpoints:

    @pytest.mark.django_db
    def test_list_only_own_notifications(self, user_a, user_b, auth_client_a, auth_client_b):
        _, a_profile = user_a
        _, b_profile = user_b
        Notification.objects.create(recipient=a_profile, type='password_changed', category='security')
        Notification.objects.create(recipient=b_profile, type='password_changed', category='security')

        resp = auth_client_a.get('/api/v1/notifications/')
        assert resp.status_code == 200
        data = resp.json()
        assert data['total'] == 1
        assert len(data['results']) == 1

    @pytest.mark.django_db
    def test_list_paginated_default_20_cap_50(self, user_a, auth_client_a):
        _, a_profile = user_a
        for i in range(25):
            Notification.objects.create(recipient=a_profile, type='password_changed', category='security')

        resp = auth_client_a.get('/api/v1/notifications/')
        data = resp.json()
        assert data['page_size'] == 20
        assert len(data['results']) == 20
        assert data['has_more'] is True

        resp2 = auth_client_a.get('/api/v1/notifications/?page_size=100')
        data2 = resp2.json()
        assert data2['page_size'] == 50  # capped

    @pytest.mark.django_db
    def test_list_ordered_newest_first(self, user_a, auth_client_a):
        _, a_profile = user_a
        n1 = Notification.objects.create(recipient=a_profile, type='password_changed', category='security')
        n2 = Notification.objects.create(recipient=a_profile, type='new_login', category='security')

        resp = auth_client_a.get('/api/v1/notifications/')
        results = resp.json()['results']
        assert results[0]['id'] == n2.id
        assert results[1]['id'] == n1.id

    @pytest.mark.django_db
    def test_unread_count(self, user_a, auth_client_a):
        _, a_profile = user_a
        Notification.objects.create(recipient=a_profile, type='password_changed', category='security')
        Notification.objects.create(
            recipient=a_profile, type='new_login', category='security', read_at=timezone.now(),
        )

        resp = auth_client_a.get('/api/v1/notifications/unread-count/')
        assert resp.status_code == 200
        assert resp.json()['count'] == 1

    @pytest.mark.django_db
    def test_mark_read_by_ids(self, user_a, auth_client_a):
        _, a_profile = user_a
        n1 = Notification.objects.create(recipient=a_profile, type='password_changed', category='security')
        n2 = Notification.objects.create(recipient=a_profile, type='new_login', category='security')

        resp = auth_client_a.post('/api/v1/notifications/mark-read/', {'ids': [n1.id]}, format='json')
        assert resp.status_code == 200
        assert resp.json()['updated'] == 1

        n1.refresh_from_db()
        n2.refresh_from_db()
        assert n1.read_at is not None
        assert n2.read_at is None

    @pytest.mark.django_db
    def test_mark_read_all(self, user_a, auth_client_a):
        _, a_profile = user_a
        Notification.objects.create(recipient=a_profile, type='password_changed', category='security')
        Notification.objects.create(recipient=a_profile, type='new_login', category='security')

        resp = auth_client_a.post('/api/v1/notifications/mark-read/', {'all': True}, format='json')
        assert resp.status_code == 200
        assert resp.json()['updated'] == 2
        assert Notification.objects.filter(recipient=a_profile, read_at__isnull=True).count() == 0

    @pytest.mark.django_db
    def test_mark_read_idempotent(self, user_a, auth_client_a):
        _, a_profile = user_a
        n1 = Notification.objects.create(recipient=a_profile, type='password_changed', category='security')

        resp1 = auth_client_a.post('/api/v1/notifications/mark-read/', {'ids': [n1.id]}, format='json')
        assert resp1.json()['updated'] == 1

        resp2 = auth_client_a.post('/api/v1/notifications/mark-read/', {'ids': [n1.id]}, format='json')
        assert resp2.json()['updated'] == 0  # already read — not re-counted

    @pytest.mark.django_db
    def test_mark_read_self_only(self, user_a, user_b, auth_client_a):
        """mark-read only touches the caller's own rows, even if ids include another user's notif."""
        _, a_profile = user_a
        _, b_profile = user_b
        n_b = Notification.objects.create(recipient=b_profile, type='password_changed', category='security')

        resp = auth_client_a.post('/api/v1/notifications/mark-read/', {'ids': [n_b.id]}, format='json')
        assert resp.status_code == 200
        assert resp.json()['updated'] == 0

        n_b.refresh_from_db()
        assert n_b.read_at is None

    @pytest.mark.django_db
    def test_mark_read_ids_length_cap(self, user_a, auth_client_a):
        resp = auth_client_a.post(
            '/api/v1/notifications/mark-read/', {'ids': list(range(501))}, format='json'
        )
        assert resp.status_code == 400

    @pytest.mark.django_db
    def test_anon_cannot_access_endpoints(self, anon_client):
        assert anon_client.get('/api/v1/notifications/').status_code == 401
        assert anon_client.get('/api/v1/notifications/unread-count/').status_code == 401
        assert anon_client.post('/api/v1/notifications/mark-read/', {'all': True}, format='json').status_code == 401


# ---------------------------------------------------------------------------
# TestNotificationsValidator
# ---------------------------------------------------------------------------

class TestNotificationsValidator:

    @pytest.mark.django_db
    def test_validator_accepts_in_app_bool(self, user_a, auth_client_a):
        resp = auth_client_a.patch(
            '/api/v1/users/me/',
            {'notifications': {'social': {'in_app': True}, 'security': {'in_app': False}}},
            format='json',
        )
        assert resp.status_code == 200

    @pytest.mark.django_db
    def test_validator_rejects_non_bool_in_app(self, user_a, auth_client_a):
        resp = auth_client_a.patch(
            '/api/v1/users/me/',
            {'notifications': {'social': {'in_app': 'yes'}}},
            format='json',
        )
        assert resp.status_code == 400

    @pytest.mark.django_db
    def test_validator_rejects_unknown_key(self, user_a, auth_client_a):
        resp = auth_client_a.patch(
            '/api/v1/users/me/',
            {'notifications': {'social': {'sms': True}}},
            format='json',
        )
        assert resp.status_code == 400

    @pytest.mark.django_db
    def test_validator_still_accepts_push_email(self, user_a, auth_client_a):
        resp = auth_client_a.patch(
            '/api/v1/users/me/',
            {'notifications': {'social': {'push': True, 'email': False, 'in_app': True}}},
            format='json',
        )
        assert resp.status_code == 200
