"""
test_report_image_parallel.py -- FULL-REPORT-IMG-1: persona image generates in
PARALLEL with the report (no final_report needed).

Coverage:
  - build_image_report_from_facts: facts-based pseudo-report, deterministic
    one_liner, None when no liked ids / no building rows.
  - POST report/generate-image/ with NO final_report -> facts-based prompt
    source; with final_report -> stored report passed through unchanged.
  - Concurrent (lock-held) second request never calls the model; waiter
    returns the leader's stored image / 500 / 202 per outcome.
  - Report save and image save write disjoint columns (no clobber), in both
    orders, via the real views with stale in-memory Project instances.
"""
from unittest.mock import MagicMock, patch

import pytest
from django.core.cache import cache

from apps.recommendation.models import Project
from apps.recommendation.views import reports as reports_view

_RC = {
    'report_fact_min_shown': 3,
    'report_fact_min_liked': 2,
    'report_fact_min_ratio': 1.5,
}


def _row(bid, **overrides):
    base = {
        'canonical_bld_id': bid, 'program': None, 'style': None, 'atmosphere': None,
        'color_tone': None, 'material_visual': None, 'typology_primary': None,
        'typology_tags': None, 'architectural_elements': None, 'project_year': None,
        'location_country': None, 'architect_names': None, 'architects_text': None,
        'visual_description': None,
    }
    base.update(overrides)
    return base


def _patch_rows(rows):
    return patch(
        'apps.recommendation.services.generation._fetch_taste_rows', return_value=rows,
    )


@pytest.fixture(autouse=True)
def _clear_cache():
    cache.clear()
    yield
    cache.clear()


def _make_project(user_profile, **kwargs):
    defaults = dict(
        name='ImgBoard',
        liked_ids=[{'id': 'L1', 'intensity': 1.0}, {'id': 'L2', 'intensity': 1.0}],
        disliked_ids=['D1'],
    )
    defaults.update(kwargs)
    return Project.objects.create(user=user_profile, **defaults)


def _url(project):
    return f'/api/v1/projects/{project.project_id}/report/generate-image/'


_IMG = {'image_data': 'IMGDATA', 'mime_type': 'image/webp', 'prompt': 'p'}


# -- build_image_report_from_facts -------------------------------------------

class TestBuildImageReportFromFacts:

    def test_builds_dominant_lists_and_deterministic_one_liner(self, settings):
        from apps.recommendation.services import build_image_report_from_facts
        settings.RECOMMENDATION = {**settings.RECOMMENDATION, **_RC}
        rows = [
            _row('L1', style='Brutalist', program='Museum', atmosphere='Austere',
                 material_visual=['Concrete', 'Steel']),
            _row('L2', style='Brutalist', program='Museum', atmosphere='Austere',
                 material_visual=['Concrete']),
            _row('D1', style='Kitsch', program='Housing', atmosphere='Playful',
                 material_visual=['Plastic']),
        ]
        with _patch_rows(rows):
            report = build_image_report_from_facts(['L1', 'L2'], ['D1'])
            again = build_image_report_from_facts(['L1', 'L2'], ['D1'])

        assert report['dominant_styles'] == ['brutalist']
        assert report['dominant_programs'] == ['museum']
        assert report['dominant_materials'][0] == 'concrete'
        assert 'steel' in report['dominant_materials']
        assert 'plastic' not in report['dominant_materials']
        assert report['one_liner'] == 'austere'
        assert report == again  # deterministic

    def test_few_swipes_still_grounded_without_facts(self):
        from apps.recommendation.services import build_image_report_from_facts
        rows = [_row('L1', style='Modernist', program='Housing')]
        with _patch_rows(rows):
            report = build_image_report_from_facts(['L1'], [])
        assert report['dominant_styles'] == ['modernist']
        assert report['dominant_programs'] == ['housing']
        assert report['dominant_materials'] == []
        assert report['one_liner'] == 'serene and monumental'

    def test_none_without_liked_or_rows(self):
        from apps.recommendation.services import build_image_report_from_facts
        assert build_image_report_from_facts([], ['D1']) is None
        with _patch_rows([]):
            assert build_image_report_from_facts(['L1'], []) is None

    def test_prompt_uses_facts(self):
        """The pseudo-report feeds generate_persona_image's prompt unchanged."""
        from apps.recommendation import services
        from apps.recommendation.services import build_image_report_from_facts
        with _patch_rows([_row('L1', style='Brutalist', program='Museum',
                               atmosphere='Austere', material_visual=['Concrete'])]):
            report = build_image_report_from_facts(['L1'], [])
        captured = {}

        def fake_gen(client, prompt):
            captured['prompt'] = prompt
            return None, None, 'm'

        with patch.object(services, '_get_client', return_value=MagicMock()), \
             patch('apps.recommendation.services.generation._gen_native', side_effect=fake_gen):
            services.generate_persona_image(report)
        assert 'brutalist style' in captured['prompt']
        assert 'museum typology' in captured['prompt']
        assert 'atmosphere: austere' in captured['prompt']
        assert 'Materials: concrete' in captured['prompt']


