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

    def test_follower_after_failed_leader_gets_502_not_old_report(self, user_profile):
        from apps.recommendation.views.reports import ProjectReportGenerateView
        project = _project(user_profile, final_report=OLD)
        prev_sig = OLD.get('source_signature') if isinstance(OLD, dict) else None
        # Lock already gone (leader finished) but report unchanged -> leader failed.
        res = ProjectReportGenerateView()._wait_for_leader(
            project.project_id, f'report_generate_lock:{project.project_id}', prev_sig)
        assert res.status_code == 502

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


@pytest.mark.django_db
class TestGenerationId:

    def test_generate_stamps_generation_id(self, auth_client, user_profile):
        project = _project(user_profile, final_report=OLD)
        res, _ = _post(auth_client, project, lambda *a, **k: dict(NEW))
        gid = res.json()['final_report']['generation_id']
        assert gid
        project.refresh_from_db()
        assert project.final_report['generation_id'] == gid

    def test_follower_gets_report_after_same_signature_regenerate(self, user_profile):
        """Leader's manual regenerate keeps source_signature; generation_id still
        tells the follower something was committed."""
        from apps.recommendation.views.reports import ProjectReportGenerateView
        old = {'persona_type': 'Old', 'source_signature': SIG, 'generation_id': 'g1'}
        project = _project(user_profile, final_report=old)
        Project.objects.filter(pk=project.pk).update(
            final_report={'persona_type': 'New', 'source_signature': SIG, 'generation_id': 'g2'})
        res = ProjectReportGenerateView()._wait_for_leader(
            project.project_id, f'report_generate_lock:{project.project_id}', SIG, 'g1')
        assert res.status_code == 200
        assert res.data['final_report']['generation_id'] == 'g2'

    def test_follower_502_when_generation_unchanged(self, user_profile):
        from apps.recommendation.views.reports import ProjectReportGenerateView
        old = {'persona_type': 'Old', 'source_signature': SIG, 'generation_id': 'g1'}
        project = _project(user_profile, final_report=old)
        res = ProjectReportGenerateView()._wait_for_leader(
            project.project_id, f'report_generate_lock:{project.project_id}', SIG, 'g1')
        assert res.status_code == 502

    def test_202_body_carries_based_on(self, auth_client, user_profile):
        project = _project(user_profile, final_report={**OLD, 'generation_id': 'g1'})
        cache.set(f'report_generate_lock:{project.project_id}', 'leader', 60)
        with patch('apps.recommendation.views.reports.REPORT_WAIT_BUDGET', 0):
            res, m = _post(auth_client, project, lambda *a, **k: dict(NEW))
        assert res.status_code == 202
        assert res.json()['based_on'] == 'g1'
        assert m.call_count == 0

    def test_if_generation_stale_returns_stored_without_llm(self, auth_client, user_profile):
        stored = {'persona_type': 'Fresh', 'source_signature': SIG, 'generation_id': 'g2'}
        project = _project(user_profile, final_report=stored)
        with patch('apps.recommendation.services.generate_persona_report') as m:
            res = auth_client.post(
                f'/api/v1/projects/{project.project_id}/report/generate/',
                {'regenerate': True, 'if_generation': 'g1'}, format='json')
        assert res.status_code == 200
        assert res.json()['final_report'] == stored
        assert m.call_count == 0

    def test_if_generation_matching_still_regenerates(self, auth_client, user_profile):
        stored = {'persona_type': 'Old', 'source_signature': SIG, 'generation_id': 'g1'}
        project = _project(user_profile, final_report=stored)
        axis = patch('apps.recommendation.views.reports.compute_axis_scores', return_value={'form': 0.1})
        with patch('apps.recommendation.services.generate_persona_report',
                   return_value=dict(NEW)) as m, axis:
            res = auth_client.post(
                f'/api/v1/projects/{project.project_id}/report/generate/',
                {'regenerate': True, 'if_generation': 'g1'}, format='json')
        assert res.status_code == 200
        assert m.call_count == 1
        assert res.json()['final_report']['generation_id'] != 'g1'
