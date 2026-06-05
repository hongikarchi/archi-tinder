"""test_merge_cap.py — merge_guest_into_target row-cap tests (fix ④).

Patches _MERGE_ROW_CAP to a small value (2) and verifies that only the
capped number of Project rows migrate from guest to target.

No CREATEDB required — uses the SQLite override from conftest.py.
"""
import pytest
from unittest.mock import patch

from django.contrib.auth.models import User
from apps.accounts.models import UserProfile


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_profile(username='capuser', is_guest=False):
    from django.utils import timezone
    import uuid
    user = User.objects.create_user(username=f'{username}_{uuid.uuid4().hex}', email='')
    user.set_unusable_password()
    user.save()
    kwargs = dict(user=user, display_name=username)
    if is_guest:
        kwargs.update(
            is_guest=True,
            consent_accepted_at=timezone.now(),
            consent_policy_version='1.0',
        )
    return UserProfile.objects.create(**kwargs)


# ---------------------------------------------------------------------------
# Cap tests
# ---------------------------------------------------------------------------

@pytest.mark.django_db
def test_merge_project_cap_limits_rows(db):
    """With _MERGE_ROW_CAP=2 and 3 guest Projects, only 2 land on target."""
    from apps.recommendation.models import Project
    from apps.accounts.merge import merge_guest_into_target

    guest = _make_profile('guest_cap', is_guest=True)
    target = _make_profile('target_cap', is_guest=False)

    # 3 projects on guest — one must be dropped by the cap
    Project.objects.create(user=guest, name='GProj1')
    Project.objects.create(user=guest, name='GProj2')
    Project.objects.create(user=guest, name='GProj3')

    with patch('apps.accounts.merge._MERGE_ROW_CAP', 2):
        merge_guest_into_target(guest, target)

    migrated = Project.objects.filter(user=target).count()
    assert migrated == 2, f'Expected 2 migrated projects (cap=2), got {migrated}'


@pytest.mark.django_db
def test_merge_project_no_cap_when_below_limit(db):
    """With _MERGE_ROW_CAP=2 and only 2 guest Projects, both migrate (cap not hit)."""
    from apps.recommendation.models import Project
    from apps.accounts.merge import merge_guest_into_target

    guest = _make_profile('guest_nocap', is_guest=True)
    target = _make_profile('target_nocap', is_guest=False)

    Project.objects.create(user=guest, name='GProj1')
    Project.objects.create(user=guest, name='GProj2')

    with patch('apps.accounts.merge._MERGE_ROW_CAP', 2):
        merge_guest_into_target(guest, target)

    migrated = Project.objects.filter(user=target).count()
    assert migrated == 2, f'Expected 2 migrated projects, got {migrated}'