# -- view: facts vs report source --------------------------------------------

@pytest.mark.django_db
class TestImageViewSource:

    def test_no_final_report_uses_facts_source(self, auth_client, user_profile):
        project = _make_project(user_profile)
        facts_report = {'dominant_styles': ['x'], 'one_liner': 'y'}
        with patch('apps.recommendation.services.build_image_report_from_facts',
                   return_value=facts_report) as mock_facts, \
             patch('apps.recommendation.services.generate_persona_image',
                   return_value=_IMG) as mock_gen:
            resp = auth_client.post(_url(project), {}, format='json')

        assert resp.status_code == 200
        assert resp.json() == _IMG
        mock_facts.assert_called_once_with(['L1', 'L2'], ['D1'])
        mock_gen.assert_called_once_with(facts_report)
        project.refresh_from_db()
        assert project.report_image == 'IMGDATA'
        assert project.final_report is None  # image save did not invent a report

    def test_with_final_report_unchanged_path(self, auth_client, user_profile):
        report = {'dominant_styles': ['a'], 'one_liner': 'z'}
        project = _make_project(user_profile, final_report=report)
        with patch('apps.recommendation.services.build_image_report_from_facts') as mock_facts, \
             patch('apps.recommendation.services.generate_persona_image',
                   return_value=_IMG) as mock_gen:
            resp = auth_client.post(_url(project), {}, format='json')

        assert resp.status_code == 200
        mock_facts.assert_not_called()
        mock_gen.assert_called_once_with(report)

    def test_no_report_no_likes_400(self, auth_client, user_profile):
        project = _make_project(user_profile, liked_ids=[])
        resp = auth_client.post(_url(project), {}, format='json')
        assert resp.status_code == 400

    def test_no_report_no_building_rows_404(self, auth_client, user_profile):
        project = _make_project(user_profile)
        with patch('apps.recommendation.services.build_image_report_from_facts',
                   return_value=None), \
             patch('apps.recommendation.services.generate_persona_image') as mock_gen:
            resp = auth_client.post(_url(project), {}, format='json')
        assert resp.status_code == 404
        mock_gen.assert_not_called()
        assert cache.get(reports_view._image_lock_key(project.project_id)) is None

    def test_failure_returns_500_and_releases_lock(self, auth_client, user_profile):
        project = _make_project(user_profile)
        with patch('apps.recommendation.services.build_image_report_from_facts',
                   return_value={'one_liner': 'y'}), \
             patch('apps.recommendation.services.generate_persona_image', return_value=None):
            resp = auth_client.post(_url(project), {}, format='json')
        assert resp.status_code == 500
        assert cache.get(reports_view._image_lock_key(project.project_id)) is None


# -- view: concurrency dedupe ------------------------------------------------

