"""
test_oauth_email_verified.py -- SECURITY: OAuth email-verified guard tests.

Verifies the account-takeover mitigation introduced in auth.py:
  - Linking by email is gated on email_verified=True.
  - Unverified email never links into an existing account.
  - Unverified email is NOT stored on newly created accounts.
  - GuestPromoteView email-match merge is gated on email_verified.
  - GuestPromoteView in-place promote with unverified email uses empty email.

Test matrix:
  VER-1  _get_or_create_user, verified email → links new social into existing
         account (preserves prior behaviour).
  VER-2  _get_or_create_user, UNVERIFIED email → creates NEW account with
         email=='' (no link, no email stored).
  VER-3  GoogleLoginView POST with access_token, verified email matching
         existing user → links (endpoint-level test; mocks requests.get).
  VER-4  GoogleLoginView POST with access_token, UNVERIFIED email matching
         existing user → creates NEW user, email==''.
  VER-5  GuestPromoteView, UNVERIFIED google email matching existing verified
         user → does NOT merge; in-place promote with email==''.
"""

import pytest
from unittest.mock import patch, MagicMock
from django.contrib.auth.models import User
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from apps.accounts.models import UserProfile, SocialAccount
from apps.accounts.views.auth import _get_or_create_user


# ---------------------------------------------------------------------------
# VER-1: verified email match → links into existing account
# ---------------------------------------------------------------------------

@pytest.mark.django_db
def test_get_or_create_user_verified_email_links_existing():
    """Verified email matching an existing account → link (prior behaviour preserved)."""
    existing_user = User.objects.create_user(
        username='existing', email='victim@example.com',
    )
    existing_profile = UserProfile.objects.create(
        user=existing_user, display_name='Existing User',
    )

    result_profile = _get_or_create_user(
        provider='google',
        provider_id='google_sub_001',
        email='victim@example.com',
        display_name='Google User',
        avatar_url='https://example.com/avatar.jpg',
        email_verified=True,
    )

    # Must return the EXISTING profile, not a new one
    assert result_profile.pk == existing_profile.pk

    # SocialAccount must be linked to the existing user
    social = SocialAccount.objects.get(provider='google', provider_id='google_sub_001')
    assert social.user.pk == existing_profile.pk

    # Only one UserProfile should exist
    assert UserProfile.objects.count() == 1


# ---------------------------------------------------------------------------
# VER-2: UNVERIFIED email → new account, email==''
# ---------------------------------------------------------------------------

@pytest.mark.django_db
def test_get_or_create_user_unverified_email_creates_new_no_email():
    """UNVERIFIED email matching an existing account → NEW account created, email==''."""
    existing_user = User.objects.create_user(
        username='victim', email='victim@example.com',
    )
    UserProfile.objects.create(user=existing_user, display_name='Victim')

    result_profile = _get_or_create_user(
        provider='google',
        provider_id='google_sub_attacker',
        email='victim@example.com',
        display_name='Attacker',
        avatar_url='',
        email_verified=False,
    )

    # Must NOT return the existing profile — a NEW account must be created
    assert result_profile.user.pk != existing_user.pk

    # New account must have empty email (not the unverified address)
    assert result_profile.user.email == ''

    # Two profiles now exist
    assert UserProfile.objects.count() == 2

    # SocialAccount is attached to the NEW profile (not victim)
    social = SocialAccount.objects.get(provider='google', provider_id='google_sub_attacker')
    assert social.user.pk == result_profile.pk
    assert social.user.pk != existing_user.pk


# ---------------------------------------------------------------------------
# VER-3: GoogleLoginView endpoint, verified email → links existing account
# ---------------------------------------------------------------------------

