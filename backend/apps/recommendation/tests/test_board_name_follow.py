"""
test_board_name_follow.py — FULL-REPORT-UI-1: board name follows the regenerated
persona name unless the user renamed the board (no new column).
"""
import pytest
from unittest.mock import patch

from django.core.cache import cache

from apps.recommendation.models import Project
from apps.recommendation.report_name import followed_board_name

OLD = {
    'persona_type': 'Old Flat',
    'i18n': {'ko': {'persona_type': '옛 이름'}, 'en': {'persona_type': 'Old English'}},
}
NEW = {
    'persona_type': 'New Flat',
    'i18n': {'ko': {'persona_type': '새 이름'}, 'en': {'persona_type': 'New English'}},
}


@pytest.fixture(autouse=True)
def _clear_cache():
    cache.clear()
    yield
    cache.clear()


def _make_project(user_profile, **kwargs):
    defaults = dict(name='Board', liked_ids=[{'id': 'B001', 'intensity': 1.0}], visibility='public')
    defaults.update(kwargs)
    return Project.objects.create(user=user_profile, **defaults)


def _regen(client, project, report=NEW):
    gen = patch('apps.recommendation.services.generate_persona_report',
                side_effect=lambda *a, **k: dict(report))
    axis = patch('apps.recommendation.views.reports.compute_axis_scores', return_value={'form': 0.1})
    with gen, axis:
        return client.post(f'/api/v1/projects/{project.project_id}/report/generate/',
                           {'regenerate': True}, format='json')


@pytest.mark.django_db
class TestBoardNameFollow:

    def test_flat_match_follows_in_profile_language(self, auth_client, user_profile):
        project = _make_project(user_profile, name='Old Flat', final_report=OLD)
        assert _regen(auth_client, project).status_code == 200
        project.refresh_from_db()
        assert project.name == '새 이름'

    def test_en_i18n_match_still_follows_when_language_ko(self, auth_client, user_profile):
        project = _make_project(user_profile, name='Old English', final_report=OLD)
        _regen(auth_client, project)
        project.refresh_from_db()
        assert project.name == '새 이름'

    def test_customised_name_unchanged(self, auth_client, user_profile):
        project = _make_project(user_profile, name='My Board', final_report=OLD)
        _regen(auth_client, project)
        project.refresh_from_db()
        assert project.name == 'My Board'

    def test_first_generation_unchanged(self, auth_client, user_profile):
        project = _make_project(user_profile, name='Old Flat')
        _regen(auth_client, project)
        project.refresh_from_db()
        assert project.name == 'Old Flat'

    def test_empty_name_unchanged(self, auth_client, user_profile):
        project = _make_project(user_profile, name='', final_report=OLD)
        _regen(auth_client, project)
        project.refresh_from_db()
        assert project.name == ''

    def test_concurrent_rename_is_not_overwritten(self, auth_client, user_profile):
        project = _make_project(user_profile, name='Old Flat', final_report=OLD)

        def _gen_with_rename(*a, **k):
            # Owner renames the board while generation is in flight.
            Project.objects.filter(pk=project.pk).update(name='내가 정한 이름')
            return dict(NEW)

        gen = patch('apps.recommendation.services.generate_persona_report',
                    side_effect=_gen_with_rename)
        axis = patch('apps.recommendation.views.reports.compute_axis_scores',
                     return_value={'form': 0.1})
        with gen, axis:
            res = auth_client.post(f'/api/v1/projects/{project.project_id}/report/generate/',
                                   {'regenerate': True}, format='json')
        assert res.status_code == 200
        project.refresh_from_db()
        assert project.name == '내가 정한 이름'
        assert project.final_report['persona_type'] == 'New Flat'

    def test_serialized_project_shows_new_name(self, auth_client, user_profile):
        project = _make_project(user_profile, name='Old Flat', final_report=OLD)
        _regen(auth_client, project)
        data = auth_client.get(f'/api/v1/projects/{project.project_id}/').json()
        assert data['name'] == '새 이름'


class TestFollowedBoardName:

    def test_strip_on_both_sides(self):
        old = {'persona_type': '  Old  '}
        assert followed_board_name(' Old ', old, {'persona_type': ' New '}) == 'New'

    def test_missing_i18n_falls_back_to_flat(self):
        assert followed_board_name('Old Flat', OLD, {'persona_type': 'Flat Only'}, 'en') == 'Flat Only'

    def test_language_picks_i18n_block(self):
        assert followed_board_name('Old Flat', OLD, NEW, 'en') == 'New English'

    def test_non_dict_old_report(self):
        for old in (None, 'x', [], 5):
            assert followed_board_name('Old Flat', old, NEW) is None

    def test_no_match_empty_or_same(self):
        assert followed_board_name('Mine', OLD, NEW) is None
        assert followed_board_name('', OLD, NEW) is None
        assert followed_board_name(None, OLD, NEW) is None
        assert followed_board_name('Old Flat', OLD, {'persona_type': 'Old Flat'}) is None

    def test_new_report_without_name(self):
        assert followed_board_name('Old Flat', OLD, {'summary': 'x'}) is None
        assert followed_board_name('Old Flat', OLD, None) is None

    def test_truncation(self):
        assert followed_board_name('Old Flat', OLD, {'persona_type': 'a' * 300}) == 'a' * 200