@pytest.mark.django_db
class TestImageViewDedupe:

    def test_locked_second_request_does_not_call_model_and_returns_leader_image(
        self, auth_client, user_profile,
    ):
        project = _make_project(user_profile)
        lock_key = reports_view._image_lock_key(project.project_id)
        assert cache.add(lock_key, 'other-token', 90)  # a leader is generating

        def leader_finishes(_seconds):
            Project.objects.filter(pk=project.pk).update(
                report_image='LEADER', report_image_mime='image/webp',
            )
            cache.delete(lock_key)

        with patch('apps.recommendation.services.generate_persona_image') as mock_gen, \
             patch('apps.recommendation.services.build_image_report_from_facts') as mock_facts, \
             patch.object(reports_view.time, 'sleep', side_effect=leader_finishes):
            resp = auth_client.post(_url(project), {}, format='json')

        assert resp.status_code == 200
        assert resp.json() == {'image_data': 'LEADER', 'mime_type': 'image/webp', 'prompt': None}
        mock_gen.assert_not_called()
        mock_facts.assert_not_called()

    def test_locked_and_leader_failed_returns_500_without_model_call(
        self, auth_client, user_profile,
    ):
        project = _make_project(user_profile)
        lock_key = reports_view._image_lock_key(project.project_id)
        cache.add(lock_key, 'other-token', 90)
        with patch('apps.recommendation.services.generate_persona_image') as mock_gen, \
             patch.object(reports_view.time, 'sleep',
                          side_effect=lambda s: cache.delete(lock_key)):
            resp = auth_client.post(_url(project), {}, format='json')
        assert resp.status_code == 500
        mock_gen.assert_not_called()

    def test_locked_past_wait_budget_returns_202_without_model_call(
        self, auth_client, user_profile,
    ):
        project = _make_project(user_profile)
        cache.add(reports_view._image_lock_key(project.project_id), 'other-token', 90)
        with patch('apps.recommendation.services.generate_persona_image') as mock_gen, \
             patch.object(reports_view, 'IMAGE_WAIT_BUDGET', 0), \
             patch.object(reports_view.time, 'sleep'):
            resp = auth_client.post(_url(project), {}, format='json')
        assert resp.status_code == 202
        body = resp.json()
        assert body['status'] == 'in_progress'
        assert body['retry_after'] == 5
        mock_gen.assert_not_called()

    def test_lock_uses_unique_token_and_ttl_covers_worst_case(self, auth_client, user_profile):
        project = _make_project(user_profile)
        lock_key = reports_view._image_lock_key(project.project_id)
        seen = {}
        real_add = cache.add

        def spy_add(key, value, timeout=None, *a, **kw):
            seen['value'], seen['timeout'] = value, timeout
            return real_add(key, value, timeout, *a, **kw)

        with patch('apps.recommendation.services.build_image_report_from_facts',
                   return_value={'one_liner': 'y'}), \
             patch('apps.recommendation.services.generate_persona_image',
                   return_value=_IMG), \
             patch.object(reports_view.cache, 'add', side_effect=spy_add):
            resp = auth_client.post(_url(project), {}, format='json')
        assert resp.status_code == 200
        assert seen['value'] != '1' and len(seen['value']) >= 32
        assert seen['timeout'] == reports_view.IMAGE_LOCK_TTL >= 180
        assert reports_view.IMAGE_WAIT_BUDGET <= 30
        assert cache.get(lock_key) is None

    def test_leader_does_not_delete_a_later_leaders_lock(self, auth_client, user_profile):
        """Leader's TTL expired mid-generation and a new leader took the lock;
        the first leader's release must leave the new lock intact."""
        project = _make_project(user_profile)
        lock_key = reports_view._image_lock_key(project.project_id)

        def gen_while_lock_replaced(_source):
            cache.set(lock_key, 'later-leader-token', 90)
            return _IMG

        with patch('apps.recommendation.services.build_image_report_from_facts',
                   return_value={'one_liner': 'y'}), \
             patch('apps.recommendation.services.generate_persona_image',
                   side_effect=gen_while_lock_replaced):
            resp = auth_client.post(_url(project), {}, format='json')
        assert resp.status_code == 200
        assert cache.get(lock_key) == 'later-leader-token'

    def test_two_sequential_posts_generate_once(self, auth_client, user_profile):
        """After the first completes, the second hits the stored-image short-circuit."""
        project = _make_project(user_profile)
        with patch('apps.recommendation.services.build_image_report_from_facts',
                   return_value={'one_liner': 'y'}), \
             patch('apps.recommendation.services.generate_persona_image',
                   return_value=_IMG) as mock_gen:
            first = auth_client.post(_url(project), {}, format='json')
            second = auth_client.post(_url(project), {}, format='json')
        assert first.status_code == second.status_code == 200
        assert second.json()['image_data'] == 'IMGDATA'
        mock_gen.assert_called_once()


# -- report/image saves never clobber each other -----------------------------

@pytest.mark.django_db
class TestReportImageNoClobber:

    _REPORT = {'persona_type': 'T', 'one_liner': 'o'}
    _AXIS = {'axis': 0.5}

    def test_report_saved_while_image_generating_survives_image_save(
        self, auth_client, user_profile,
    ):
        """Image request loaded Project BEFORE the report landed; the report is
        written during image generation; the image save must not wipe it."""
        project = _make_project(user_profile)

        def gen_and_report_lands(_source):
            # Concurrent report request commits its columns mid-generation.
            Project.objects.filter(pk=project.pk).update(
                final_report=self._REPORT, axis_scores=self._AXIS,
            )
            return _IMG

        with patch('apps.recommendation.services.build_image_report_from_facts',
                   return_value={'one_liner': 'y'}), \
             patch('apps.recommendation.services.generate_persona_image',
                   side_effect=gen_and_report_lands):
            resp = auth_client.post(_url(project), {}, format='json')

        assert resp.status_code == 200
        project.refresh_from_db()
        assert project.final_report == self._REPORT
        assert project.axis_scores == self._AXIS
        assert project.report_image == 'IMGDATA'

    def test_image_saved_while_report_generating_survives_report_save(
        self, auth_client, user_profile,
    ):
        project = _make_project(user_profile)

        def report_with_image_landing(*_a, **_kw):
            Project.objects.filter(pk=project.pk).update(
                report_image='IMGDATA', report_image_mime='image/webp',
            )
            return self._REPORT

        with patch('apps.recommendation.services.generate_persona_report',
                   side_effect=report_with_image_landing), \
             patch('apps.recommendation.views.reports.compute_axis_scores',
                   return_value=self._AXIS):
            resp = auth_client.post(
                f'/api/v1/projects/{project.project_id}/report/generate/', {}, format='json',
            )

        assert resp.status_code == 200
        project.refresh_from_db()
        assert project.final_report == self._REPORT
        assert project.axis_scores == self._AXIS
        assert project.report_image == 'IMGDATA'
        assert project.report_image_mime == 'image/webp'
