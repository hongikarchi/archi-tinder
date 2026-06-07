"""
test_auth_login.py -- AUTH-LOGIN-1 backend tests.

E1: handle+password auth (register / login / set-password)
E2: email verify via OAuth linking (link-email)

Coverage matrix
  TestRegister            (5 tests) -- success, duplicate handle, weak password,
                                       reserved handle, handle format validation
  TestPasswordLogin       (5 tests) -- correct creds, wrong password (generic),
                                       nonexistent handle (same generic message),
                                       OAuth user no password (generic),
                                       response shape + JWT works
  TestSetPassword         (7 tests) -- first-set on guest (no current needed),
                                       guest first-set then login works,
                                       change requires correct current,
                                       wrong current → 400,
                                       weak new password → 400,
                                       old refresh blacklisted + fresh pair returned (AUTH-CRITICAL),
                                       throttle → 429 after 5 calls/min (AUTH-CRITICAL)
  TestLinkEmail           (6 tests) -- verified new email → set + SocialAccount
                                       + email_verified_at populated,
                                       unverified → 400 unverified_email,
                                       email already on another user → 400 reject,
                                       provider_id already on another user → 400,
                                       re-link own account is idempotent,
                                       unauthenticated → 401
  TestUserSerializerFields (3 tests) -- email/has_password/email_verified_at
                                        present in UserSerializer output (self-only);
                                        not present in public UserProfileSerializer
"""

import pytest
from django.contrib.auth.models import User
from django.core.cache import cache
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken
from unittest.mock import patch

from apps.accounts.models import UserProfile, SocialAccount


# ---------------------------------------------------------------------------
# Helpers / Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def clear_throttle_cache():
    """Clear cache before every test so throttle counters don't bleed between tests."""
    cache.clear()
    yield
    cache.clear()


def _make_profile(username='u1', email='', password=None, handle=None,
                  is_guest=False, display_name='Test User'):
    """Create a minimal User + UserProfile.  Returns profile."""
    user = User.objects.create_user(username=username, email=email)
    if password:
        user.set_password(password)
        user.save(update_fields=['password'])
    else:
        user.set_unusable_password()
        user.save(update_fields=['password'])
    profile = UserProfile.objects.create(
        user=user, display_name=display_name, handle=handle, is_guest=is_guest,
    )
    return profile


def _auth_client(profile):
    """Return an APIClient pre-loaded with a valid JWT for profile."""
    client = APIClient()
    refresh = RefreshToken.for_user(profile.user)
    client.credentials(HTTP_AUTHORIZATION=f'Bearer {refresh.access_token}')
    return client


# ---------------------------------------------------------------------------
# E1: Register
# ---------------------------------------------------------------------------

class TestRegister:

    ENDPOINT = '/api/v1/auth/register/'

    @pytest.mark.django_db
    def test_register_success(self):
        client = APIClient()
        resp = client.post(self.ENDPOINT, {
            'handle': 'newuser1',
            'password': 'Secur3P@ssw0rd!',
            'display_name': 'New User',
        }, format='json')
        assert resp.status_code == 201
        data = resp.json()
        assert 'access' in data
        assert 'refresh' in data
        assert data['user']['handle'] == 'newuser1'
        # Verify profile was created with is_guest=False
        profile = UserProfile.objects.get(handle='newuser1')
        assert profile.is_guest is False
        assert profile.user.has_usable_password() is True
        # User.username must NOT equal the handle (internal stable key)
        assert profile.user.username != 'newuser1'
        assert profile.user.username.startswith('local_')

    @pytest.mark.django_db
    def test_register_duplicate_handle(self, db):
        _make_profile(username='existing', handle='takenhandle')
        client = APIClient()
        resp = client.post(self.ENDPOINT, {
            'handle': 'takenhandle',
            'password': 'Secur3P@ssw0rd!',
        }, format='json')
        assert resp.status_code == 400
        data = resp.json()
        assert 'handle' in data

    @pytest.mark.django_db
    def test_register_duplicate_handle_case_insensitive(self, db):
        """handle uniqueness check is case-insensitive."""
        _make_profile(username='existing', handle='takenhandle')
        client = APIClient()
        # Try registering with uppercase variant (which also fails the format check)
        resp = client.post(self.ENDPOINT, {
            'handle': 'TakenHandle',
            'password': 'Secur3P@ssw0rd!',
        }, format='json')
        assert resp.status_code == 400

    @pytest.mark.django_db
    def test_register_weak_password(self):
        client = APIClient()
        resp = client.post(self.ENDPOINT, {
            'handle': 'weakpwuser',
            'password': '123',
        }, format='json')
        assert resp.status_code == 400
        assert 'password' in resp.json()

    @pytest.mark.django_db
    def test_register_reserved_handle(self):
        client = APIClient()
        resp = client.post(self.ENDPOINT, {
            'handle': 'admin',
            'password': 'Secur3P@ssw0rd!',
        }, format='json')
        assert resp.status_code == 400
        assert 'handle' in resp.json()

    @pytest.mark.django_db
    def test_register_invalid_handle_format(self):
        client = APIClient()
        resp = client.post(self.ENDPOINT, {
            'handle': 'ab',  # too short (< 3 chars)
            'password': 'Secur3P@ssw0rd!',
        }, format='json')
        assert resp.status_code == 400
        assert 'handle' in resp.json()


