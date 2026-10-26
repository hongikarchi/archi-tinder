"""Social-only signup: first Google/Kakao login creates the account; onboarding completes it."""

import pytest
from django.contrib.auth.models import User
from rest_framework.test import APIClient

from apps.accounts.models import SocialAccount, UserProfile

GOOGLE_INFO = {
    'provider_id': 'g_new_1', 'email': 'new@example.com', 'email_verified': True,
    'display_name': 'New Person', 'avatar_url': '',
}
KAKAO_INFO = {
    'provider_id': '12345', 'email': 'k@example.com', 'email_verified': True,
    'display_name': '카카오유저', 'avatar_url': 'https://example.com/k.png',
}
KAKAO_URI = 'http://localhost:5173/auth/kakao/callback'


def _google(monkeypatch, info=GOOGLE_INFO):
    monkeypatch.setattr('apps.accounts.views.auth._exchange_google_code', lambda code: dict(info))
    return APIClient().post('/api/v1/auth/social/google/', {'code': 'c'}, format='json')


@pytest.mark.django_db
def test_google_new_user_created_and_relogin_same(monkeypatch):
    r = _google(monkeypatch)
    assert r.status_code == 200
    assert r.json()['user']['onboarding_required'] is True
    uid = r.json()['user']['user_id']
    p = UserProfile.objects.get(user_id=uid)
    assert p.is_guest is False and p.consent_accepted_at is None
    assert not p.user.has_usable_password()
    r2 = _google(monkeypatch)
    assert r2.json()['user']['user_id'] == uid
    assert UserProfile.objects.count() == 1


@pytest.mark.django_db
def test_kakao_success(monkeypatch, settings):
    settings.KAKAO_REDIRECT_URIS = [KAKAO_URI]
    monkeypatch.setattr('apps.accounts.views.auth._exchange_kakao_code', lambda c, r: dict(KAKAO_INFO))
    r = APIClient().post('/api/v1/auth/social/kakao/', {'code': 'c', 'redirect_uri': KAKAO_URI}, format='json')
    assert r.status_code == 200
    assert r.json()['user']['onboarding_required'] is True
    assert r.json()['user']['handle'] == '카카오유저'
    assert SocialAccount.objects.filter(provider='kakao', provider_id='12345').exists()


@pytest.mark.django_db
def test_kakao_bad_redirect_uri(monkeypatch, settings):
    settings.KAKAO_REDIRECT_URIS = [KAKAO_URI]
    r = APIClient().post('/api/v1/auth/social/kakao/', {'code': 'c', 'redirect_uri': 'http://evil/'}, format='json')
    assert r.status_code == 400
    assert r.json()['detail'] == 'invalid_redirect_uri'


@pytest.mark.django_db
def test_kakao_exchange_failure_401(monkeypatch, settings):
    settings.KAKAO_REDIRECT_URIS = [KAKAO_URI]

    def boom(c, r):
        raise ValueError('x')
    monkeypatch.setattr('apps.accounts.views.auth._exchange_kakao_code', boom)
    r = APIClient().post('/api/v1/auth/social/kakao/', {'code': 'c', 'redirect_uri': KAKAO_URI}, format='json')
    assert r.status_code == 401
    assert r.json()['detail'] == 'kakao_auth_failed'


@pytest.mark.django_db
def test_handle_collision_gets_suffix(monkeypatch):
    u = User.objects.create_user(username='x')
    UserProfile.objects.create(user=u, handle='NewPerson', display_name='NewPerson')
    info = dict(GOOGLE_INFO, display_name='NewPerson', email='')
    r = _google(monkeypatch, info)
    h = r.json()['user']['handle']
    assert h != 'NewPerson' and h.startswith('NewPerson')


def _authed(monkeypatch):
    r = _google(monkeypatch)
    c = APIClient()
    c.credentials(HTTP_AUTHORIZATION=f"Bearer {r.json()['access']}")
    return c


@pytest.mark.django_db
def test_onboarding_flow(monkeypatch):
    c = _authed(monkeypatch)
    body = {'handle': 'my_id', 'onboarding_role': 'student', 'consent_accepted': True}
    r = c.post('/api/v1/auth/onboarding/', {**body, 'consent_accepted': False}, format='json')
    assert r.status_code == 400 and r.json()['detail'] == 'consent_required'
    r = c.post('/api/v1/auth/onboarding/', {**body, 'onboarding_role': 'zzz'}, format='json')
    assert r.status_code == 400 and r.json()['detail'] == 'role_invalid'
    r = c.post('/api/v1/auth/onboarding/', {**body, 'handle': 'a b'}, format='json')
    assert r.status_code == 400 and r.json()['detail'] == 'handle_invalid'
    r = c.post('/api/v1/auth/onboarding/', body, format='json')
    assert r.status_code == 200
    assert r.json()['onboarding_required'] is False
    assert r.json()['handle'] == 'my_id'
    r = c.post('/api/v1/auth/onboarding/', body, format='json')
    assert r.status_code == 409 and r.json()['detail'] == 'already_onboarded'
