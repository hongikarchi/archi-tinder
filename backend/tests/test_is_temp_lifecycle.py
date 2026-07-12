"""
test_is_temp_lifecycle.py — FULL-ONBOARDING-2 is_temp lifecycle integration tests.

Coverage (DB-backed tests using @pytest.mark.django_db):
1. PATCH {is_temp: true} on a permanent board → 400 one-way message
2. PATCH {is_temp: false} promote on temp board works (non-guest)
3. Guest with 3 permanent boards promoting a temp board → 400 limit
4. Both list views exclude is_temp=True rows
5. Guest with 1 temp + 2 permanent boards: discovery guest-count checks pass (no false 403)

Pure unit tests (filter kwarg assertions) are in:
  apps/recommendation/tests/test_is_temp_data_filters.py
"""
import pytest
from unittest.mock import patch, MagicMock

from django.contrib.auth.models import User

from apps.accounts.models import UserProfile
from apps.recommendation.models import Project


# ---------------------------------------------------------------------------
# Helpers / fixtures
# ---------------------------------------------------------------------------

def _make_guest_profile(db, username='guestuser', email='guest@test.com'):
    """Create a guest UserProfile (is_guest=True)."""
    u = User.objects.create_user(username=username, email=email)
    p = UserProfile.objects.create(user=u, display_name='Guest', is_guest=True)
    return p


def _auth_client_for(profile):
    from rest_framework.test import APIClient
    from rest_framework_simplejwt.tokens import RefreshToken
    client = APIClient()
    refresh = RefreshToken.for_user(profile.user)
    client.credentials(HTTP_AUTHORIZATION=f'Bearer {refresh.access_token}')
    return client


# ---------------------------------------------------------------------------
# 1. PATCH {is_temp: true} on permanent board → 400
# ---------------------------------------------------------------------------

@pytest.mark.django_db
def test_patch_is_temp_true_on_permanent_board_rejected(user_profile, auth_client):
    """Setting is_temp=True on a permanent board must return 400 with one-way message."""
    board = Project.objects.create(user=user_profile, name='Permanent Board', is_temp=False)
    resp = auth_client.patch(
        f'/api/v1/projects/{board.project_id}/',
        {'is_temp': True},
        format='json',
    )
    assert resp.status_code == 400
    body = str(resp.json())
    assert 'one-way' in body or 'is_temp' in body


# ---------------------------------------------------------------------------
# 2. PATCH {is_temp: false} promote works for non-guest
# ---------------------------------------------------------------------------

@pytest.mark.django_db
def test_patch_is_temp_false_promote_succeeds_for_non_guest(user_profile, auth_client):
    """Non-guest owner can promote a temp board to permanent."""
    board = Project.objects.create(user=user_profile, name='Temp Board', is_temp=True)
    resp = auth_client.patch(
        f'/api/v1/projects/{board.project_id}/',
        {'is_temp': False},
        format='json',
    )
    assert resp.status_code == 200
    board.refresh_from_db()
    assert board.is_temp is False


# ---------------------------------------------------------------------------
# 3. Guest with 3 permanent boards promoting temp → 400
# ---------------------------------------------------------------------------

@pytest.mark.django_db
def test_guest_promote_temp_board_rejected_at_limit(db):
    """Guest who already has 3 permanent boards cannot promote a temp board."""
    guest = _make_guest_profile(db, username='g_promote', email='g_promote@test.com')
    client = _auth_client_for(guest)

    # 3 permanent boards
    for i in range(3):
        Project.objects.create(user=guest, name=f'Perm {i}', is_temp=False)

    # 1 temp board (Taste session flow)
    temp_board = Project.objects.create(user=guest, name='Temp Taste', is_temp=True)

    resp = client.patch(
        f'/api/v1/projects/{temp_board.project_id}/',
        {'is_temp': False},
        format='json',
    )
    assert resp.status_code == 403
    body = resp.json()
    assert body.get('detail') == 'verify_required'
    assert body.get('reason') == 'board_limit_reached'
    assert body.get('limit') == 3

    # Board must remain temp
    temp_board.refresh_from_db()
    assert temp_board.is_temp is True


