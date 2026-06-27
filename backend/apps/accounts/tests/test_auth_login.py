"""
test_auth_login.py -- AUTH-LOGIN-1 + LOGIN-ONBOARD-1 backend tests.

E1: handle+password auth (register / login / set-password)
E2: email verify via OAuth linking (link-email)

Coverage matrix
  TestRegister            -- success (is_guest=True, handle==display_name),
                             consent_accepted required,
                             duplicate id rejected (iexact),
                             weak password rejected,
                             reserved id rejected,
                             Hangul id accepted,
                             whitespace in id rejected,
                             short id (1 char) rejected, 2 chars accepted
  TestPasswordLogin       -- correct creds, wrong password (generic),
                             nonexistent handle (same generic message),
                             OAuth user no password (generic),
                             response shape + JWT works,
                             NFC-normalized Hangul login matches stored NFC form
  TestSetPassword         -- first-set on guest (no current needed),
                             guest first-set then login works,
                             change requires correct current,
                             wrong current → 400,
                             weak new password → 400,
                             old refresh blacklisted + fresh pair returned (AUTH-CRITICAL),
                             throttle → 429 after 5 calls/min (AUTH-CRITICAL)
  TestLinkEmail           -- verified new email → set + SocialAccount
                             + email_verified_at populated + is_guest flipped False,
                             unverified → 400 unverified_email,
                             email already on another user → 400 reject,
                             provider_id already on another user → 400,
                             re-link own account is idempotent,
                             unauthenticated → 401
  TestCheckHandle         -- available id, taken id, invalid format, throttle
  TestUserSerializerFields -- email/has_password/email_verified_at
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
# E1: Register  (LOGIN-ONBOARD-1 updated)
# ---------------------------------------------------------------------------

class TestRegister:

    ENDPOINT = '/api/v1/auth/register/'

    def _post(self, payload, **kwargs):
        client = APIClient()
        return client.post(self.ENDPOINT, payload, format='json', **kwargs)

    def _base_payload(self, **overrides):
        base = {
            'id': 'newuser1',
            'password': 'Secur3P@ssw0rd!',
            'consent_accepted': True,
        }
        base.update(overrides)
        return base

    @pytest.mark.django_db
    def test_register_success_is_guest_true(self):
        """Successful register: is_guest=True, handle==display_name==id, consent_accepted_at set."""
        resp = self._post(self._base_payload())
        assert resp.status_code == 201
        data = resp.json()
        assert 'access' in data
        assert 'refresh' in data
        assert data['user']['handle'] == 'newuser1'
        # LOGIN-ONBOARD-1: is_guest=True (unverified account)
        profile = UserProfile.objects.get(handle='newuser1')
        assert profile.is_guest is True
        assert profile.display_name == 'newuser1'  # handle == display_name
        assert profile.consent_accepted_at is not None
        assert profile.user.has_usable_password() is True
        # User.username must NOT equal the id (internal stable key)
        assert profile.user.username != 'newuser1'
        assert profile.user.username.startswith('local_')

    @pytest.mark.django_db
    def test_register_consent_required(self):
        """Missing or false consent_accepted → 400 consent_required."""
        # Missing
        resp = self._post({'id': 'testid1', 'password': 'Secur3P@ssw0rd!'})
        assert resp.status_code == 400
        assert resp.json()['detail'] == 'consent_required'

        # Explicitly false
        resp = self._post({'id': 'testid2', 'password': 'Secur3P@ssw0rd!', 'consent_accepted': False})
        assert resp.status_code == 400

    @pytest.mark.django_db
    def test_register_hangul_id_accepted(self):
        """Hangul ID is accepted and stored NFC-normalized."""
        resp = self._post(self._base_payload(id='건축가김'))
        assert resp.status_code == 201
        data = resp.json()
        assert data['user']['handle'] == '건축가김'
        profile = UserProfile.objects.get(handle='건축가김')
        assert profile.display_name == '건축가김'
        assert profile.is_guest is True

    @pytest.mark.django_db
    def test_register_mixed_hangul_ascii_id_accepted(self):
        """Mixed Hangul+ASCII ID accepted."""
        resp = self._post(self._base_payload(id='dain_김'))
        assert resp.status_code == 201
        assert resp.json()['user']['handle'] == 'dain_김'

    @pytest.mark.django_db
    def test_register_space_in_id_rejected(self):
        """Space in ID → 400 (whitespace not allowed)."""
        resp = self._post(self._base_payload(id='my id'))
        assert resp.status_code == 400
        assert 'id' in resp.json()

    @pytest.mark.django_db
    def test_register_one_char_id_rejected(self):
        """1-char ID → 400 (min length is 2)."""
        resp = self._post(self._base_payload(id='a'))
        assert resp.status_code == 400
        assert 'id' in resp.json()

    @pytest.mark.django_db
    def test_register_two_char_id_accepted(self):
        """2-char ID → accepted (LOGIN-ONBOARD-1 min length is 2, was 3)."""
        resp = self._post(self._base_payload(id='ab'))
        assert resp.status_code == 201

    @pytest.mark.django_db
    def test_register_duplicate_id(self, db):
        """Duplicate ID (case-insensitive) → 400."""
        _make_profile(username='existing', handle='takenid')
        resp = self._post(self._base_payload(id='takenid'))
        assert resp.status_code == 400
        assert 'id' in resp.json()

    @pytest.mark.django_db
    def test_register_duplicate_id_case_insensitive(self, db):
        """Duplicate ID check is case-insensitive after NFC normalization."""
        _make_profile(username='existing', handle='takenid')
        # Same string different case — both rejected (uniqueness via iexact)
        resp = self._post(self._base_payload(id='TAKENID'))
        assert resp.status_code == 400

    @pytest.mark.django_db
    def test_register_weak_password(self):
        """Weak password → 400."""
        resp = self._post(self._base_payload(id='weakpwuser', password='123'))
        assert resp.status_code == 400
        assert 'password' in resp.json()

    @pytest.mark.django_db
    def test_register_reserved_id(self):
        """Reserved ID 'admin' → 400."""
        resp = self._post(self._base_payload(id='admin'))
        assert resp.status_code == 400
        assert 'id' in resp.json()

    @pytest.mark.django_db
    def test_register_with_affiliation_and_role(self):
        """Optional affiliation + onboarding_role stored on profile."""
        resp = self._post(self._base_payload(
            id='archi_user1',
            affiliation='Korea University',
            onboarding_role='student',
        ))
        assert resp.status_code == 201
        profile = UserProfile.objects.get(handle='archi_user1')
        assert profile.affiliation == 'Korea University'
        assert profile.onboarding_role == 'student'

    @pytest.mark.django_db
    def test_register_legacy_handle_field_still_accepted(self):
        """Legacy 'handle' field (instead of 'id') still works for backward compat."""
        client = APIClient()
        resp = client.post(self.ENDPOINT, {
            'handle': 'legacyhandle',
            'password': 'Secur3P@ssw0rd!',
            'consent_accepted': True,
        }, format='json')
        assert resp.status_code == 201


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
    def test_login_with_id_field(self, db):
        """Login also accepts 'id' instead of 'handle' (LOGIN-ONBOARD-1)."""
        _make_profile(username='idloginuser', handle='idloginhandle',
                      password='G00dP@ssword!', display_name='ID Login User')
        client = APIClient()
        resp = client.post(self.ENDPOINT, {
            'id': 'idloginhandle',
            'password': 'G00dP@ssword!',
        }, format='json')
        assert resp.status_code == 200

    @pytest.mark.django_db
    def test_login_nfc_normalized_hangul(self, db):
        """Hangul ID login works when client sends NFC-normalized form."""
        import unicodedata
        hangul_id = unicodedata.normalize('NFC', '건축가김')
        _make_profile(username='hangul_user', handle=hangul_id,
                      password='G00dP@ssword!', display_name=hangul_id)
        client = APIClient()
        resp = client.post(self.ENDPOINT, {
            'handle': hangul_id,
            'password': 'G00dP@ssword!',
        }, format='json')
        assert resp.status_code == 200

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
        _make_profile(username='oauthonly', handle='oauthhandle',
                      password=None)
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
        resp = client.post(self.ENDPOINT, {
            'password': 'N3wSecur3P@ss!',
        }, format='json')
        assert resp.status_code == 200

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
        old_refresh = RefreshToken.for_user(profile.user)
        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION=f'Bearer {old_refresh.access_token}')

        resp = client.post(self.ENDPOINT, {
            'password': 'Str0ngNewP@ss!',
        }, format='json')
        assert resp.status_code == 200

        data = resp.json()
        assert 'access' in data
        assert 'refresh' in data
        assert 'user' in data

        outstanding_qs = OutstandingToken.objects.filter(
            user=profile.user,
            jti=str(old_refresh['jti']),
        )
        assert outstanding_qs.exists(), 'OutstandingToken row for old refresh must exist'
        assert BlacklistedToken.objects.filter(token=outstanding_qs.first()).exists(), \
            'Old refresh token must be blacklisted after set-password'

        refresh_client = APIClient()
        refresh_resp = refresh_client.post(
            '/api/v1/auth/token/refresh/',
            {'refresh': str(old_refresh)},
            format='json',
        )
        assert refresh_resp.status_code == 401

        new_refresh_resp = refresh_client.post(
            '/api/v1/auth/token/refresh/',
            {'refresh': data['refresh']},
            format='json',
        )
        assert new_refresh_resp.status_code == 200

    @pytest.mark.django_db
    def test_set_password_throttle_429_after_five_calls(self, db):
        """More than 5 set-password calls per minute → 429 Too Many Requests."""
        profile = _make_profile(username='throttletest', handle='throttletesthandle',
                                password='OldSecur3P@ss!')
        client = _auth_client(profile)

        for _ in range(5):
            client.post(self.ENDPOINT, {
                'current_password': 'wrong',
                'password': 'Str0ngNewP@ss!',
            }, format='json')

        resp = client.post(self.ENDPOINT, {
            'current_password': 'wrong',
            'password': 'Str0ngNewP@ss!',
        }, format='json')
        assert resp.status_code == 429, \
            f'Expected 429 after 5 calls, got {resp.status_code}'


# ---------------------------------------------------------------------------
# E2: Link Email  (LOGIN-ONBOARD-1: also flips is_guest=False)
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
    def test_link_email_success_flips_is_guest_false(self, db):
        """Verified email → set User.email, SocialAccount, email_verified_at, is_guest=False."""
        # Start as is_guest=True (id+password unverified account)
        profile = _make_profile(username='linker1', handle='linkerhandle1',
                                is_guest=True)
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
        # LOGIN-ONBOARD-1: linking verified Google email flips is_guest=False
        assert profile.is_guest is False

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
# Check Handle (LOGIN-ONBOARD-1)
# ---------------------------------------------------------------------------

class TestCheckHandle:

    ENDPOINT = '/api/v1/auth/check-handle/'

    @pytest.mark.django_db
    def test_available_id(self):
        """Unused valid ID → available=True."""
        client = APIClient()
        resp = client.get(self.ENDPOINT, {'id': 'freehandle1'})
        assert resp.status_code == 200
        data = resp.json()
        assert data['available'] is True
        assert data['reason'] is None

    @pytest.mark.django_db
    def test_taken_id(self, db):
        """Taken ID → available=False."""
        _make_profile(username='taken_user', handle='takenid123')
        client = APIClient()
        resp = client.get(self.ENDPOINT, {'id': 'takenid123'})
        assert resp.status_code == 200
        data = resp.json()
        assert data['available'] is False
        assert data['reason'] is not None

    @pytest.mark.django_db
    def test_invalid_format_space(self):
        """ID with space → available=False with reason."""
        client = APIClient()
        resp = client.get(self.ENDPOINT, {'id': 'my id'})
        assert resp.status_code == 200
        assert resp.json()['available'] is False
        assert resp.json()['reason'] is not None

    @pytest.mark.django_db
    def test_hangul_available_id(self):
        """Hangul ID → available=True."""
        client = APIClient()
        resp = client.get(self.ENDPOINT, {'id': '건축가김'})
        assert resp.status_code == 200
        assert resp.json()['available'] is True

    @pytest.mark.django_db
    def test_reserved_id(self):
        """Reserved ID 'admin' → available=False."""
        client = APIClient()
        resp = client.get(self.ENDPOINT, {'id': 'admin'})
        assert resp.status_code == 200
        assert resp.json()['available'] is False

    @pytest.mark.django_db
    def test_check_handle_throttle(self):
        """Exceeding 20 requests/min → 429."""
        client = APIClient()
        for _ in range(20):
            client.get(self.ENDPOINT, {'id': 'somehandle'})
        resp = client.get(self.ENDPOINT, {'id': 'somehandle'})
        assert resp.status_code == 429, (
            f'Expected 429 after 20 requests, got {resp.status_code}'
        )


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
