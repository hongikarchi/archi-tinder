"""
test_report_cache.py — BACK-REPORT-CACHE-1: report/image cache short-circuit.

Root-cause fix: ProjectReportGenerateView / ProjectReportImageView previously
regenerated + overwrote the stored report/image on every POST, which combined
with frontend auto-fires and the 10/hour throttle produced silent 429s and
nondeterministic report rewrites.

Coverage:
  - POST report/generate/ with a stored final_report and no `regenerate` flag
    returns the stored report WITHOUT calling generate_persona_report /
    compute_axis_scores / cache eviction.
  - POST report/generate/ with `regenerate: true` always regenerates.
  - POST report/generate-image/ mirrors the same pattern for report_image.
  - Response shapes are identical (same key sets) between cached and
    generated paths for both endpoints.
"""
import pytest
from unittest.mock import patch

from django.core.cache import cache

from apps.recommendation.models import Project


@pytest.fixture(autouse=True)
def _clear_throttle_cache():
    """LocMemCache is process-wide (persists across tests in one pytest run),
    while fixtures like `user_profile` reset per-test on a fresh in-memory
    SQLite DB -- pks can repeat across tests. Clear the DRF throttle cache
    before each test so UserRateThrottle counters (keyed by user pk) never
    bleed between tests and cause a flaky 429 mid-suite.
    """
    cache.clear()
    yield
    cache.clear()


def _make_project(user_profile, **kwargs):
    defaults = dict(
        name='ReportBoard',
        liked_ids=[{'id': 'B001', 'intensity': 1.0}],
    )
    defaults.update(kwargs)
    return Project.objects.create(user=user_profile, **defaults)


# ── ProjectReportGenerateView ──────────────────────────────────────────────