@pytest.mark.django_db
def test_google_login_view_verified_email_links_existing():
    """GoogleLoginView: verified Google email matching existing user → links."""
    existing_user = User.objects.create_user(
        username='legit_user', email='legit@example.com',
    )
    existing_profile = UserProfile.objects.create(
        user=existing_user, display_name='Legit User',
    )

    userinfo_response = MagicMock()
    userinfo_response.status_code = 200
    userinfo_response.json.return_value = {
        'sub': 'google_sub_legit',
        'email': 'legit@example.com',
        'email_verified': True,
        'name': 'Legit Google',
        'picture': 'https://example.com/pic.jpg',
    }

    client = APIClient()
    with patch('apps.accounts.views.auth.requests.get', return_value=userinfo_response):
        resp = client.post(
            '/api/v1/auth/google/',
            {'access_token': 'fake_access_token'},
            format='json',
        )

    assert resp.status_code == 200

    # Only one UserProfile must exist (linked, not a new account)
    assert UserProfile.objects.count() == 1

    # SocialAccount attached to the existing profile
    social = SocialAccount.objects.get(provider='google', provider_id='google_sub_legit')
    assert social.user.pk == existing_profile.pk


# ---------------------------------------------------------------------------
# VER-4: GoogleLoginView endpoint, UNVERIFIED email → new user, email==''
# ---------------------------------------------------------------------------

@pytest.mark.django_db
def test_google_login_view_unverified_email_creates_new_no_email():
    """GoogleLoginView: unverified Google email matching existing user → NEW account, email==''."""
    existing_user = User.objects.create_user(
        username='victim2', email='victim2@example.com',
    )
    UserProfile.objects.create(user=existing_user, display_name='Victim2')

    userinfo_response = MagicMock()
    userinfo_response.status_code = 200
    userinfo_response.json.return_value = {
        'sub': 'google_sub_unverified',
        'email': 'victim2@example.com',
        'email_verified': False,
        'name': 'Attacker2',
        'picture': '',
    }

    client = APIClient()
    with patch('apps.accounts.views.auth.requests.get', return_value=userinfo_response):
        resp = client.post(
            '/api/v1/auth/google/',
            {'access_token': 'fake_access_token'},
            format='json',
        )

    assert resp.status_code == 200

    # Two profiles now — victim unchanged, attacker in new account
    assert UserProfile.objects.count() == 2

    # New account has email==''
    new_user = User.objects.get(username='google_google_sub_unverified')
    assert new_user.email == ''

    # Victim's email untouched
    existing_user.refresh_from_db()
    assert existing_user.email == 'victim2@example.com'


# ---------------------------------------------------------------------------
# VER-5: GuestPromoteView, UNVERIFIED Google email → in-place promote, email==''
# ---------------------------------------------------------------------------

@pytest.mark.django_db
def test_guest_promote_unverified_email_no_merge():
    """GuestPromoteView: unverified Google email matching existing user → NO merge, email==''."""
    # Set up an existing verified user
    existing_user = User.objects.create_user(
        username='verified_user', email='target@example.com',
    )
    UserProfile.objects.create(
        user=existing_user, display_name='Verified User', is_guest=False,
    )

    # Set up a guest user
    guest_user = User.objects.create_user(username='guest_abc', email='')
    guest_user.set_unusable_password()
    guest_user.save()
    UserProfile.objects.create(
        user=guest_user, display_name='Guest', is_guest=True,
    )

    # Issue a guest JWT
    client = APIClient()
    guest_token = str(RefreshToken.for_user(guest_user).access_token)
    client.credentials(HTTP_AUTHORIZATION=f'Bearer {guest_token}')

    fake_google_data = {
        'provider_id':    'google_sub_attacker3',
        'email':          'target@example.com',
        'display_name':   'Attacker3',
        'avatar_url':     '',
        'email_verified': False,
    }

    with patch(
        'apps.accounts.views.auth._exchange_google_code',
        return_value=fake_google_data,
    ):
        resp = client.post(
            '/api/v1/auth/promote/',
            {'provider': 'google', 'code': 'fake_code'},
            format='json',
        )

    assert resp.status_code == 200

    # Must NOT have merged: existing verified user still intact
    existing_user.refresh_from_db()
    assert existing_user.email == 'target@example.com'
    assert User.objects.filter(pk=existing_user.pk).exists()

    # Guest was promoted in-place (not deleted; guest_user row updated)
    promoted_user = User.objects.get(pk=guest_user.pk)
    # email must be '' (unverified address not stored)
    assert promoted_user.email == ''

    # profile is no longer a guest
    promoted_profile = promoted_user.profile
    assert not promoted_profile.is_guest

    # Two profiles still exist (no merge)
    assert UserProfile.objects.count() == 2