@pytest.mark.django_db
class TestReportWriteTakesRowLock:
    """The generate view's final write must hold the same row lock as PATCH."""

    def test_final_write_uses_select_for_update_inside_atomic(self, auth_client, user_profile):
        from django.db import connection
        project = _make_project(user_profile, name='Old Flat', final_report=OLD)
        real = Project.objects.select_for_update
        seen = {}
        # pytest-django already wraps the test in an atomic block, so
        # in_atomic_block is always True; the view's own nested atomic() opens
        # a savepoint, which deepens savepoint_ids.
        base = len(connection.savepoint_ids)

        def spy():
            seen['depth'] = len(connection.savepoint_ids)
            seen['calls'] = seen.get('calls', 0) + 1
            return real()

        with patch.object(Project.objects, 'select_for_update', side_effect=spy):
            assert _regen(auth_client, project).status_code == 200
        assert seen['calls'] == 1
        assert seen['depth'] > base
        project.refresh_from_db()
        assert project.final_report['persona_type'] == 'New Flat'
        assert project.name == '새 이름'


@pytest.mark.django_db
class TestReportWriteEdgeCases:

    def test_vanished_row_returns_404(self, auth_client, user_profile):
        project = _make_project(user_profile, name='Old Flat', final_report=OLD)
        pk = project.pk

        def _gen_with_delete(*a, **k):
            # Board is deleted while generation is in flight.
            Project.objects.filter(pk=pk).delete()
            return dict(NEW)

        gen = patch('apps.recommendation.services.generate_persona_report',
                    side_effect=_gen_with_delete)
        axis = patch('apps.recommendation.views.reports.compute_axis_scores',
                     return_value={'form': 0.1})
        with gen, axis:
            res = auth_client.post(f'/api/v1/projects/{project.project_id}/report/generate/',
                                   {'regenerate': True}, format='json')
        assert res.status_code == 404
        assert res.json() == {'detail': 'Not found'}
        assert not Project.objects.filter(pk=pk).exists()

    def test_legacy_report_regenerate_stamp_survives_then_patch_stales(
            self, auth_client, user_profile):
        from apps.recommendation.report_signature import liked_signature
        liked = [{'id': 'B001', 'intensity': 1.0}, {'id': 'B002', 'intensity': 1.0}]
        project = _make_project(user_profile, liked_ids=liked,
                                final_report={'summary': 'legacy'})
        assert _regen(auth_client, project).status_code == 200
        project.refresh_from_db()
        assert project.final_report['source_signature'] == liked_signature(liked)
        url = f'/api/v1/projects/{project.project_id}/'
        assert auth_client.get(url).json()['report_stale'] is False

        res = auth_client.patch(url, {'remove_building_ids': ['B002']}, format='json')
        assert res.status_code == 200
        assert res.json()['report_stale'] is True
        project.refresh_from_db()
        # PATCH must not clobber the stamp with the post-removal set.
        assert project.final_report['source_signature'] == liked_signature(liked)


class TestDiscoveryDraftNameFollow:
    """Pure rule: a discovery_ default name counts as 'not renamed by user'."""

    def test_prefix_mirror_matches_discovery_feed(self):
        from apps.recommendation import report_name
        from apps.recommendation.discovery_feed import DISCOVERY_DRAFT_PREFIX
        assert report_name._DISCOVERY_DRAFT_PREFIX == DISCOVERY_DRAFT_PREFIX

    def test_first_report_replaces_discovery_name(self):
        assert followed_board_name('discovery_261023_1430', None, NEW) == '새 이름'
        assert followed_board_name('discovery_261023_1430', {}, NEW, 'en') == 'New English'

    def test_regeneration_while_still_discovery_name(self):
        assert followed_board_name('discovery_261023_1430', OLD, NEW) == '새 이름'

    def test_user_renamed_untouched(self):
        assert followed_board_name('My Board', None, NEW) is None
        assert followed_board_name('My Board', OLD, NEW) is None

    def test_empty_persona_returns_none(self):
        assert followed_board_name('discovery_261023_1430', None, {'summary': 'x'}) is None
        assert followed_board_name('discovery_261023_1430', None, None) is None
        assert followed_board_name('discovery_261023_1430', None, {'persona_type': '  '}) is None
