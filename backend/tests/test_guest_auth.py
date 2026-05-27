"""test_guest_auth.py — FULL-LOGIN-REDESIGN-1 (PR 1) integration tests.

Covers:
  1. test_guest_create_sets_consent_timestamp
  2. test_guest_create_rejects_missing_consent
  3. test_guest_throttle_3_per_min
  4. test_jwt_has_is_guest_claim
  5. test_verify_gate_blocks_4th_board
  6. test_verify_gate_allows_3_boards
  7. test_verify_gate_skipped_for_verified
  8. test_promote_branch_2_in_place_transform
  9. test_promote_branch_1_merge_cross_device
  10. test_promote_blacklists_guest_refresh
  11. test_promote_rejects_non_guest

Fixtures used from backend/conftest.py: api_client, user_profile, auth_client.
"""
import pytest
from unittest.mock import patch
from django.contrib.auth.models import User
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken
import jwt as _jwt  # PyJWT installed via djangorestframework-simplejwt dependency


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_guest(display_name='Tester', role='student'):
    """Create a guest User + UserProfile directly (bypasses throttle)."""
    from django.utils import timezone
    from apps.accounts.models import UserProfile
    import uuid
    django_user = User.objects.create_user(
        username=f'guest_{uuid.uuid4().hex}',
        email='',
    )
    django_user.set_unusable_password()
    django_user.save()
    profile = UserProfile.objects.create(
        user=django_user,
        display_name=display_name,
        is_guest=True,
        onboarding_role=role,
        consent_accepted_at=timezone.now(),
        consent_policy_version='1.0',
    )
    return profile


def _make_verified(email='verified@example.com', display_name='Verified'):
    """Create a verified User + UserProfile + SocialAccount."""
    from apps.accounts.models import UserProfile, SocialAccount
    import uuid
    django_user = User.objects.create_user(
        username=email,
        email=email,
    )
    profile = UserProfile.objects.create(
        user=django_user,
        display_name=display_name,
        is_guest=False,
    )
    SocialAccount.objects.create(
        user=profile,
        provider='google',
        provider_id=f'google_{uuid.uuid4().hex}',
    )
    return profile


def _auth_client_for(profile):
    client = APIClient()
    refresh = RefreshToken.for_user(profile.user)
    client.credentials(HTTP_AUTHORIZATION=f'Bearer {str(refresh.access_token)}')
    return client


GUEST_PAYLOAD = {
    'display_name': 'Tester',
    'onboarding_role': 'student',
    'consent_accepted': True,
    'consent_policy_version': '1.0',
}

_FAKE_GOOGLE_DATA = {
    'provider_id': 'google_promote_sub_001',
    'email': 'promote@example.com',
    'display_name': 'Promote User',
    'avatar_url': '',
}


# ---------------------------------------------------------------------------
# 1. Consent timestamp saved
# ---------------------------------------------------------------------------

@pytest.mark.django_db
def test_guest_create_sets_consent_timestamp(api_client):
    response = api_client.post('/api/v1/auth/guest/', GUEST_PAYLOAD, format='json')
    assert response.status_code == 200, response.data
    data = response.json()
    assert 'access' in data
    assert 'refresh' in data
    assert data['user']['is_guest'] is True

    # Verify consent_accepted_at is set in the DB
    from apps.accounts.models import UserProfile
    user_id = data['user']['user_id']
    profile = UserProfile.objects.get(user__id=user_id)
    assert profile.consent_accepted_at is not None
    assert profile.consent_policy_version == '1.0'


# ---------------------------------------------------------------------------
# 2. Missing / false consent rejected
# ---------------------------------------------------------------------------

@pytest.mark.django_db
def test_guest_create_rejects_missing_consent(api_client):
    # No consent_accepted key at all
    resp = api_client.post(
        '/api/v1/auth/guest/',
        {'display_name': 'Tester', 'onboarding_role': 'student'},
        format='json',
    )
    assert resp.status_code == 400
    assert resp.json()['detail'] == 'consent_required'


@pytest.mark.django_db
def test_guest_create_rejects_false_consent(api_client):
    resp = api_client.post(
        '/api/v1/auth/guest/',
        {**GUEST_PAYLOAD, 'consent_accepted': False},
        format='json',
    )
    assert resp.status_code == 400
    assert resp.json()['detail'] == 'consent_required'


@pytest.mark.django_db
def test_guest_create_rejects_string_consent(api_client):
    """String 'true' must be rejected — only JSON boolean true passes (Fix B)."""
    resp = api_client.post(
        '/api/v1/auth/guest/',
        {**GUEST_PAYLOAD, 'consent_accepted': 'true'},
        format='json',
    )
    assert resp.status_code == 400
    assert resp.json()['detail'] == 'consent_required'


# ---------------------------------------------------------------------------
# 3. Throttle: 4th request within 60 s → 429
# ---------------------------------------------------------------------------