@pytest.mark.django_db
class TestProjectReportGenerateCache:

    def test_cached_report_short_circuits_no_generation_call(self, auth_client, user_profile):
        stored_report = {'summary': 'Existing persona report'}
        stored_axis = {'form': 0.5, 'materiality': 0.2, 'scale': 0.1, 'energy': 0.0, 'tradition': -0.3}
        project = _make_project(
            user_profile, final_report=stored_report, axis_scores=stored_axis,
        )

        with patch('apps.recommendation.services.generate_persona_report') as mock_gen, \
             patch('apps.recommendation.views.reports.compute_axis_scores') as mock_axis, \
             patch('apps.recommendation.views.reports.evict_projects_list') as mock_evict_list, \
             patch('apps.recommendation.views.reports.evict_project_detail') as mock_evict_detail:
            resp = auth_client.post(
                f'/api/v1/projects/{project.project_id}/report/generate/',
                {}, format='json',
            )

        assert resp.status_code == 200
        data = resp.json()
        assert data == {'final_report': stored_report, 'axis_scores': stored_axis}
        mock_gen.assert_not_called()
        mock_axis.assert_not_called()
        mock_evict_list.assert_not_called()
        mock_evict_detail.assert_not_called()

        project.refresh_from_db()
        assert project.final_report == stored_report

    def test_regenerate_true_always_regenerates(self, auth_client, user_profile):
        stored_report = {'summary': 'Stale report'}
        new_report = {'summary': 'Fresh persona report'}
        new_axis = {'form': 0.9, 'materiality': 0.1, 'scale': 0.4, 'energy': 0.2, 'tradition': 0.0}
        project = _make_project(
            user_profile, final_report=stored_report, axis_scores={'form': 0.0},
        )

        with patch('apps.recommendation.services.generate_persona_report', return_value=new_report) as mock_gen, \
             patch('apps.recommendation.views.reports.compute_axis_scores', return_value=new_axis) as mock_axis, \
             patch('apps.recommendation.views.reports.evict_projects_list') as mock_evict_list, \
             patch('apps.recommendation.views.reports.evict_project_detail') as mock_evict_detail:
            resp = auth_client.post(
                f'/api/v1/projects/{project.project_id}/report/generate/',
                {'regenerate': True}, format='json',
            )

        assert resp.status_code == 200
        data = resp.json()
        assert data == {'final_report': new_report, 'axis_scores': new_axis}
        mock_gen.assert_called_once()
        mock_axis.assert_called_once()
        mock_evict_list.assert_called_once()
        mock_evict_detail.assert_called_once()

        project.refresh_from_db()
        assert project.final_report == new_report
        assert project.axis_scores == new_axis

    def test_no_stored_report_generates_as_before(self, auth_client, user_profile):
        """No final_report yet -- must behave exactly like today (generate path)."""
        new_report = {'summary': 'First persona report'}
        new_axis = {'form': 0.1}
        project = _make_project(user_profile)

        with patch('apps.recommendation.services.generate_persona_report', return_value=new_report) as mock_gen, \
             patch('apps.recommendation.views.reports.compute_axis_scores', return_value=new_axis), \
             patch('apps.recommendation.views.reports.evict_projects_list'), \
             patch('apps.recommendation.views.reports.evict_project_detail'):
            resp = auth_client.post(
                f'/api/v1/projects/{project.project_id}/report/generate/',
                {}, format='json',
            )

        assert resp.status_code == 200
        assert resp.json() == {'final_report': new_report, 'axis_scores': new_axis}
        mock_gen.assert_called_once()

    def test_cached_and_generated_response_shapes_identical(self, auth_client, user_profile):
        """Key sets must match between the cached short-circuit and the generation path."""
        cached_project = _make_project(
            user_profile, final_report={'summary': 'cached'}, axis_scores={'form': 0.1},
        )
        with patch('apps.recommendation.services.generate_persona_report'), \
             patch('apps.recommendation.views.reports.compute_axis_scores'), \
             patch('apps.recommendation.views.reports.evict_projects_list'), \
             patch('apps.recommendation.views.reports.evict_project_detail'):
            cached_resp = auth_client.post(
                f'/api/v1/projects/{cached_project.project_id}/report/generate/',
                {}, format='json',
            )

        gen_project = _make_project(user_profile, name='FreshBoard')
        with patch(
            'apps.recommendation.services.generate_persona_report',
            return_value={'summary': 'generated'},
        ), patch(
            'apps.recommendation.views.reports.compute_axis_scores',
            return_value={'form': 0.2},
        ), patch('apps.recommendation.views.reports.evict_projects_list'), \
                patch('apps.recommendation.views.reports.evict_project_detail'):
            gen_resp = auth_client.post(
                f'/api/v1/projects/{gen_project.project_id}/report/generate/',
                {}, format='json',
            )

        assert set(cached_resp.json().keys()) == set(gen_resp.json().keys()) == {
            'final_report', 'axis_scores',
        }

    def test_no_liked_ids_still_400_when_no_stored_report(self, auth_client, user_profile):
        """Preserve existing error path when neither cache nor liked_ids exist."""
        project = _make_project(user_profile, liked_ids=[])
        resp = auth_client.post(
            f'/api/v1/projects/{project.project_id}/report/generate/',
            {}, format='json',
        )
        assert resp.status_code == 400

    def test_not_found_for_other_users_project(self, auth_client, other_profile):
        project = _make_project(other_profile)
        resp = auth_client.post(
            f'/api/v1/projects/{project.project_id}/report/generate/',
            {}, format='json',
        )
        assert resp.status_code == 404


# ── ProjectReportImageView ─────────────────────────────────────────────────