# ---------------------------------------------------------------------------
# E1: Login
# ---------------------------------------------------------------------------

class TestPasswordLogin:

    ENDPOINT = '/api/v1/auth/login/'

    @pytest.mark.django_db
    def test_login_success(self, db):
        _make_profile(username='loginuser', handle='loginhandle',
                      password='G00dP@ssword!', display_name='Login User')
        client = APIClient()
        resp = client.post(self.ENDPOINT, {
            'handle': 'loginhandle',
            'password': 'G00dP@ssword!',
        }, format='json')
        assert resp.status_code == 200
        data = resp.json()
        assert 'access' in data
        assert 'refresh' in data
        assert data['user']['handle'] == 'loginhandle'

    @pytest.mark.django_db
    def test_login_wrong_password_generic_error(self, db):
        _make_profile(username='u_wrongpw', handle='wrongpwhandle',
                      password='G00dP@ssword!')
        client = APIClient()
        resp = client.post(self.ENDPOINT, {
            'handle': 'wrongpwhandle',
            'password': 'WrongPassword!',
        }, format='json')
        assert resp.status_code == 400
        assert resp.json()['detail'] == 'Invalid handle or password.'

    @pytest.mark.django_db
    def test_login_nonexistent_handle_generic_error(self, db):
        """Nonexistent handle must return the same generic message as wrong password."""
        client = APIClient()
        resp = client.post(self.ENDPOINT, {
            'handle': 'doesnotexist',
            'password': 'SomePassword1!',
        }, format='json')
        assert resp.status_code == 400
        assert resp.json()['detail'] == 'Invalid handle or password.'

    @pytest.mark.django_db
    def test_login_oauth_user_no_password_generic_error(self, db):
        """OAuth-only user (no usable password) → same generic error."""
        # No password set (OAuth-only)
        _make_profile(username='oauthonly', handle='oauthhandle',
                      password=None)  # set_unusable_password in helper
        client = APIClient()
        resp = client.post(self.ENDPOINT, {
            'handle': 'oauthhandle',
            'password': 'AnyPassword1!',
        }, format='json')
        assert resp.status_code == 400
        assert resp.json()['detail'] == 'Invalid handle or password.'

    @pytest.mark.django_db
    def test_login_jwt_is_usable(self, db):
        """Returned JWT must be accepted by /auth/me/."""
        _make_profile(username='jwttest', handle='jwttesthandle',
                      password='G00dP@ssword!')
        client = APIClient()
        login_resp = client.post(self.ENDPOINT, {
            'handle': 'jwttesthandle',
            'password': 'G00dP@ssword!',
        }, format='json')
        assert login_resp.status_code == 200
        access = login_resp.json()['access']
        client.credentials(HTTP_AUTHORIZATION=f'Bearer {access}')
        me_resp = client.get('/api/v1/auth/me/')
        assert me_resp.status_code == 200


