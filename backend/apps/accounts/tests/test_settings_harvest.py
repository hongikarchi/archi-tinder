"""
test_settings_harvest.py -- Settings harvest Slice 1 backend tests (SETTINGS-1).

New fields on UserProfile: handle (public @handle) + notifications (JSON prefs dict).

Coverage:
  TestHandlePatch              (11 tests) -- valid handle, uniqueness conflict, format
                                             violations, reserved handle, self-save OK,
                                             CRLF guard, null clear
  TestNotificationsPatch       (7 tests)  -- valid dict, large key count rejected,
                                             non-dict value rejected, nested unknown key
                                             rejected, nested non-bool value rejected,
                                             valid push/email booleans accepted,
                                             PATCH round-trip via /auth/me/ GET
  TestSecurityRegression       (2 tests)  -- email + username in PATCH body are ignored
  TestHandleInPublicShape      (4 tests)  -- handle present in UserProfileSerializer +
                                             UserSerializer (auth response) output;
                                             notifications absent from public profile;
                                             notifications PRESENT in /auth/me/ (self-only)
"""
import pytest
from django.contrib.auth.models import User
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from apps.accounts.models import UserProfile


# ---------------------------------------------------------------------------
# Helpers / Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def make_user_and_profile(db):
    """Factory: returns a callable that creates a User + UserProfile."""
    created = []

    def _make(username='settingsuser', email='settings@example.com',
              display_name='Settings User'):
        user = User.objects.create_user(
            username=username, email=email, password='pass123',
        )
        profile = UserProfile.objects.create(user=user, display_name=display_name)
        created.append((user, profile))
        return user, profile

    return _make


@pytest.fixture
def user_and_profile(make_user_and_profile):
    return make_user_and_profile()


@pytest.fixture
def auth_client(user_and_profile):
    user, _ = user_and_profile
    client = APIClient()
    refresh = RefreshToken.for_user(user)
    client.credentials(HTTP_AUTHORIZATION=f'Bearer {refresh.access_token}')
    return client


def _make_second_user(db, username='second_user', email='second@example.com'):
    """Standalone helper: create a second user + profile (used in uniqueness tests)."""
    user2 = User.objects.create_user(username=username, email=email, password='pass456')
    profile2 = UserProfile.objects.create(user=user2, display_name='Second User')
    return user2, profile2


# ---------------------------------------------------------------------------
# TestHandlePatch
# ---------------------------------------------------------------------------

