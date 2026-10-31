"""
test_report_staleness.py — FULL-REPORT-UI-1: report_stale via source_signature.

No schema change: the persona report dict carries `source_signature` (digest of
the liked building ids it was generated from). ProjectSerializer.report_stale is
True iff that signature exists and differs from the board's current liked ids.
"""
import pytest
from unittest.mock import patch

from django.core.cache import cache

from apps.recommendation.models import Project
from apps.recommendation.report_signature import liked_signature


@pytest.fixture(autouse=True)
def _clear_cache():
    cache.clear()
    yield
    cache.clear()


def _liked(*ids):
    return [{'id': i, 'intensity': 1.0} for i in ids]


def _make_project(user_profile, **kwargs):
    defaults = dict(name='StaleBoard', liked_ids=_liked('B001', 'B002'), visibility='public')
    defaults.update(kwargs)
    return Project.objects.create(user=user_profile, **defaults)


def _generate(client, project, regenerate=False):
    body = {'regenerate': True} if regenerate else {}
    gen = patch(
        'apps.recommendation.services.generate_persona_report',
        side_effect=lambda *a, **k: {'summary': 'fresh'},
    )
    axis = patch('apps.recommendation.views.reports.compute_axis_scores', return_value={'form': 0.1})
    evict = patch('apps.recommendation.views.reports.evict_projects_list')
    with gen, axis, evict:
        return client.post(f'/api/v1/projects/{project.project_id}/report/generate/', body, format='json')


def _detail(client, project):
    return client.get(f'/api/v1/projects/{project.project_id}/').json()


class TestLikedSignature:

    def test_stable_and_order_independent(self):
        a = liked_signature(_liked('B001', 'B002', 'B003'))
        b = liked_signature(_liked('B003', 'B001', 'B002'))
        assert a == b
        assert len(a) == 16
        assert a == liked_signature(_liked('B001', 'B002', 'B003'))

    def test_differs_when_set_differs(self):
        assert liked_signature(_liked('B001')) != liked_signature(_liked('B001', 'B002'))

    def test_tolerates_legacy_strings_and_mixed(self):
        assert liked_signature(['B001', 'B002']) == liked_signature(_liked('B002', 'B001'))
        assert liked_signature(['B001', {'id': 'B002'}]) == liked_signature(_liked('B001', 'B002'))

    def test_empty(self):
        assert liked_signature([]) == liked_signature(None)