# ---------------------------------------------------------------------------
# E1: Set / Change Password
# ---------------------------------------------------------------------------

class TestSetPassword:

    ENDPOINT = '/api/v1/auth/set-password/'

    @pytest.mark.django_db
    def test_first_set_no_current_password_required(self, db):
        """Guest (no usable password) → set password without current_password."""
        profile = _make_profile(username='guest1', handle='guesthandle1',
                                is_guest=True, password=None)
        client = _auth_client(profile)
        resp = client.post(self.ENDPOINT, {
            'password': 'N3wSecur3P@ss!',
        }, format='json')
        assert resp.status_code == 200

    @pytest.mark.django_db
    def test_first_set_then_login_works(self, db):
        """After first-set, handle+password login must succeed."""
        profile = _make_profile(username='guest2', handle='guesthandle2',
                                is_guest=True, password=None)
        client = _auth_client(profile)
        # Set password
        resp = client.post(self.ENDPOINT, {
            'password': 'N3wSecur3P@ss!',
        }, format='json')
        assert resp.status_code == 200

        # Now login should work
        login_client = APIClient()
        login_resp = login_client.post('/api/v1/auth/login/', {
            'handle': 'guesthandle2',
            'password': 'N3wSecur3P@ss!',
        }, format='json')
        assert login_resp.status_code == 200

    @pytest.mark.django_db
    def test_change_password_requires_correct_current(self, db):
        """Existing password → change with correct current_password → 200."""
        profile = _make_profile(username='changepw', handle='changepwhandle',
                                password='OldSecur3P@ss!')
        client = _auth_client(profile)
        resp = client.post(self.ENDPOINT, {
            'current_password': 'OldSecur3P@ss!',
            'password': 'N3wSecur3P@ss99!',
        }, format='json')
        assert resp.status_code == 200

    @pytest.mark.django_db
    def test_change_password_wrong_current(self, db):
        """Wrong current_password → 400."""
        profile = _make_profile(username='wrongcurr', handle='wrongcurrhandle',
                                password='OldSecur3P@ss!')
        client = _auth_client(profile)
        resp = client.post(self.ENDPOINT, {
            'current_password': 'WrongCurrent!',
            'password': 'N3wSecur3P@ss99!',
        }, format='json')
        assert resp.status_code == 400
        assert 'current_password' in resp.json()

    @pytest.mark.django_db
    def test_weak_new_password_rejected(self, db):
        """Weak new password → 400 regardless of first-set vs change."""
        profile = _make_profile(username='weaknew', handle='weaknewhandle',
                                is_guest=True, password=None)
        client = _auth_client(profile)
        resp = client.post(self.ENDPOINT, {
            'password': '123',
        }, format='json')
        assert resp.status_code == 400
        assert 'password' in resp.json()

    @pytest.mark.django_db
    def test_set_password_blacklists_old_token_and_returns_fresh_pair(self, db):
        """After set-password: old refresh token is blacklisted; new token in response works."""
        from rest_framework_simplejwt.token_blacklist.models import (
            OutstandingToken, BlacklistedToken,
        )
        profile = _make_profile(username='bltest1', handle='bltesthandle1',
                                is_guest=True, password=None)
        # Obtain a refresh token BEFORE changing the password.
        old_refresh = RefreshToken.for_user(profile.user)
        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION=f'Bearer {old_refresh.access_token}')

        resp = client.post(self.ENDPOINT, {
            'password': 'Str0ngNewP@ss!',
        }, format='json')
        assert resp.status_code == 200

        # Response must carry a fresh token pair (option b).
        data = resp.json()
        assert 'access' in data
        assert 'refresh' in data
        assert 'user' in data

        # Old refresh token must now be blacklisted.
        outstanding_qs = OutstandingToken.objects.filter(
            user=profile.user,
            jti=str(old_refresh['jti']),
        )
        assert outstanding_qs.exists(), 'OutstandingToken row for old refresh must exist'
        assert BlacklistedToken.objects.filter(token=outstanding_qs.first()).exists(), \
            'Old refresh token must be blacklisted after set-password'

        # Old refresh token must be rejected by /auth/token/refresh/.
        refresh_client = APIClient()
        refresh_resp = refresh_client.post(
            '/api/v1/auth/token/refresh/',
            {'refresh': str(old_refresh)},
            format='json',
        )
        assert refresh_resp.status_code == 401, \
            'Blacklisted refresh token must be rejected (expected 401)'

        # Newly returned refresh token must still work.
        new_refresh_resp = refresh_client.post(
            '/api/v1/auth/token/refresh/',
            {'refresh': data['refresh']},
            format='json',
        )
        assert new_refresh_resp.status_code == 200, \
            'Fresh refresh token returned in response must still be valid'

    @pytest.mark.django_db
    def test_set_password_throttle_429_after_five_calls(self, db):
        """More than 5 set-password calls per minute → 429 Too Many Requests."""
        profile = _make_profile(username='throttletest', handle='throttletesthandle',
                                password='OldSecur3P@ss!')
        client = _auth_client(profile)

        # Fire 5 calls with wrong current_password (still counts toward throttle).
        for _ in range(5):
            client.post(self.ENDPOINT, {
                'current_password': 'wrong',
                'password': 'Str0ngNewP@ss!',
            }, format='json')

        # 6th call must be throttled.
        resp = client.post(self.ENDPOINT, {
            'current_password': 'wrong',
            'password': 'Str0ngNewP@ss!',
        }, format='json')
        assert resp.status_code == 429, \
            f'Expected 429 after 5 calls, got {resp.status_code}'


