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

    with patch('apps.accounts.views.auth._exchange_google_code', return_value=_FAKE_GOOGLE_DATA):
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

    with patch('apps.accounts.views.auth._exchange_google_code', return_value=_FAKE_GOOGLE_DATA):
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

    with patch('apps.accounts.views.auth._exchange_google_code', return_value=_FAKE_GOOGLE_DATA):
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

    with patch('apps.accounts.views.auth._exchange_google_code', return_value=_FAKE_GOOGLE_DATA):
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

    with patch('apps.accounts.views.auth._exchange_google_code', return_value=_FAKE_GOOGLE_DATA):
        resp = client.post(
            '/api/v1/auth/promote/',
            {'provider': 'google', 'code': 'mock_code'},
            format='json',
        )

    assert resp.status_code == 400
    assert resp.json()['detail'] == 'not_a_guest'


# ---------------------------------------------------------------------------
# 12-18. merge_guest_into_target collision tests
# ---------------------------------------------------------------------------
# These tests call the helper directly — no Google mock / token-blacklist noise.

def _make_follow(follower, followee):
    """Create a Follow row directly (bypasses signals for counter manipulation)."""
    from apps.social.models import Follow
    return Follow.objects.create(follower=follower, followee=followee)


def _make_architect_follow(follower, architect_id='arch_000001'):
    from apps.social.models import ArchitectFollow
    return ArchitectFollow.objects.create(follower=follower, architect_id=architect_id)


def _make_reaction(user, project):
    from apps.social.models import Reaction
    return Reaction.objects.create(user=user, project=project)


def _make_project(user, name='Test Board'):
    from apps.recommendation.models import Project
    return Project.objects.create(user=user, name=name)


# (a) Follow follower-role dedup: guest + target both follow user X → no dup, no 500
@pytest.mark.django_db
def test_merge_follow_follower_dedup(db):
    """Guest and target both follow user X → after merge target follows X once."""
    from apps.accounts.merge import merge_guest_into_target
    from apps.social.models import Follow

    guest = _make_guest(display_name='GuestA')
    target = _make_verified(email='target_a@example.com')
    third = _make_verified(email='third_a@example.com')

    _make_follow(guest, third)    # guest→third
    _make_follow(target, third)   # target→third (collision)

    merge_guest_into_target(guest, target)

    # Exactly one Follow row: target→third
    rows = Follow.objects.filter(follower=target, followee=third)
    assert rows.count() == 1

    # No guest rows remain
    assert Follow.objects.filter(follower=guest).count() == 0

    # Counter-cache correct
    target.refresh_from_db()
    assert target.following_count == Follow.objects.filter(follower=target).count()


# (b) Follow followee-role dedup: someone follows both guest + target → no dup
@pytest.mark.django_db
def test_merge_follow_followee_dedup(db):
    """User Y follows both guest and target → after merge only one follower row."""
    from apps.accounts.merge import merge_guest_into_target
    from apps.social.models import Follow

    guest = _make_guest(display_name='GuestB')
    target = _make_verified(email='target_b@example.com')
    fan = _make_verified(email='fan_b@example.com')

    _make_follow(fan, guest)     # fan→guest
    _make_follow(fan, target)    # fan→target (collision)

    merge_guest_into_target(guest, target)

    rows = Follow.objects.filter(follower=fan, followee=target)
    assert rows.count() == 1

    assert Follow.objects.filter(followee=guest).count() == 0

    target.refresh_from_db()
    assert target.follower_count == Follow.objects.filter(followee=target).count()


# (c) Reaction dedup: guest + target both reacted to same project → no dup, no 500
@pytest.mark.django_db
def test_merge_reaction_dedup(db):
    """Guest and target both reacted to project P → after merge one reaction."""
    from apps.accounts.merge import merge_guest_into_target
    from apps.social.models import Reaction

    guest = _make_guest(display_name='GuestC')
    target = _make_verified(email='target_c@example.com')
    project = _make_project(target, name='Shared Project')

    _make_reaction(guest, project)
    _make_reaction(target, project)

    merge_guest_into_target(guest, target)

    rows = Reaction.objects.filter(user=target, project=project)
    assert rows.count() == 1

    assert Reaction.objects.filter(user=guest).count() == 0