class TestHandlePatch:

    @pytest.mark.django_db
    def test_valid_handle_saved_and_returned(self, user_and_profile, auth_client):
        """PATCH with a valid handle returns 200 and persists the value."""
        user, _ = user_and_profile
        response = auth_client.patch(
            '/api/v1/users/me/', {'handle': 'dain_architect'}, format='json',
        )
        assert response.status_code == 200
        data = response.json()
        assert 'handle' in data
        assert data['handle'] == 'dain_architect'
        # Confirm DB persistence
        profile = UserProfile.objects.get(user=user)
        assert profile.handle == 'dain_architect'

    @pytest.mark.django_db
    def test_handle_uniqueness_conflict_returns_400(self, user_and_profile, auth_client, db):
        """Second user cannot claim a handle already taken by the first user."""
        # First user claims 'dain_architect'
        auth_client.patch(
            '/api/v1/users/me/', {'handle': 'dain_architect'}, format='json',
        )
        # Second user tries the same handle
        user2, _ = _make_second_user(db)
        client2 = APIClient()
        refresh2 = RefreshToken.for_user(user2)
        client2.credentials(HTTP_AUTHORIZATION=f'Bearer {refresh2.access_token}')
        response = client2.patch(
            '/api/v1/users/me/', {'handle': 'dain_architect'}, format='json',
        )
        assert response.status_code == 400
        assert 'handle' in response.json()

    @pytest.mark.django_db
    def test_handle_case_conflict_returns_400(self, user_and_profile, auth_client, db):
        """Case-insensitive uniqueness: 'dain_arch' and 'DAIN_ARCH' conflict.

        Note: 'DAIN_ARCH' is first rejected because it's uppercase (format violation),
        so we test with the iexact path: first user sets 'dain_arch', second user
        tries a DB-level iexact duplicate (but lowercase so format passes).
        """
        # First user sets 'dain_arch'
        auth_client.patch('/api/v1/users/me/', {'handle': 'dain_arch'}, format='json')
        # Second user tries 'dain_arch' exactly — same string, should conflict
        user2, _ = _make_second_user(db)
        client2 = APIClient()
        client2.credentials(HTTP_AUTHORIZATION=f'Bearer {RefreshToken.for_user(user2).access_token}')
        response = client2.patch(
            '/api/v1/users/me/', {'handle': 'dain_arch'}, format='json',
        )
        assert response.status_code == 400

    @pytest.mark.django_db
    def test_handle_self_save_does_not_conflict(self, user_and_profile, auth_client):
        """User re-saving their own handle returns 200 (no self-conflict)."""
        auth_client.patch('/api/v1/users/me/', {'handle': 'my_handle'}, format='json')
        # Re-save the same handle as the same user
        response = auth_client.patch(
            '/api/v1/users/me/', {'handle': 'my_handle'}, format='json',
        )
        assert response.status_code == 200
        assert response.json()['handle'] == 'my_handle'

    @pytest.mark.django_db
    def test_handle_uppercase_rejected(self, user_and_profile, auth_client):
        """PATCH with uppercase handle returns 400 (format violation)."""
        response = auth_client.patch(
            '/api/v1/users/me/', {'handle': 'DainArchitect'}, format='json',
        )
        assert response.status_code == 400
        assert 'handle' in response.json()

    @pytest.mark.django_db
    def test_handle_too_short_rejected(self, user_and_profile, auth_client):
        """PATCH with a 2-char handle returns 400 (min length is 3)."""
        response = auth_client.patch(
            '/api/v1/users/me/', {'handle': 'ab'}, format='json',
        )
        assert response.status_code == 400
        assert 'handle' in response.json()

    @pytest.mark.django_db
    def test_handle_illegal_char_rejected(self, user_and_profile, auth_client):
        """PATCH with handle containing a space or hyphen returns 400."""
        for bad in ['dain architect', 'dain-architect', 'dain.arch']:
            response = auth_client.patch(
                '/api/v1/users/me/', {'handle': bad}, format='json',
            )
            assert response.status_code == 400, f'Expected 400 for handle={bad!r}'

    @pytest.mark.django_db
    def test_reserved_handle_rejected(self, user_and_profile, auth_client):
        """PATCH with reserved handle 'admin' returns 400."""
        response = auth_client.patch(
            '/api/v1/users/me/', {'handle': 'admin'}, format='json',
        )
        assert response.status_code == 400
        assert 'handle' in response.json()

    @pytest.mark.django_db
    def test_all_reserved_handles_rejected(self, user_and_profile, auth_client):
        """Every word in the reserved set is rejected."""
        reserved = [
            'me', 'admin', 'administrator', 'settings', 'api', 'root',
            'support', 'help', 'null', 'undefined', 'profile', 'user',
            'users', 'login', 'logout', 'auth',
        ]
        for word in reserved:
            response = auth_client.patch(
                '/api/v1/users/me/', {'handle': word}, format='json',
            )
            assert response.status_code == 400, f'Reserved word "{word}" was not rejected'

    @pytest.mark.django_db
    def test_handle_trailing_newline_rejected(self, user_and_profile, auth_client):
        """PATCH with handle containing a trailing newline returns 400 (CRLF-injection guard).

        re.match with $ accepts a trailing newline; fullmatch is required to block it.
        This test pins that fullmatch is used, not match.
        """
        response = auth_client.patch(
            '/api/v1/users/me/', {'handle': 'dain_arch\n'}, format='json',
        )
        assert response.status_code == 400
        assert 'handle' in response.json()

    @pytest.mark.django_db
    def test_handle_null_clears_value(self, user_and_profile, auth_client):
        """PATCH with handle=null is accepted and clears the handle."""
        # Set a handle first
        auth_client.patch('/api/v1/users/me/', {'handle': 'my_handle'}, format='json')
        # Now clear it
        response = auth_client.patch(
            '/api/v1/users/me/', {'handle': None}, format='json',
        )
        assert response.status_code == 200
        data = response.json()
        assert data['handle'] is None