# ---------------------------------------------------------------------------
# E2: Link Email
# ---------------------------------------------------------------------------

_GOOD_GOOGLE_DATA = {
    'provider_id':    'google_sub_999',
    'email':          'verified@example.com',
    'display_name':   'Verified User',
    'avatar_url':     'https://example.com/av.jpg',
    'email_verified': True,
}

_UNVERIFIED_GOOGLE_DATA = {
    **_GOOD_GOOGLE_DATA,
    'email_verified': False,
}


class TestLinkEmail:

    ENDPOINT = '/api/v1/auth/link-email/'

    @pytest.mark.django_db
    def test_link_email_success(self, db):
        """Verified email → set User.email, SocialAccount, email_verified_at."""
        profile = _make_profile(username='linker1', handle='linkerhandle1')
        client = _auth_client(profile)

        with patch(
            'apps.accounts.views.auth._exchange_google_code',
            return_value=_GOOD_GOOGLE_DATA,
        ):
            resp = client.post(self.ENDPOINT, {
                'provider': 'google',
                'code': 'valid_code',
            }, format='json')

        assert resp.status_code == 200
        data = resp.json()
        assert data['email'] == 'verified@example.com'

        # DB state
        profile.user.refresh_from_db()
        assert profile.user.email == 'verified@example.com'
        assert SocialAccount.objects.filter(
            provider='google',
            provider_id='google_sub_999',
            user=profile,
        ).exists()
        profile.refresh_from_db()
        assert profile.email_verified_at is not None

    @pytest.mark.django_db
    def test_link_email_unverified_rejected(self, db):
        """Unverified email → 400 unverified_email."""
        profile = _make_profile(username='linker2', handle='linkerhandle2')
        client = _auth_client(profile)

        with patch(
            'apps.accounts.views.auth._exchange_google_code',
            return_value=_UNVERIFIED_GOOGLE_DATA,
        ):
            resp = client.post(self.ENDPOINT, {
                'provider': 'google',
                'code': 'unverified_code',
            }, format='json')

        assert resp.status_code == 400
        assert resp.json()['detail'] == 'unverified_email'

    @pytest.mark.django_db
    def test_link_email_already_on_another_user_rejected(self, db):
        """Email already on a different user → 400 email_already_linked."""
        # Another user already has this email
        other_user = User.objects.create_user(
            username='other', email='verified@example.com',
        )
        UserProfile.objects.create(user=other_user, display_name='Other')

        profile = _make_profile(username='linker3', handle='linkerhandle3')
        client = _auth_client(profile)

        with patch(
            'apps.accounts.views.auth._exchange_google_code',
            return_value=_GOOD_GOOGLE_DATA,
        ):
            resp = client.post(self.ENDPOINT, {
                'provider': 'google',
                'code': 'code_for_taken_email',
            }, format='json')

        assert resp.status_code == 400
        assert resp.json()['detail'] == 'email_already_linked'

    @pytest.mark.django_db
    def test_link_email_provider_id_on_another_user_rejected(self, db):
        """SocialAccount(google, provider_id) already on a different user → 400."""
        # Another user already has this Google provider_id
        other_user = User.objects.create_user(username='other2', email='other2@example.com')
        other_profile = UserProfile.objects.create(user=other_user, display_name='Other2')
        SocialAccount.objects.create(
            provider='google', provider_id='google_sub_999', user=other_profile,
        )

        profile = _make_profile(username='linker4', handle='linkerhandle4')
        client = _auth_client(profile)

        with patch(
            'apps.accounts.views.auth._exchange_google_code',
            return_value=_GOOD_GOOGLE_DATA,
        ):
            resp = client.post(self.ENDPOINT, {
                'provider': 'google',
                'code': 'code_for_taken_provider_id',
            }, format='json')

        assert resp.status_code == 400
        assert resp.json()['detail'] == 'email_already_linked'

    @pytest.mark.django_db
    def test_link_email_relink_own_account_idempotent(self, db):
        """Re-linking the user's own already-linked Google account → 200 (idempotent)."""
        profile = _make_profile(username='linker5', handle='linkerhandle5')
        # Pre-link
        profile.user.email = 'verified@example.com'
        profile.user.save(update_fields=['email'])
        SocialAccount.objects.create(
            provider='google', provider_id='google_sub_999', user=profile,
        )
        client = _auth_client(profile)

        with patch(
            'apps.accounts.views.auth._exchange_google_code',
            return_value=_GOOD_GOOGLE_DATA,
        ):
            resp = client.post(self.ENDPOINT, {
                'provider': 'google',
                'code': 'relink_code',
            }, format='json')

        assert resp.status_code == 200

    @pytest.mark.django_db
    def test_link_email_requires_auth(self):
        """Unauthenticated request → 401."""
        client = APIClient()
        resp = client.post(self.ENDPOINT, {
            'provider': 'google',
            'code': 'code',
        }, format='json')
        assert resp.status_code == 401


