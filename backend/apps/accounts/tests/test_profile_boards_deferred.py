"""Profile board list must not load heavy Project columns (report_image etc.)."""
from unittest.mock import patch

import pytest
from django.contrib.auth.models import User
from django.db import connection
from django.test.utils import CaptureQueriesContext

from apps.accounts.models import UserProfile
from apps.accounts.views.profile import _build_boards_field
from apps.recommendation.models import Project


def _owner():
    user = User.objects.create_user(username='owner', email='owner@example.com', password='x')
    return UserProfile.objects.create(user=user, display_name='Owner')


def _run(profile, is_owner=False):
    with patch('apps.recommendation.engine.get_building_thumbnails', return_value=[]):
        with CaptureQueriesContext(connection) as ctx:
            boards = _build_boards_field(profile, is_owner=is_owner, page=1, page_size=50)
    return boards, ctx


@pytest.mark.django_db
def test_has_report_image_flag_and_url():
    profile = _owner()
    with_img = Project.objects.create(
        user=profile, name='with', visibility='public', report_image='BIGBASE64',
        report_image_mime='image/png', liked_ids=['bld_000001'],
    )
    empty = Project.objects.create(user=profile, name='empty', visibility='public', report_image='')
    none_img = Project.objects.create(user=profile, name='none', visibility='public', report_image=None)

    boards, _ = _run(profile)
    by_id = {i['project_id']: i for i in boards['items']}
    a = by_id[str(with_img.pk)]
    assert a['has_report_image'] is True
    assert a['report_image_url'] == f'/api/v1/projects/{with_img.pk}/report-image/'
    for b in (empty, none_img):
        item = by_id[str(b.pk)]
        assert item['has_report_image'] is False
        assert item['report_image_url'] == ''
    assert boards['total_count'] == 3


@pytest.mark.django_db
def test_query_count_does_not_scale_with_boards():
    profile = _owner()
    Project.objects.create(user=profile, name='b0', visibility='public', report_image='X')
    _, small = _run(profile)

    for i in range(1, 8):
        Project.objects.create(
            user=profile, name=f'b{i}', visibility='public',
            report_image='X' if i % 2 else None,
            analysis_report={'k': 'v'}, axis_scores={'a': 1},
        )
    boards, big = _run(profile)
    assert len(boards['items']) == 8
    assert len(big.captured_queries) == len(small.captured_queries)