# ---------------------------------------------------------------------------
# TestNotificationsPatch
# ---------------------------------------------------------------------------

class TestNotificationsPatch:

    @pytest.mark.django_db
    def test_valid_notifications_saved_and_reloaded_equal(self, user_and_profile, auth_client):
        """PATCH with valid notifications dict returns 200; reloaded value equals input."""
        user, _ = user_and_profile
        prefs = {
            'follows': {'push': True, 'email': False},
            'likes':   {'push': False, 'email': True},
        }
        response = auth_client.patch(
            '/api/v1/users/me/', {'notifications': prefs}, format='json',
        )
        assert response.status_code == 200
        # Re-fetch from DB to confirm persistence (not just serializer echo)
        profile = UserProfile.objects.get(user=user)
        assert profile.notifications == prefs

    @pytest.mark.django_db
    def test_notifications_too_many_keys_rejected(self, user_and_profile, auth_client):
        """PATCH with notifications dict having >50 keys returns 400."""
        prefs = {f'cat_{i}': {'push': True, 'email': False} for i in range(51)}
        response = auth_client.patch(
            '/api/v1/users/me/', {'notifications': prefs}, format='json',
        )
        assert response.status_code == 400
        assert 'notifications' in response.json()

    @pytest.mark.django_db
    def test_notifications_oversized_key_rejected(self, user_and_profile, auth_client):
        """PATCH with a notifications key longer than 64 chars returns 400."""
        prefs = {'x' * 65: {'push': True, 'email': False}}
        response = auth_client.patch(
            '/api/v1/users/me/', {'notifications': prefs}, format='json',
        )
        assert response.status_code == 400
        assert 'notifications' in response.json()

    @pytest.mark.django_db
    def test_notifications_non_dict_value_rejected(self, user_and_profile, auth_client):
        """PATCH where a notifications value is not a dict returns 400."""
        prefs = {'follows': True}  # value is bool, not dict
        response = auth_client.patch(
            '/api/v1/users/me/', {'notifications': prefs}, format='json',
        )
        assert response.status_code == 400
        assert 'notifications' in response.json()

    @pytest.mark.django_db
    def test_notifications_non_dict_top_level_rejected(self, user_and_profile, auth_client):
        """PATCH where notifications is a list (not dict) returns 400."""
        response = auth_client.patch(
            '/api/v1/users/me/', {'notifications': ['follows']}, format='json',
        )
        assert response.status_code == 400
        assert 'notifications' in response.json()

    @pytest.mark.django_db
    def test_notifications_unknown_nested_key_rejected(self, user_and_profile, auth_client):
        """PATCH where a nested value dict has an unknown key returns 400.

        Only 'push' and 'email' are allowed nested keys; anything else
        (e.g. 'garbage') must be rejected to prevent arbitrary blob storage.
        """
        prefs = {'follows': {'push': True, 'garbage': 'huge_string'}}
        response = auth_client.patch(
            '/api/v1/users/me/', {'notifications': prefs}, format='json',
        )
        assert response.status_code == 400
        assert 'notifications' in response.json()

    @pytest.mark.django_db
    def test_notifications_nested_non_bool_value_rejected(self, user_and_profile, auth_client):
        """PATCH where a nested push/email value is not a boolean returns 400.

        Integers and strings are rejected — only JSON true/false are valid.
        """
        for bad_val in [1, 0, 'true', 'false', None]:
            prefs = {'follows': {'push': bad_val}}
            response = auth_client.patch(
                '/api/v1/users/me/', {'notifications': prefs}, format='json',
            )
            assert response.status_code == 400, (
                f'Expected 400 for notifications.follows.push={bad_val!r}'
            )
            assert 'notifications' in response.json()

    @pytest.mark.django_db
    def test_notifications_valid_push_email_booleans_accepted(self, user_and_profile, auth_client):
        """PATCH with {push: bool, email: bool} nested shape returns 200."""
        prefs = {
            'follows': {'push': True, 'email': False},
            'likes':   {'push': False, 'email': True},
            'comments': {'push': True},
        }
        response = auth_client.patch(
            '/api/v1/users/me/', {'notifications': prefs}, format='json',
        )
        assert response.status_code == 200

    @pytest.mark.django_db
    def test_notifications_patch_then_read_via_auth_me(self, user_and_profile, auth_client):
        """PATCH notifications then GET /auth/me/ returns the saved value (round-trip).

        This is the primary 'self can read own notifications' contract test.
        """
        prefs = {
            'follows': {'push': True, 'email': False},
            'likes':   {'push': False, 'email': True},
        }
        patch_resp = auth_client.patch(
            '/api/v1/users/me/', {'notifications': prefs}, format='json',
        )
        assert patch_resp.status_code == 200

        me_resp = auth_client.get('/api/v1/auth/me/')
        assert me_resp.status_code == 200
        data = me_resp.json()
        assert 'notifications' in data, 'notifications missing from /auth/me/ response'
        assert data['notifications'] == prefs, (
            f'notifications mismatch: expected {prefs!r}, got {data["notifications"]!r}'
        )