# (d) ArchitectFollow merge + dedup
@pytest.mark.django_db
def test_merge_architect_follow(db):
    """Guest ArchitectFollows are transferred; duplicates are dropped."""
    from apps.accounts.merge import merge_guest_into_target
    from apps.social.models import ArchitectFollow

    guest = _make_guest(display_name='GuestD')
    target = _make_verified(email='target_d@example.com')

    _make_architect_follow(guest, 'arch_000001')   # collision
    _make_architect_follow(guest, 'arch_000002')   # unique → reassign
    _make_architect_follow(target, 'arch_000001')  # target already has this

    merge_guest_into_target(guest, target)

    # arch_000001: one row (target's), no dup
    assert ArchitectFollow.objects.filter(follower=target, architect_id='arch_000001').count() == 1
    # arch_000002 transferred
    assert ArchitectFollow.objects.filter(follower=target, architect_id='arch_000002').count() == 1
    # No guest rows remain
    assert ArchitectFollow.objects.filter(follower=guest).count() == 0


# (e) liked_building_ids: guest-first union, deduped, capped at 200
@pytest.mark.django_db
def test_merge_liked_building_ids(db):
    """liked_building_ids: guest-first, deduped, within 200 cap."""
    from apps.accounts.merge import merge_guest_into_target

    guest = _make_guest(display_name='GuestE')
    target = _make_verified(email='target_e@example.com')

    guest.liked_building_ids = ['g1', 'g2', 'shared']
    guest.save(update_fields=['liked_building_ids'])
    target.liked_building_ids = ['shared', 't1']
    target.save(update_fields=['liked_building_ids'])

    merge_guest_into_target(guest, target)

    target.refresh_from_db()
    result = target.liked_building_ids
    # Guest-first order; shared deduplicated; t1 at end
    assert result == ['g1', 'g2', 'shared', 't1']
    assert len(result) <= 200


@pytest.mark.django_db
def test_merge_liked_building_ids_cap(db):
    """liked_building_ids cap: over-200 list is trimmed to 200."""
    from apps.accounts.merge import merge_guest_into_target

    guest = _make_guest(display_name='GuestE2')
    target = _make_verified(email='target_e2@example.com')

    # 150 guest + 100 target (50 overlap) = 200 unique after dedup → 200
    guest.liked_building_ids = [f'g{i}' for i in range(150)]
    target.liked_building_ids = [f'g{i}' for i in range(100, 200)]  # 100-199 overlap 100-149
    guest.save(update_fields=['liked_building_ids'])
    target.save(update_fields=['liked_building_ids'])

    merge_guest_into_target(guest, target)

    target.refresh_from_db()
    assert len(target.liked_building_ids) <= 200


# (f) Self-follow guard: guest follows target → after merge no self-follow
@pytest.mark.django_db
def test_merge_self_follow_guard(db):
    """Guest follows target → that row is deleted, not reassigned (no self-follow)."""
    from apps.accounts.merge import merge_guest_into_target
    from apps.social.models import Follow

    guest = _make_guest(display_name='GuestF')
    target = _make_verified(email='target_f@example.com')

    _make_follow(guest, target)  # guest→target: would become target→target

    merge_guest_into_target(guest, target)

    # No self-follow row
    assert Follow.objects.filter(follower=target, followee=target).count() == 0


# (g) Existing no-collision path still works end-to-end via promote endpoint
@pytest.mark.django_db
def test_merge_no_collision_via_promote_endpoint(db):
    """Guest with boards + unique follows → merge into target with no shared data.

    Verifies the full promote endpoint still works after the merge.py refactor.
    """
    from apps.recommendation.models import Project
    from apps.social.models import Follow, ArchitectFollow

    target_profile = _make_verified(email=_FAKE_GOOGLE_DATA['email'])
    target_social = target_profile.social_accounts.first()
    target_social.provider_id = _FAKE_GOOGLE_DATA['provider_id']
    target_social.save()

    guest_profile = _make_guest()
    guest_user_id = guest_profile.user.id
    client = _auth_client_for(guest_profile)

    # Unique data on guest (no collisions)
    Project.objects.create(user=guest_profile, name='Guest Board A')
    third_user = _make_verified(email='third_nc@example.com')
    _make_follow(guest_profile, third_user)
    _make_architect_follow(guest_profile, 'arch_999001')

    with patch('apps.accounts.views.auth._exchange_google_code', return_value=_FAKE_GOOGLE_DATA):
        resp = client.post(
            '/api/v1/auth/promote/',
            {'provider': 'google', 'code': 'mock_code'},
            format='json',
        )

    assert resp.status_code == 200, resp.data
    data = resp.json()
    assert data['merged'] is True
    assert data['user']['user_id'] == target_profile.user.id

    # Guest deleted
    from django.contrib.auth.models import User as DjangoUser
    assert not DjangoUser.objects.filter(id=guest_user_id).exists()

    # Project migrated
    assert Project.objects.filter(user=target_profile, name='Guest Board A').exists()

    # Follow migrated
    assert Follow.objects.filter(follower=target_profile, followee=third_user).exists()

    # ArchitectFollow migrated
    assert ArchitectFollow.objects.filter(
        follower=target_profile, architect_id='arch_999001',
    ).exists()