@pytest.mark.django_db
class TestProjectReportImageCache:

    def test_cached_image_short_circuits_no_generation_call(self, auth_client, user_profile):
        project = _make_project(
            user_profile,
            final_report={'summary': 'report'},
            report_image='base64-existing-image-data',
            report_image_mime='image/png',
        )

        with patch('apps.recommendation.services.generate_persona_image') as mock_gen, \
             patch('apps.recommendation.views.reports.evict_projects_list') as mock_evict_list, \
             patch('apps.recommendation.views.reports.evict_project_detail') as mock_evict_detail:
            resp = auth_client.post(
                f'/api/v1/projects/{project.project_id}/report/generate-image/',
                {}, format='json',
            )

        assert resp.status_code == 200
        data = resp.json()
        assert data['image_data'] == 'base64-existing-image-data'
        assert data['mime_type'] == 'image/png'
        mock_gen.assert_not_called()
        mock_evict_list.assert_not_called()
        mock_evict_detail.assert_not_called()

    def test_regenerate_true_always_regenerates_image(self, auth_client, user_profile):
        project = _make_project(
            user_profile,
            final_report={'summary': 'report'},
            report_image='stale-image-data',
            report_image_mime='image/png',
        )
        new_result = {'image_data': 'fresh-image-data', 'mime_type': 'image/jpeg', 'prompt': 'a prompt'}

        with patch(
            'apps.recommendation.services.generate_persona_image', return_value=new_result,
        ) as mock_gen, \
                patch('apps.recommendation.views.reports.evict_projects_list') as mock_evict_list, \
                patch('apps.recommendation.views.reports.evict_project_detail') as mock_evict_detail:
            resp = auth_client.post(
                f'/api/v1/projects/{project.project_id}/report/generate-image/',
                {'regenerate': True}, format='json',
            )

        assert resp.status_code == 200
        assert resp.json() == new_result
        mock_gen.assert_called_once()
        mock_evict_list.assert_called_once()
        mock_evict_detail.assert_called_once()

        project.refresh_from_db()
        assert project.report_image == 'fresh-image-data'
        assert project.report_image_mime == 'image/jpeg'

    def test_no_stored_image_generates_as_before(self, auth_client, user_profile):
        project = _make_project(user_profile, final_report={'summary': 'report'})
        new_result = {'image_data': 'first-image-data', 'mime_type': 'image/png', 'prompt': 'p'}

        with patch(
            'apps.recommendation.services.generate_persona_image', return_value=new_result,
        ) as mock_gen, \
                patch('apps.recommendation.views.reports.evict_projects_list'), \
                patch('apps.recommendation.views.reports.evict_project_detail'):
            resp = auth_client.post(
                f'/api/v1/projects/{project.project_id}/report/generate-image/',
                {}, format='json',
            )

        assert resp.status_code == 200
        assert resp.json() == new_result
        mock_gen.assert_called_once()

    def test_cached_and_generated_response_shapes_identical(self, auth_client, user_profile):
        cached_project = _make_project(
            user_profile,
            final_report={'summary': 'r'},
            report_image='cached-img',
            report_image_mime='image/png',
        )
        with patch('apps.recommendation.services.generate_persona_image'), \
             patch('apps.recommendation.views.reports.evict_projects_list'), \
             patch('apps.recommendation.views.reports.evict_project_detail'):
            cached_resp = auth_client.post(
                f'/api/v1/projects/{cached_project.project_id}/report/generate-image/',
                {}, format='json',
            )

        gen_project = _make_project(user_profile, name='FreshImgBoard', final_report={'summary': 'r'})
        with patch(
            'apps.recommendation.services.generate_persona_image',
            return_value={'image_data': 'x', 'mime_type': 'image/png', 'prompt': 'p'},
        ), patch('apps.recommendation.views.reports.evict_projects_list'), \
                patch('apps.recommendation.views.reports.evict_project_detail'):
            gen_resp = auth_client.post(
                f'/api/v1/projects/{gen_project.project_id}/report/generate-image/',
                {}, format='json',
            )

        assert set(cached_resp.json().keys()) == set(gen_resp.json().keys()) == {
            'image_data', 'mime_type', 'prompt',
        }

    def test_requires_final_report_first(self, auth_client, user_profile):
        project = _make_project(user_profile)
        resp = auth_client.post(
            f'/api/v1/projects/{project.project_id}/report/generate-image/',
            {}, format='json',
        )
        assert resp.status_code == 400

    def test_not_found_for_other_users_project(self, auth_client, other_profile):
        project = _make_project(other_profile)
        resp = auth_client.post(
            f'/api/v1/projects/{project.project_id}/report/generate-image/',
            {}, format='json',
        )
        assert resp.status_code == 404