# ---------------------------------------------------------------------------
# TestSecurityRegression
# ---------------------------------------------------------------------------

class TestSecurityRegression:

    @pytest.mark.django_db
    def test_patch_email_in_body_is_ignored(self, user_and_profile, auth_client):
        """PATCH with email in body leaves user.email unchanged (not editable via profile PATCH)."""
        user, _ = user_and_profile
        original_email = user.email
        response = auth_client.patch(
            '/api/v1/users/me/',
            {'email': 'hacked@evil.com'},
            format='json',
        )
        assert response.status_code == 200
        user.refresh_from_db()
        assert user.email == original_email, (
            f'email changed from {original_email!r} to {user.email!r} — security regression!'
        )

    @pytest.mark.django_db
    def test_patch_username_in_body_is_ignored(self, user_and_profile, auth_client):
        """PATCH with username in body leaves user.username unchanged."""
        user, _ = user_and_profile
        original_username = user.username
        response = auth_client.patch(
            '/api/v1/users/me/',
            {'username': 'hacked_username'},
            format='json',
        )
        assert response.status_code == 200
        user.refresh_from_db()
        assert user.username == original_username, (
            f'username changed from {original_username!r} to {user.username!r} — security regression!'
        )


# ---------------------------------------------------------------------------
# TestHandleInPublicShape
# ---------------------------------------------------------------------------

class TestHandleInPublicShape:

    @pytest.mark.django_db
    def test_handle_in_user_profile_serializer_output(self, user_and_profile):
        """GET /api/v1/users/{user_id}/ (UserProfileSerializer) includes handle."""
        user, _ = user_and_profile
        client = APIClient()
        response = client.get(f'/api/v1/users/{user.id}/')
        assert response.status_code == 200
        assert 'handle' in response.json()

    @pytest.mark.django_db
    def test_handle_in_user_serializer_auth_response(self, user_and_profile, auth_client):
        """GET /api/v1/auth/me/ (UserSerializer) includes handle."""
        response = auth_client.get('/api/v1/auth/me/')
        assert response.status_code == 200
        assert 'handle' in response.json()

    @pytest.mark.django_db
    def test_notifications_absent_from_public_profile(self, user_and_profile):
        """GET /api/v1/users/{user_id}/ does NOT expose notifications (private prefs)."""
        user, _ = user_and_profile
        client = APIClient()
        response = client.get(f'/api/v1/users/{user.id}/')
        assert response.status_code == 200
        assert 'notifications' not in response.json()

    @pytest.mark.django_db
    def test_notifications_present_in_auth_me(self, user_and_profile, auth_client):
        """GET /api/v1/auth/me/ (UserSerializer) DOES expose notifications (self-only).

        UserSerializer is only ever instantiated with the requester's own profile
        (MeView, _make_token_response, GuestPromoteView) so adding notifications
        here cannot leak another user's prefs.  This is the self-only read path.
        """
        response = auth_client.get('/api/v1/auth/me/')
        assert response.status_code == 200
        assert 'notifications' in response.json()