@pytest.mark.django_db
def test_guest_throttle_3_per_min(api_client):
    """Throttle kicks in on the 4th request from the same IP within the window.

    DRF throttle uses Django cache for counting.  The autouse _clear_cache
    fixture resets the cache between test functions, so this test sees a fresh
    window.  Three requests must succeed; the fourth must return 429.
    """
    for i in range(3):
        resp = api_client.post('/api/v1/auth/guest/', GUEST_PAYLOAD, format='json')
        assert resp.status_code == 200, f'request {i+1} failed: {resp.data}'

    resp = api_client.post('/api/v1/auth/guest/', GUEST_PAYLOAD, format='json')
    assert resp.status_code == 429


# ---------------------------------------------------------------------------
# 4. JWT access token carries is_guest claim
# ---------------------------------------------------------------------------

@pytest.mark.django_db
def test_jwt_has_is_guest_claim(api_client):
    resp = api_client.post('/api/v1/auth/guest/', GUEST_PAYLOAD, format='json')
    assert resp.status_code == 200
    access_token = resp.json()['access']
    # Decode without verification — we only need to inspect the payload
    payload = _jwt.decode(access_token, options={'verify_signature': False})
    assert 'is_guest' in payload
    assert payload['is_guest'] is True


# ---------------------------------------------------------------------------
# 5. Verify gate blocks 4th board
# ---------------------------------------------------------------------------

@pytest.mark.django_db
def test_verify_gate_blocks_4th_board(db):
    """Guest with 3 projects → POST /projects/ 4th time → 403 verify_required."""
    from apps.recommendation.models import Project
    profile = _make_guest()
    client = _auth_client_for(profile)

    for i in range(3):
        Project.objects.create(
            user=profile,
            name=f'Board {i}',
        )

    resp = client.post(
        '/api/v1/projects/',
        {'name': 'Board 4', 'visibility': 'private'},
        format='json',
    )
    assert resp.status_code == 403
    data = resp.json()
    assert data['detail'] == 'verify_required'
    assert data['reason'] == 'board_limit_reached'
    assert data['limit'] == 3


# ---------------------------------------------------------------------------
# 6. Verify gate allows 3 boards
# ---------------------------------------------------------------------------

@pytest.mark.django_db
def test_verify_gate_allows_3_boards(db):
    """Guest creating exactly 3 boards → all succeed."""
    profile = _make_guest()
    client = _auth_client_for(profile)

    for i in range(3):
        resp = client.post(
            '/api/v1/projects/',
            {'name': f'Board {i}', 'visibility': 'private'},
            format='json',
        )
        assert resp.status_code == 201, f'board {i} failed: {resp.data}'


# ---------------------------------------------------------------------------
# 7. Verify gate skipped for verified users
# ---------------------------------------------------------------------------

@pytest.mark.django_db
def test_verify_gate_skipped_for_verified(db):
    """Verified user with 3+ boards can create more freely."""
    from apps.recommendation.models import Project
    profile = _make_verified()
    client = _auth_client_for(profile)

    for i in range(3):
        Project.objects.create(user=profile, name=f'Existing Board {i}')

    resp = client.post(
        '/api/v1/projects/',
        {'name': 'Board 4', 'visibility': 'private'},
        format='json',
    )
    assert resp.status_code == 201


# ---------------------------------------------------------------------------
# 8. Promote branch 2 — in-place transform
# ---------------------------------------------------------------------------

@pytest.mark.django_db
def test_promote_branch_2_in_place_transform(db):
    """Guest with 3 boards + Google code → in-place upgrade.

    user_id preserved, is_guest=False, SocialAccount created,
    board count unchanged.
    """
    from apps.recommendation.models import Project
    from apps.accounts.models import SocialAccount

    profile = _make_guest()
    original_user_id = profile.user.id
    client = _auth_client_for(profile)

    for i in range(3):
        Project.objects.create(user=profile, name=f'Board {i}')

    with patch('apps.accounts.views._exchange_google_code', return_value=_FAKE_GOOGLE_DATA):
        resp = client.post(
            '/api/v1/auth/promote/',
            {'provider': 'google', 'code': 'mock_code'},
            format='json',
        )

    assert resp.status_code == 200, resp.data
    data = resp.json()
    assert data['promoted'] is True
    assert data['merged'] is False
    assert data['user']['is_guest'] is False
    # user_id preserved (in-place transform, same row)
    assert data['user']['user_id'] == original_user_id

    # Refresh from DB
    profile.refresh_from_db()
    assert profile.is_guest is False
    assert Project.objects.filter(user=profile).count() == 3

    assert SocialAccount.objects.filter(
        provider='google',
        provider_id=_FAKE_GOOGLE_DATA['provider_id'],
    ).exists()


# ---------------------------------------------------------------------------
# 9. Promote branch 1 — merge cross-device collision
# ---------------------------------------------------------------------------

