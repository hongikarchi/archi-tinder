"""
test_oauth_email_verified.py -- SECURITY: OAuth email-verified guard tests.

LOGIN-ONBOARD-1 update: _get_or_create_user no longer creates new accounts.
Brand-new Google logins (no matching account) now return signup_required (404).

Verifies the account-takeover mitigation introduced in auth.py:
  - Linking by email is gated on email_verified=True.
  - Unverified email never links into an existing account.
  - Brand-new social login (no existing account) → signup_required 404.
  - GuestPromoteView email-match merge is gated on email_verified.
  - GuestPromoteView in-place promote with unverified email uses empty email.

Test matrix:
  VER-1  _get_or_create_user, verified email → links new social into existing
         account (preserves prior behaviour).
  VER-2  _get_or_create_user, UNVERIFIED email matching existing user → returns
         None (no new account created, no link).  [LOGIN-ONBOARD-1 changed]
  VER-2b _get_or_create_user, brand-new provider_id + no email match → None.
  VER-3  GoogleLoginView POST with access_token, verified email matching
         existing user → links (endpoint-level test; mocks requests.get).
  VER-4  GoogleLoginView POST with access_token, UNVERIFIED email matching
         existing user → 404 signup_required (no create).  [LOGIN-ONBOARD-1 changed]
  VER-4b GoogleLoginView POST, brand-new Google account (no existing user at all)
         → 404 signup_required.  [LOGIN-ONBOARD-1 new]
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
    assert result_profile is not None
    assert result_profile.pk == existing_profile.pk

    # SocialAccount must be linked to the existing user
    social = SocialAccount.objects.get(provider='google', provider_id='google_sub_001')
    assert social.user.pk == existing_profile.pk

    # Only one UserProfile should exist
    assert UserProfile.objects.count() == 1


# ---------------------------------------------------------------------------
# VER-2: UNVERIFIED email matching existing user → None (no new account)
# ---------------------------------------------------------------------------

@pytest.mark.django_db
def test_get_or_create_user_unverified_email_returns_none():
    """UNVERIFIED email matching an existing account → None (no account creation).

    LOGIN-ONBOARD-1: create-new branch removed. Returns None so caller returns
    signup_required. The existing account is NOT touched.
    """
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

    # LOGIN-ONBOARD-1: returns None (no new account created)
    assert result_profile is None

    # Only one profile — existing user untouched
    assert UserProfile.objects.count() == 1

    # No SocialAccount was created for the attacker
    assert not SocialAccount.objects.filter(
        provider='google', provider_id='google_sub_attacker',
    ).exists()


# ---------------------------------------------------------------------------
# VER-2b: brand-new provider_id, no email match → None
# ---------------------------------------------------------------------------

@pytest.mark.django_db
def test_get_or_create_user_brand_new_returns_none():
    """No existing account + new provider_id → None (signup_required)."""
    result_profile = _get_or_create_user(
        provider='google',
        provider_id='brand_new_sub_999',
        email='brandnew@example.com',
        display_name='Brand New',
        avatar_url='',
        email_verified=True,
    )

    # LOGIN-ONBOARD-1: no account creation → None
    assert result_profile is None
    assert UserProfile.objects.count() == 0


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
            '/api/v1/auth/social/google/',
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
# VER-4: GoogleLoginView endpoint, UNVERIFIED email → 404 signup_required
# ---------------------------------------------------------------------------

@pytest.mark.django_db
def test_google_login_view_unverified_email_signup_required():
    """GoogleLoginView: unverified Google email → 404 signup_required (no create).

    LOGIN-ONBOARD-1: create-new branch removed. Unverified email no longer
    creates a new account. Returns signup_required instead.
    """
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
            '/api/v1/auth/social/google/',
            {'access_token': 'fake_access_token'},
            format='json',
        )

    # LOGIN-ONBOARD-1: no new account → signup_required
    assert resp.status_code == 404
    data = resp.json()
    assert data['detail'] == 'signup_required'

    # Victim untouched; no new account created
    assert UserProfile.objects.count() == 1
    existing_user.refresh_from_db()
    assert existing_user.email == 'victim2@example.com'


# ---------------------------------------------------------------------------
# VER-4b: GoogleLoginView endpoint, brand-new account → 404 signup_required
# ---------------------------------------------------------------------------

@pytest.mark.django_db
def test_google_login_view_brand_new_signup_required():
    """GoogleLoginView: completely new Google user (no existing account) → 404 signup_required."""
    userinfo_response = MagicMock()
    userinfo_response.status_code = 200
    userinfo_response.json.return_value = {
        'sub': 'google_sub_brandnew',
        'email': 'brandnew@example.com',
        'email_verified': True,
        'name': 'Brand New',
        'picture': '',
    }

    client = APIClient()
    with patch('apps.accounts.views.auth.requests.get', return_value=userinfo_response):
        resp = client.post(
            '/api/v1/auth/social/google/',
            {'access_token': 'fake_access_token'},
            format='json',
        )

    assert resp.status_code == 404
    data = resp.json()
    assert data['detail'] == 'signup_required'
    assert data['reason'] == 'no_account'

    # No accounts created
    assert UserProfile.objects.count() == 0


# ---------------------------------------------------------------------------
# VER-5: GuestPromoteView, UNVERIFIED Google email → in-place promote, email==''
# ---------------------------------------------------------------------------

@pytest.mark.django_db
def test_guest_promote_unverified_email_no_merge():
    """GuestPromoteView: unverified Google email matching existing user → NO merge, email==''.

    GuestPromoteView uses _exchange_google_code directly (not _get_or_create_user)
    so this test is unaffected by the create-new removal.
    """
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


# ---------------------------------------------------------------------------
# LOGIN-ONBOARD-1 regression: display_name (unified ID) must NOT be
# overwritten by the provider's free-form name on social login.
# ---------------------------------------------------------------------------

@pytest.mark.django_db
def test_social_login_preserves_display_name_on_returning_social_account():
    """Branch (i): returning social login must NOT clobber the user's unified display_name.

    After LOGIN-ONBOARD-1, display_name == handle (the user-chosen ID).
    A returning Google login was overwriting display_name with the provider's
    free-form name (e.g. 'John Smith'), defeating the unified-ID invariant.
    This regression test pins the correct behavior: display_name is preserved.
    """
    existing_user = User.objects.create_user(
        username='myaccount', email='me@example.com',
    )
    existing_profile = UserProfile.objects.create(
        user=existing_user,
        display_name='dain_kim',  # user's chosen unified ID
        handle='dain_kim',
    )
    # Pre-existing SocialAccount (branch i path)
    SocialAccount.objects.create(
        user=existing_profile,
        provider='google',
        provider_id='google_sub_dain',
    )

    result_profile = _get_or_create_user(
        provider='google',
        provider_id='google_sub_dain',
        email='me@example.com',
        display_name='Dain Kim Real Name',  # provider's free-form name
        avatar_url='https://example.com/new_avatar.jpg',
        email_verified=True,
    )

    assert result_profile is not None
    assert result_profile.pk == existing_profile.pk

    # display_name must be preserved (user's unified ID, not clobbered)
    result_profile.refresh_from_db()
    assert result_profile.display_name == 'dain_kim', (
        'display_name must not be overwritten by provider name on social re-login'
    )
    assert result_profile.handle == 'dain_kim'

    # avatar_url IS allowed to sync from the provider
    assert result_profile.avatar_url == 'https://example.com/new_avatar.jpg'


@pytest.mark.django_db
def test_social_login_preserves_display_name_on_email_match_link():
    """Branch (ii): email-match link must NOT clobber the user's unified display_name.

    When a social account is linked to an existing user via email match, the
    provider's free-form name must not overwrite the user's chosen display_name.
    """
    existing_user = User.objects.create_user(
        username='myemail_account', email='linked@example.com',
    )
    existing_profile = UserProfile.objects.create(
        user=existing_user,
        display_name='건축가_dain',  # user's chosen unified ID (Hangul+ASCII)
        handle='건축가_dain',
    )

    result_profile = _get_or_create_user(
        provider='google',
        provider_id='google_sub_email_match',
        email='linked@example.com',
        display_name='Link Provider Name',  # provider's free-form name
        avatar_url='',
        email_verified=True,
    )

    assert result_profile is not None
    assert result_profile.pk == existing_profile.pk

    result_profile.refresh_from_db()
    # display_name must be preserved (unified ID)
    assert result_profile.display_name == '건축가_dain', (
        'display_name must not be overwritten by provider name on email-match link'
    )
    assert result_profile.handle == '건축가_dain'