# ---------------------------------------------------------------------------
# 4. Both list views exclude is_temp=True rows
# ---------------------------------------------------------------------------

@pytest.mark.django_db
def test_project_list_view_excludes_temp_boards(user_profile, auth_client):
    """GET /api/v1/projects/ must not include is_temp=True boards."""
    Project.objects.create(user=user_profile, name='Permanent', is_temp=False)
    Project.objects.create(user=user_profile, name='Temp', is_temp=True)

    resp = auth_client.get('/api/v1/projects/')
    assert resp.status_code == 200
    data = resp.json()
    names = [r['name'] for r in data['results']]
    assert 'Permanent' in names
    assert 'Temp' not in names


@pytest.mark.django_db
def test_user_projects_list_view_excludes_temp_boards(user_profile, auth_client):
    """GET /api/v1/users/{id}/projects/ must not include is_temp=True boards."""
    Project.objects.create(user=user_profile, name='Public Board', is_temp=False, visibility='public')
    Project.objects.create(user=user_profile, name='Temp Board', is_temp=True, visibility='public')

    resp = auth_client.get(f'/api/v1/users/{user_profile.user.id}/projects/')
    assert resp.status_code == 200
    data = resp.json()
    names = [r['name'] for r in data['results']]
    assert 'Public Board' in names
    assert 'Temp Board' not in names


# ---------------------------------------------------------------------------
# 5. Guest with 1 temp + 2 permanent boards passes discovery guest-count
# ---------------------------------------------------------------------------

@pytest.mark.django_db
def test_guest_with_temp_board_not_blocked_by_discovery_guest_limit(db):
    """Guest who has 1 temp + 2 permanent boards (total 3) should NOT be blocked
    at the discovery feedback guest-count check because temp boards are excluded.

    The guest-count branch runs when draft is None (draft_id omitted or not found).
    With is_temp=False filter: count=2 < 3 → no 403 → create_discovery_draft runs.
    Without the fix: count=3 (temp counted) → 403 (regression the fix prevents).

    We omit draft_id so draft is always None, forcing the branch to execute.
    """
    guest = _make_guest_profile(db, username='g_disc', email='g_disc@test.com')
    client = _auth_client_for(guest)

    # 2 permanent + 1 temp board — total 3 boards, but only 2 permanent
    Project.objects.create(user=guest, name='Perm1', is_temp=False)
    Project.objects.create(user=guest, name='Perm2', is_temp=False)
    Project.objects.create(user=guest, name='Temp', is_temp=True)

    # Patch buildings DB cursor so the view finds the building.
    # This also patches create_discovery_draft so we don't actually write a board.
    mock_cursor_ctx = MagicMock()
    mock_cursor_ctx.__enter__ = MagicMock(return_value=mock_cursor_ctx)
    mock_cursor_ctx.__exit__ = MagicMock(return_value=False)
    mock_cursor_ctx.fetchone = MagicMock(return_value=(1,))

    fake_draft = Project.objects.create(user=guest, name='new_draft', is_temp=False)

    with patch(
        'apps.recommendation.views.discovery._dj_connections',
        new_callable=MagicMock,
    ) as mock_conns:
        mock_conns.__getitem__.return_value.cursor.return_value = mock_cursor_ctx
        with patch(
            'apps.recommendation.views.discovery.create_discovery_draft',
            return_value=fake_draft,
        ):
            # No draft_id → draft is None → guest-count branch executes
            resp = client.post(
                '/api/v1/discovery/feedback/',
                {
                    'canonical_bld_id': 'bld_000001',
                    'action': 'like',
                    # draft_id intentionally omitted so draft=None forces count check
                },
                format='json',
            )

    # Must NOT be 403: is_temp=False count is 2 (temp board excluded), so 2 < 3
    assert resp.status_code != 403, f"Unexpected 403 (temp board wrongly counted): {resp.json()}"