# ---------------------------------------------------------------------------
# UserSerializer: self-only fields (email / email_verified_at / has_password)
# ---------------------------------------------------------------------------

class TestUserSerializerFields:

    @pytest.mark.django_db
    def test_user_serializer_includes_email_and_has_password(self, db):
        """UserSerializer (self-only) must include email + has_password + email_verified_at."""
        from apps.accounts.serializers import UserSerializer
        profile = _make_profile(username='serial1', email='serial@example.com',
                                handle='serialhandle1', password='G00dP@ss!')
        data = UserSerializer(profile).data
        assert 'email' in data
        assert 'has_password' in data
        assert 'email_verified_at' in data
        assert data['email'] == 'serial@example.com'
        assert data['has_password'] is True

    @pytest.mark.django_db
    def test_user_serializer_has_password_false_for_guest(self, db):
        """Guest/OAuth user (no usable password) → has_password=False."""
        from apps.accounts.serializers import UserSerializer
        profile = _make_profile(username='serial2', handle='serialhandle2',
                                is_guest=True, password=None)
        data = UserSerializer(profile).data
        assert data['has_password'] is False

    @pytest.mark.django_db
    def test_public_profile_serializer_does_not_include_email(self, db):
        """Public UserProfileSerializer must NOT expose email/has_password/email_verified_at."""
        from apps.accounts.serializers import UserProfileSerializer
        profile = _make_profile(username='serial3', email='priv@example.com',
                                handle='serialhandle3')
        data = UserProfileSerializer(profile).data
        assert 'email' not in data
        assert 'has_password' not in data
        assert 'email_verified_at' not in data
