"""
test_report_regen_dedupe.py -- ProjectReportGenerateView concurrency:
board-name follow decided from the LOCKED row, post-lock "someone else already
committed a current report" check, manual regenerate on a fresh report, and the
per-project in-flight lock.
"""
import pytest
from unittest.mock import patch

from django.core.cache import cache

from apps.recommendation.models import Project
from apps.recommendation.report_signature import liked_signature

LIKED = [{'id': 'B001', 'intensity': 1.0}]
SIG = liked_signature(LIKED)
OLD = {'persona_type': 'Old Flat', 'source_signature': 'stale-sig'}
NEW = {'persona_type': 'New Flat'}


@pytest.fixture(autouse=True)
def _clear_cache():
    cache.clear()
    yield
    cache.clear()


def _project(user_profile, **kw):
    d = dict(name='Board', liked_ids=LIKED, visibility='public')
    d.update(kw)
    return Project.objects.create(user=user_profile, **d)


def _post(client, project, gen):
    axis = patch('apps.recommendation.views.reports.compute_axis_scores', return_value={'form': 0.1})
    with patch('apps.recommendation.services.generate_persona_report', side_effect=gen) as m, axis:
        res = client.post(f'/api/v1/projects/{project.project_id}/report/generate/',
                          {'regenerate': True}, format='json')
    return res, m


@pytest.mark.django_db
class TestLockedRowDecisions:

    def test_name_follow_uses_report_committed_during_llm(self, auth_client, user_profile):
        """Row changed (report + name) while the LLM ran: follow is judged against
        the report actually being replaced, not the pre-LLM snapshot."""
        project = _project(user_profile, name='Old Flat', final_report=OLD)

        def gen(*a, **k):
            Project.objects.filter(pk=project.pk).update(
                name='Mid Flat', final_report={'persona_type': 'Mid Flat', 'source_signature': 'other'})
            return dict(NEW)

        res, _ = _post(auth_client, project, gen)
        assert res.status_code == 200
        project.refresh_from_db()
        assert project.name == 'New Flat'
        assert project.final_report['persona_type'] == 'New Flat'

    def test_rename_during_llm_wins(self, auth_client, user_profile):
        project = _project(user_profile, name='Old Flat', final_report=OLD)

        def gen(*a, **k):
            Project.objects.filter(pk=project.pk).update(name='Mine')
            return dict(NEW)

        res, _ = _post(auth_client, project, gen)
        assert res.status_code == 200
        project.refresh_from_db()
        assert project.name == 'Mine'

    def test_current_report_committed_meanwhile_is_kept(self, auth_client, user_profile):
        project = _project(user_profile, name='Old Flat', final_report=OLD)
        other = {'persona_type': 'Other Flat', 'source_signature': SIG}

        def gen(*a, **k):
            Project.objects.filter(pk=project.pk).update(final_report=other)
            return dict(NEW)

        res, _ = _post(auth_client, project, gen)
        assert res.status_code == 200
        assert res.json()['final_report'] == other
        project.refresh_from_db()
        assert project.final_report == other
        assert project.name == 'Old Flat'

    def test_manual_regenerate_on_fresh_report_still_overwrites(self, auth_client, user_profile):
        project = _project(user_profile, name='Old Flat',
                           final_report={'persona_type': 'Old Flat', 'source_signature': SIG})
        res, m = _post(auth_client, project, lambda *a, **k: dict(NEW))
        assert res.status_code == 200
        assert m.call_count == 1
        project.refresh_from_db()
        assert project.final_report['persona_type'] == 'New Flat'
        assert project.final_report['source_signature'] == SIG
        assert project.name == 'New Flat'


@pytest.mark.django_db
class TestInFlightLock:

    def test_duplicate_while_leader_running_does_not_call_llm(self, auth_client, user_profile):
        project = _project(user_profile, final_report=OLD)
        cache.set(f'report_generate_lock:{project.project_id}', 'leader', 60)
        with patch('apps.recommendation.views.reports.REPORT_WAIT_BUDGET', 0):
            res, m = _post(auth_client, project, lambda *a, **k: dict(NEW))
        assert res.status_code == 202
        assert res.json()['status'] == 'in_progress'
        assert m.call_count == 0

    def test_lock_released_after_success(self, auth_client, user_profile):
        project = _project(user_profile, final_report=OLD)
        _post(auth_client, project, lambda *a, **k: dict(NEW))
        assert cache.get(f'report_generate_lock:{project.project_id}') is None

    def test_lock_released_after_llm_error(self, auth_client, user_profile):
        project = _project(user_profile, final_report=OLD)

        def boom(*a, **k):
            raise RuntimeError('llm down')

        res, _ = _post(auth_client, project, boom)
        assert res.status_code == 502
        assert cache.get(f'report_generate_lock:{project.project_id}') is None