@pytest.mark.django_db
class TestReportStale:

    def test_generate_stamps_signature_and_not_stale(self, auth_client, user_profile):
        project = _make_project(user_profile)
        resp = _generate(auth_client, project)
        assert resp.status_code == 200
        expected = liked_signature(_liked('B001', 'B002'))
        assert resp.json()['final_report']['source_signature'] == expected
        project.refresh_from_db()
        assert project.final_report['source_signature'] == expected
        assert _detail(auth_client, project)['report_stale'] is False

    def test_stale_after_removal_and_fresh_after_regenerate(self, auth_client, user_profile):
        project = _make_project(user_profile)
        _generate(auth_client, project)

        resp = auth_client.patch(
            f'/api/v1/projects/{project.project_id}/',
            {'remove_building_ids': ['B002']}, format='json',
        )
        assert resp.status_code == 200
        assert resp.json()['report_stale'] is True
        assert _detail(auth_client, project)['report_stale'] is True

        _generate(auth_client, project, regenerate=True)
        assert _detail(auth_client, project)['report_stale'] is False

    def test_legacy_report_not_stale_until_removal(self, auth_client, user_profile):
        project = _make_project(user_profile, final_report={'summary': 'legacy'})
        assert _detail(auth_client, project)['report_stale'] is False

        resp = auth_client.patch(
            f'/api/v1/projects/{project.project_id}/',
            {'remove_building_ids': ['B001']}, format='json',
        )
        assert resp.status_code == 200
        assert resp.json()['report_stale'] is True
        project.refresh_from_db()
        # Stamped with the liked set as it was BEFORE the removal.
        assert project.final_report['source_signature'] == liked_signature(_liked('B001', 'B002'))
        assert project.final_report['summary'] == 'legacy'

    def test_rejected_last_liked_removal_does_not_stamp(self, auth_client, user_profile):
        project = _make_project(
            user_profile, liked_ids=_liked('B001'), final_report={'summary': 'legacy'},
        )
        resp = auth_client.patch(
            f'/api/v1/projects/{project.project_id}/',
            {'remove_building_ids': ['B001']}, format='json',
        )
        assert resp.status_code == 400
        project.refresh_from_db()
        assert 'source_signature' not in project.final_report

    def test_empty_report_dict_is_not_stamped_on_removal(self, auth_client, user_profile):
        project = _make_project(user_profile, final_report={})
        resp = auth_client.patch(
            f'/api/v1/projects/{project.project_id}/',
            {'remove_building_ids': ['B001']}, format='json',
        )
        assert resp.status_code == 200
        project.refresh_from_db()
        assert project.final_report == {}

    def test_no_report_or_no_liked_is_not_stale(self, auth_client, user_profile):
        no_report = _make_project(user_profile)
        assert _detail(auth_client, no_report)['report_stale'] is False
        no_liked = _make_project(
            user_profile, name='Empty', liked_ids=[],
            final_report={'summary': 'x', 'source_signature': liked_signature(_liked('B001'))},
        )
        # Signature present and differs from the (empty) current set -> stale by definition.
        assert _detail(auth_client, no_liked)['report_stale'] is True
        empty_plain = _make_project(user_profile, name='Empty2', liked_ids=[])
        assert _detail(auth_client, empty_plain)['report_stale'] is False

    def test_non_owner_never_sees_stale_flag(self, auth_client, api_client, user_profile):
        # Report content is owner-only: non-owners always get report_stale False
        # (the flag would otherwise reveal that a report exists / changed).
        project = _make_project(user_profile)
        _generate(auth_client, project)
        assert _detail(api_client, project)['report_stale'] is False
        auth_client.patch(
            f'/api/v1/projects/{project.project_id}/',
            {'remove_building_ids': ['B002']}, format='json',
        )
        assert _detail(auth_client, project)['report_stale'] is True
        assert _detail(api_client, project)['report_stale'] is False


@pytest.mark.django_db
class TestLastLikedGuardCountsRenderable:
    """Guard counts only remaining liked ids that exist and are publishable."""

    def test_only_unrenderable_remaining_is_rejected(self, auth_client, user_profile):
        project = _make_project(user_profile, liked_ids=_liked('B001', 'B002'))
        with patch('apps.recommendation.views.projects._count_renderable', return_value=0) as m:
            resp = auth_client.patch(
                f'/api/v1/projects/{project.project_id}/',
                {'remove_building_ids': ['B001']}, format='json',
            )
        assert resp.status_code == 400
        assert resp.json()['detail'] == 'last_liked_building'
        assert m.call_args[0][0] == ['B002']
        project.refresh_from_db()
        assert len(project.liked_ids) == 2

    def test_renderable_remaining_is_allowed(self, auth_client, user_profile):
        project = _make_project(user_profile, liked_ids=_liked('B001', 'B002'))
        with patch('apps.recommendation.views.projects._count_renderable', return_value=1):
            resp = auth_client.patch(
                f'/api/v1/projects/{project.project_id}/',
                {'remove_building_ids': ['B001']}, format='json',
            )
        assert resp.status_code == 200

    def test_count_renderable_query_is_publishable_gated_and_parameterized(self):
        from unittest.mock import MagicMock
        from apps.recommendation.views.projects import _count_renderable
        cur = MagicMock()
        cur.fetchone.return_value = (1,)
        conn = MagicMock()
        conn.__getitem__.return_value.cursor.return_value.__enter__.return_value = cur
        with patch('apps.recommendation.views.projects.connections', conn):
            assert _count_renderable(['B002', 'B002', 'B003']) == 1
        sql, params = cur.execute.call_args[0]
        assert 'is_publishable = true' in sql
        assert '%s' in sql and 'B002' not in sql
        assert params == [['B002', 'B003']]

    def test_count_renderable_empty_skips_query(self):
        from apps.recommendation.views.projects import _count_renderable
        assert _count_renderable([]) == 0