@pytest.mark.django_db
def test_promote_branch_1_merge_cross_device(db):
    """Guest with 2 boards + Google code where target already exists.

    Expected: boards reassigned to target, guest user deleted,
    target user JWT returned with is_guest=False.
    """
    from apps.recommendation.models import Project

    # Target user already verified with the same Google identity
    target_profile = _make_verified(email=_FAKE_GOOGLE_DATA['email'])
    target_social = target_profile.social_accounts.first()
    # Override provider_id to match _FAKE_GOOGLE_DATA
    target_social.provider_id = _FAKE_GOOGLE_DATA['provider_id']
    target_social.save()

    guest_profile = _make_guest()
    guest_user_id = guest_profile.user.id
    client = _auth_client_for(guest_profile)

    Project.objects.create(user=guest_profile, name='Guest Board A')
    Project.objects.create(user=guest_profile, name='Guest Board B')

    with patch('apps.accounts.views._exchange_google_code', return_value=_FAKE_GOOGLE_DATA):
        resp = client.post(
            '/api/v1/auth/promote/',
            {'provider': 'google', 'code': 'mock_code'},
            format='json',
        )

    assert resp.status_code == 200, resp.data
    data = resp.json()
    assert data['promoted'] is True
    assert data['merged'] is True
    assert data['user']['user_id'] == target_profile.user.id

    # Guest user deleted
    assert not User.objects.filter(id=guest_user_id).exists()

    # Boards migrated to target
    assert Project.objects.filter(user=target_profile).count() == 2


# ---------------------------------------------------------------------------
# 10. Promote blacklists old guest refresh token
# ---------------------------------------------------------------------------

@pytest.mark.django_db
def test_promote_blacklists_guest_refresh(db):
    """Branch-2 (in-place): old refresh token is immediately blacklisted after promote.

    Fix F: assert directly via DB after promote, not via a subsequent
    TokenRefreshView call (which only tested rotation blacklisting, not Branch-2
    explicit blacklisting).
    """
    from rest_framework_simplejwt.token_blacklist.models import (
        OutstandingToken, BlacklistedToken,
    )

    profile = _make_guest()
    refresh = RefreshToken.for_user(profile.user)
    guest_user_obj = profile.user

    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f'Bearer {str(refresh.access_token)}')

    with patch('apps.accounts.views._exchange_google_code', return_value=_FAKE_GOOGLE_DATA):
        promote_resp = client.post(
            '/api/v1/auth/promote/',
            {'provider': 'google', 'code': 'mock_code'},
            format='json',
        )

    assert promote_resp.status_code == 200, promote_resp.data

    # Immediately after promote, old refresh must be in blacklist (Fix D).
    # Branch-2 keeps guest_user_obj alive (in-place transform), so filter by user.
    old_outstanding = OutstandingToken.objects.filter(user=guest_user_obj).first()
    assert old_outstanding is not None, 'OutstandingToken row for guest user not found'
    assert BlacklistedToken.objects.filter(token=old_outstanding).exists(), \
        'Branch-2 promote did NOT blacklist old guest refresh token'


@pytest.mark.django_db
def test_promote_branch_1_blacklists_guest_refresh(db):
    """Branch-1 (cross-device merge): old guest refresh token is immediately blacklisted.

    Branch-1 deletes the guest user, so OutstandingToken.user becomes NULL.
    Query by jti instead of user.
    """
    from rest_framework_simplejwt.token_blacklist.models import (
        OutstandingToken, BlacklistedToken,
    )

    # Target user already verified with the same Google identity
    target_profile = _make_verified(email=_FAKE_GOOGLE_DATA['email'])
    target_social = target_profile.social_accounts.first()
    target_social.provider_id = _FAKE_GOOGLE_DATA['provider_id']
    target_social.save()

    guest_profile = _make_guest()
    guest_refresh = RefreshToken.for_user(guest_profile.user)
    jti = guest_refresh.get('jti')

    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f'Bearer {str(guest_refresh.access_token)}')

    with patch('apps.accounts.views._exchange_google_code', return_value=_FAKE_GOOGLE_DATA):
        promote_resp = client.post(
            '/api/v1/auth/promote/',
            {'provider': 'google', 'code': 'mock_code'},
            format='json',
        )

    assert promote_resp.status_code == 200, promote_resp.data

    # Guest user deleted in Branch-1; OutstandingToken.user is SET_NULL.
    # Query by jti to locate the outstanding token row.
    ot = OutstandingToken.objects.filter(jti=jti).first()
    assert ot is not None, 'OutstandingToken row not found by jti'
    assert BlacklistedToken.objects.filter(token=ot).exists(), \
        'Branch-1 promote did NOT blacklist old guest refresh token'


# ---------------------------------------------------------------------------
# 11. Promote rejects non-guest
# ---------------------------------------------------------------------------

@pytest.mark.django_db
def test_promote_rejects_non_guest(db):
    """Verified user calling promote → 400 not_a_guest."""
    profile = _make_verified()
    client = _auth_client_for(profile)

    with patch('apps.accounts.views._exchange_google_code', return_value=_FAKE_GOOGLE_DATA):
        resp = client.post(
            '/api/v1/auth/promote/',
            {'provider': 'google', 'code': 'mock_code'},
            format='json',
        )

    assert resp.status_code == 400
    assert resp.json()['detail'] == 'not_a_guest'
