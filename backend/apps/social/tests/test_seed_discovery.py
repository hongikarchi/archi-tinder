"""
test_seed_discovery.py -- coverage for the seed_discovery management command
(FRONT-PEOPLE-CARD-2).

Coverage:
  1. DEBUG guard: settings.DEBUG=False -> command raises without writing.
  2. Seeding: --n 3 -> 3 users pass the exact two-gate feed queryset
     views_people.py uses; type_code matches the real _compute_type_code
     derivation for each seeded vector.
  3. Idempotency: re-running with the same --n creates 0 new users.
  4. --clean removes all seed_* users + cascades.
  5. --publish-existing flips non-public Projects with a report_image to
     visibility='public', leaves report_image-less projects untouched.
"""
import io

import pytest
from django.core.management import call_command
from django.test import override_settings

from apps.accounts.models import PersonalityProfile
from apps.accounts.views.personality import _compute_type_code
from apps.recommendation.models import Project


def _run(*args):
    out = io.StringIO()
    call_command('seed_discovery', *args, stdout=out)
    return out.getvalue()


def _feed_candidate_ids():
    """Same two-gate queryset shape as views_people.PeopleDiscoveryView.get."""
    report_image_owner_ids = set(
        Project.objects
        .filter(visibility='public')
        .exclude(report_image__isnull=True)
        .exclude(report_image='')
        .values_list('user_id', flat=True)
        .distinct()
    )
    return set(
        PersonalityProfile.objects
        .filter(discovery_opt_in=True)
        .filter(user_id__in=report_image_owner_ids)
        .values_list('user_id', flat=True)
    )


# ---------------------------------------------------------------------------
# 1. DEBUG guard
# ---------------------------------------------------------------------------

@pytest.mark.django_db
@override_settings(DEBUG=False)
def test_debug_false_refuses_and_writes_nothing():
    from django.contrib.auth.models import User

    with pytest.raises(Exception):
        call_command('seed_discovery', '--n', '3')

    assert not User.objects.filter(username__startswith='seed_').exists()
    assert PersonalityProfile.objects.count() == 0
    assert Project.objects.count() == 0


# ---------------------------------------------------------------------------
# 2. Seeding
# ---------------------------------------------------------------------------

@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_seed_n3_creates_three_feed_eligible_users():
    from django.contrib.auth.models import User

    output = _run('--n', '3')

    seed_users = User.objects.filter(username__startswith='seed_')
    assert seed_users.count() == 3

    seed_profile_ids = set(
        seed_users.values_list('profile__id', flat=True)
    )
    candidate_ids = _feed_candidate_ids()
    # All 3 seeded profiles pass the exact feed gate.
    assert seed_profile_ids.issubset(candidate_ids)
    assert len(seed_profile_ids) == 3

    assert 'created 3 users' in output
    assert 'Feed-candidate count' in output


@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_seed_type_code_matches_real_derivation():
    _run('--n', '5')

    for personality in PersonalityProfile.objects.filter(
        user__user__username__startswith='seed_'
    ):
        expected = _compute_type_code(
            personality.axis_1, personality.axis_2,
            personality.axis_3, personality.axis_4,
        )
        assert personality.type_code == expected


@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_seed_n_zero_creates_nothing():
    from django.contrib.auth.models import User

    _run('--n', '0')
    assert User.objects.filter(username__startswith='seed_').count() == 0


@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_seeded_projects_have_placeholder_png():
    _run('--n', '2')

    for project in Project.objects.filter(user__user__username__startswith='seed_'):
        assert project.visibility == 'public'
        assert project.report_image
        assert project.report_image_mime == 'image/png'


# ---------------------------------------------------------------------------
# 3. Idempotency
# ---------------------------------------------------------------------------

@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_rerun_same_n_creates_zero_new_users():
    from django.contrib.auth.models import User

    _run('--n', '4')
    assert User.objects.filter(username__startswith='seed_').count() == 4

    output = _run('--n', '4')
    assert User.objects.filter(username__startswith='seed_').count() == 4
    assert 'created 0 users' in output
    assert 'skipped 4 existing' in output


# ---------------------------------------------------------------------------
# 4. --clean
# ---------------------------------------------------------------------------

@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_clean_removes_seed_users_and_cascades():
    from django.contrib.auth.models import User

    _run('--n', '3')
    assert User.objects.filter(username__startswith='seed_').count() == 3
    assert PersonalityProfile.objects.filter(
        user__user__username__startswith='seed_'
    ).count() == 3
    assert Project.objects.filter(
        user__user__username__startswith='seed_'
    ).count() == 3

    _run('--clean')

    assert User.objects.filter(username__startswith='seed_').count() == 0
    assert PersonalityProfile.objects.filter(
        user__user__username__startswith='seed_'
    ).count() == 0
    assert Project.objects.filter(
        user__user__username__startswith='seed_'
    ).count() == 0


@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_clean_does_not_touch_non_seed_users(user_profile):
    """user_profile fixture (conftest) creates a non-seed 'testuser' — --clean
    must leave it and its data untouched."""
    from apps.accounts.models import UserProfile

    _run('--n', '2')
    _run('--clean')

    assert UserProfile.objects.filter(pk=user_profile.id).exists()


# ---------------------------------------------------------------------------
# 5. --publish-existing
# ---------------------------------------------------------------------------

@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_publish_existing_flips_only_projects_with_report_image(user_profile):
    with_image = Project.objects.create(
        user=user_profile, name='Has Image', visibility='private',
        report_image='not-really-base64-but-non-empty',
        report_image_mime='image/png',
    )
    without_image = Project.objects.create(
        user=user_profile, name='No Image', visibility='private',
    )
    empty_image = Project.objects.create(
        user=user_profile, name='Empty Image String', visibility='private',
        report_image='',
    )

    output = _run('--n', '0', '--publish-existing')

    with_image.refresh_from_db()
    without_image.refresh_from_db()
    empty_image.refresh_from_db()

    assert with_image.visibility == 'public'
    assert without_image.visibility == 'private'
    assert empty_image.visibility == 'private'
    assert 'flipped 1 projects' in output
