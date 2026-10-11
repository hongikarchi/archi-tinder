"""Taste-start step 3-2: taste_v2 session create / resume + ProjectSerializer tags.

Postgres-backed (django_db): run with `make test-local`. The buildings DB is
never touched -- matching.* and the engine lookups are mocked.
"""
from unittest import mock

import numpy as np
import pytest

from apps.recommendation import engine
from apps.recommendation.models import AnalysisSession, Project
from apps.recommendation.serializers import ProjectSerializer
from apps.recommendation.taste_start import matching, session_pool, session_selector
from apps.recommendation.taste_start.recognizer import make_tag

URL = '/api/v1/analysis/sessions/'
VALID = [f'B{i:05d}' for i in range(1, 31)]          # buildings the "DB" knows
EMB = {b: np.random.RandomState(i).randn(384) for i, b in enumerate(VALID)}
EMB = {b: v / np.linalg.norm(v) for b, v in EMB.items()}

TAGS = [make_tag('country', 'Japan'), make_tag('material', 'wood', 'exclude')]
TAG_PAYLOAD = [{'axis': 'country', 'value': 'Japan', 'polarity': 'want'},
               {'axis': 'material', 'value': 'wood', 'polarity': 'exclude'}]
TAG_DICTS = [t.to_dict() for t in TAGS]


def card(bid, image_focus=None):
    return {'canonical_bld_id': bid, 'name': f'Building {bid}', 'image_url': 'x',
            'metadata': {}} if bid else None


def _by_ids(ids, image_focus=None):
    return [card(i) for i in ids if i in VALID]


@pytest.fixture
def env():
    """Mock the buildings-DB boundary; yields the ranked_pool mock."""
    ranked = [{'canonical_bld_id': b, 'score': 3.0} for b in VALID[3:20]]
    with mock.patch.object(engine, 'get_buildings_by_ids', side_effect=_by_ids), \
            mock.patch.object(engine, 'get_building_card', side_effect=card), \
            mock.patch.object(engine, 'get_pool_embeddings',
                              side_effect=lambda ids: {i: EMB[i] for i in ids if i in EMB}), \
            mock.patch.object(matching, 'ranked_pool', return_value=ranked) as rp, \
            mock.patch.object(matching, 'score_ids',
                              side_effect=lambda tags, ids: {i: 3.0 for i in ids}):
        yield rp


def payload(**kw):
    base = {'name': 'Japan wood', 'raw_query': 'japanese houses', 'taste_tags': TAG_PAYLOAD,
            'start_ids': VALID[:3]}
    base.update(kw)
    return base


@pytest.mark.django_db
class TestCreateV2:

    def test_create_stores_marker_tags_and_start_cards(self, auth_client, user_profile, env):
        resp = auth_client.post(URL, payload(), format='json')
        assert resp.status_code == 201
        data = resp.json()
        assert data['next_image']['canonical_bld_id'] == VALID[0]
        assert data['prefetch_image']['canonical_bld_id'] == VALID[1]
        assert data['prefetch_image_2']['canonical_bld_id'] == VALID[2]
        assert data['filter_relaxed'] is False
        assert {'session_id', 'project_id', 'name', 'session_status', 'progress'} <= set(data)

        s = AnalysisSession.objects.get(session_id=data['session_id'])
        assert s.original_filters['selector'] == 'taste_v2'
        assert s.original_filters['taste_tags'] == TAG_DICTS
        assert s.initial_batch == VALID[:3]
        assert s.exposed_ids == [VALID[0]]
        assert s.phase == 'exploring' and s.current_pool_tier == 1
        assert s.original_seed_ids == []
        assert s.pool_ids[:3] == VALID[:3] and len(set(s.pool_ids)) == len(s.pool_ids)
        assert set(s.pool_scores) == set(s.pool_ids)

        p = s.project
        assert p.is_temp is True
        assert [t['axis'] for t in p.filters['taste_tags']] == ['country', 'material']
        assert p.name == 'Japan wood'

    def test_forged_match_is_rebuilt(self, auth_client, user_profile, env):
        forged = [dict(TAG_PAYLOAD[0], match={'location_country': ['Evil']})]
        resp = auth_client.post(URL, payload(taste_tags=forged), format='json')
        assert resp.status_code == 201
        s = AnalysisSession.objects.get(session_id=resp.json()['session_id'])
        assert s.original_filters['taste_tags'][0]['match'] == TAGS[0].match

    def test_placeholder_name_gets_tag_based_board_name(self, auth_client, user_profile, env):
        resp = auth_client.post(URL, payload(name='Untitled'), format='json')
        assert resp.status_code == 201
        assert resp.json()['name'] == 'Japan'

    @pytest.mark.parametrize('bad_tags', [
        [{'axis': 'country', 'value': 'Atlantis'}], [{'axis': 'nope', 'value': 'x'}],
        ['junk'], [{'axis': 'year', 'value': [2000, 1990]}],
    ])
    def test_invalid_tags_400(self, auth_client, user_profile, env, bad_tags):
        assert auth_client.post(URL, payload(taste_tags=bad_tags), format='json').status_code == 400
        assert AnalysisSession.objects.count() == 0

    @pytest.mark.parametrize('bad_start', [
        [], 'B00001', ['B00001', 'B00001'], VALID[:4], [1, 2], ['NOPE1', 'NOPE2'],
    ])
    def test_invalid_start_ids_400(self, auth_client, user_profile, env, bad_start):
        assert auth_client.post(URL, payload(start_ids=bad_start), format='json').status_code == 400
        assert Project.objects.count() == 0

    def test_bad_exclude_ids_400(self, auth_client, user_profile, env):
        resp = auth_client.post(URL, payload(exclude_ids=['x'] * 101), format='json')
        assert resp.status_code == 400

    def test_partially_valid_start_ids_keep_order(self, auth_client, user_profile, env):
        resp = auth_client.post(URL, payload(start_ids=[VALID[2], 'NOPE1', VALID[0]]), format='json')
        assert resp.status_code == 201
        s = AnalysisSession.objects.get(session_id=resp.json()['session_id'])
        assert s.initial_batch == [VALID[2], VALID[0]]
        assert resp.json()['prefetch_image_2'] is None

    def test_dedupe_within_30s(self, auth_client, user_profile, env):
        r1 = auth_client.post(URL, payload(), format='json')
        r2 = auth_client.post(URL, payload(), format='json')
        assert r1.status_code == 201 and r2.status_code == 200
        assert r2.json()['deduped'] is True
        assert r2.json()['session_id'] == r1.json()['session_id']
        assert AnalysisSession.objects.count() == 1 and Project.objects.count() == 1

    def test_different_start_ids_not_deduped(self, auth_client, user_profile, env):
        auth_client.post(URL, payload(), format='json')
        r2 = auth_client.post(URL, payload(start_ids=VALID[3:6]), format='json')
        assert r2.status_code == 201
        assert AnalysisSession.objects.count() == 2

    def test_update_mode_excludes_board_history_and_writes_tags(self, auth_client, user_profile, env):
        proj = Project.objects.create(
            user=user_profile, name='Old board', filters={'style': 'Minimalist'},
            liked_ids=[VALID[10], {'id': VALID[11], 'intensity': 1.0}],
            disliked_ids=[VALID[12]])
        resp = auth_client.post(
            URL, payload(project_id=str(proj.project_id), force_new=True,
                         exclude_ids=[VALID[13]]), format='json')
        assert resp.status_code == 201
        assert resp.json()['project_id'] == str(proj.project_id)
        excl = env.call_args.kwargs['exclude_ids']
        assert {VALID[10], VALID[11], VALID[12], VALID[13], *VALID[:3]} <= set(excl)
        proj.refresh_from_db()
        assert proj.filters['style'] == 'Minimalist'            # legacy keys kept
        assert [t['axis'] for t in proj.filters['taste_tags']] == ['country', 'material']
        assert proj.name == 'Old board'

    def test_existing_session_resumed_without_force_new(self, auth_client, user_profile, env):
        r1 = auth_client.post(URL, payload(), format='json')
        pid = r1.json()['project_id']
        r2 = auth_client.post(URL, payload(project_id=pid), format='json')
        assert r2.status_code == 200
        assert r2.json()['session_id'] == r1.json()['session_id']

    def test_legacy_filters_create_goes_through_v2(self, auth_client, user_profile, env):
        """No taste_tags in the request: filters -> tags -> top matches as start cards -> v2."""
        top = [{'canonical_bld_id': b, 'score': 3.0, 'matched_keys': [], 'hit': 1, 'total': 2}
               for b in VALID[:3]]
        with mock.patch.object(matching, 'top_matches', return_value=top) as tm:
            resp = auth_client.post(
                URL, {'filters': {'program': 'Housing', 'location_country': 'Japan'},
                      'name': 'Legacy', 'force_new': True}, format='json')
        assert resp.status_code == 201
        data = resp.json()
        assert [data['next_image']['canonical_bld_id'], data['prefetch_image']['canonical_bld_id'],
                data['prefetch_image_2']['canonical_bld_id']] == VALID[:3]
        tags = tm.call_args.args[0]
        assert {t.axis for t in tags} == {'use', 'country'}
        assert tm.call_args.kwargs['limit'] == 3
        s = AnalysisSession.objects.get(session_id=data['session_id'])
        assert session_pool.is_v2(s)
        assert {t['axis'] for t in s.original_filters['taste_tags']} == {'use', 'country'}
        assert s.initial_batch == VALID[:3] and s.exposed_ids == [VALID[0]]
        assert s.phase == 'exploring'
        # board keeps the original filters next to the v2 tags
        assert s.project.filters['program'] == 'Housing'
        assert {t['axis'] for t in s.project.filters['taste_tags']} == {'use', 'country'}

    def test_legacy_create_without_tags_uses_diverse_start_cards(self, auth_client, user_profile, env):
        diverse = [card(b) for b in VALID[5:8]]
        with mock.patch.object(engine, 'get_diverse_random', return_value=diverse), \
                mock.patch.object(matching, 'top_matches') as tm:
            resp = auth_client.post(URL, {'filters': {}, 'name': 'Plain'}, format='json')
        assert resp.status_code == 201
        tm.assert_not_called()
        s = AnalysisSession.objects.get(session_id=resp.json()['session_id'])
        assert session_pool.is_v2(s) and s.original_filters['taste_tags'] == []
        assert s.initial_batch == VALID[5:8]

    def test_legacy_create_seed_ids_stay_in_pool_after_start_cards(self, auth_client, user_profile, env):
        top = [{'canonical_bld_id': b, 'score': 3.0, 'matched_keys': [], 'hit': 1, 'total': 1}
               for b in VALID[:3]]
        with mock.patch.object(matching, 'top_matches', return_value=top):
            resp = auth_client.post(
                URL, {'filters': {'location_country': 'Japan'}, 'seed_ids': ['SEEDX', VALID[25]],
                      'name': 'Seeds'}, format='json')
        assert resp.status_code == 201
        s = AnalysisSession.objects.get(session_id=resp.json()['session_id'])
        assert s.pool_ids[:5] == VALID[:3] + ['SEEDX', VALID[25]]
        assert s.original_seed_ids == ['SEEDX', VALID[25]]          # stay untrusted for the swipe guard

    def test_legacy_create_prefers_board_v2_tags(self, auth_client, user_profile, env):
        proj = Project.objects.create(user=user_profile, name='Tagged board',
                                      filters={'taste_tags': TAG_DICTS})
        top = [{'canonical_bld_id': b, 'score': 3.0, 'matched_keys': [], 'hit': 1, 'total': 1}
               for b in VALID[:3]]
        with mock.patch.object(matching, 'top_matches', return_value=top) as tm:
            resp = auth_client.post(
                URL, {'project_id': str(proj.project_id), 'filters': {}, 'force_new': True},
                format='json')
        assert resp.status_code == 201
        assert [(t.axis, t.polarity) for t in tm.call_args.args[0]] == [
            ('country', 'want'), ('material', 'exclude')]

    def test_legacy_create_no_match_is_404_without_board(self, auth_client, user_profile, env):
        with mock.patch.object(matching, 'top_matches', return_value=[]):
            resp = auth_client.post(URL, {'filters': {'location_country': 'Japan'}, 'name': 'Empty'},
                                    format='json')
        assert resp.status_code == 404
        assert Project.objects.count() == 0

    def test_legacy_create_does_not_use_hyde_or_relaxation(self, auth_client, user_profile, env):
        diverse = [card(b) for b in VALID[:3]]
        with mock.patch.object(engine, 'get_diverse_random', return_value=diverse), \
                mock.patch.object(engine, 'create_pool_with_relaxation') as relax, \
                mock.patch('apps.recommendation.services.embed_visual_description') as hyde:
            resp = auth_client.post(
                URL, {'filters': {}, 'visual_description': 'a glass pavilion'}, format='json')
        assert resp.status_code == 201
        relax.assert_not_called()
        hyde.assert_not_called()


@pytest.mark.django_db
class TestResumeV2:

    def _create(self, auth_client):
        return auth_client.post(URL, payload(), format='json').json()

    def test_fresh_session_state_serves_start_cards(self, auth_client, user_profile, env):
        data = self._create(auth_client)
        resp = auth_client.get(f'{URL}{data["session_id"]}/state/')
        assert resp.status_code == 200
        body = resp.json()
        assert body['next_image']['canonical_bld_id'] == VALID[0]
        assert body['prefetch_image']['canonical_bld_id'] == VALID[1]
        assert body['prefetch_image_2']['canonical_bld_id'] == VALID[2]

    def test_resume_uses_selector_after_start_cards(self, auth_client, user_profile, env):
        data = self._create(auth_client)
        s = AnalysisSession.objects.get(session_id=data['session_id'])
        s.exposed_ids = VALID[:3]
        s.save(update_fields=['exposed_ids'])
        picks = iter([(VALID[5], 'check'), (VALID[6], 'check')])
        with mock.patch.object(session_selector, 'select_next',
                               side_effect=lambda *a, **k: next(picks)) as sel:
            body = auth_client.get(f'{URL}{s.session_id}/state/').json()
        assert body['next_image']['canonical_bld_id'] == VALID[2]
        assert body['prefetch_image']['canonical_bld_id'] == VALID[5]
        assert body['prefetch_image_2']['canonical_bld_id'] == VALID[6]
        assert sel.call_count == 2
        # second lookahead sees the first prefetch as already exposed
        assert VALID[5] in sel.call_args_list[1].args[1]

    def test_converged_v2_shows_action_card_once_then_selector(self, auth_client, user_profile, env):
        data = self._create(auth_client)
        s = AnalysisSession.objects.get(session_id=data['session_id'])
        s.phase = 'converged'
        s.exposed_ids = VALID[:3]
        s.save(update_fields=['phase', 'exposed_ids'])
        first = auth_client.get(f'{URL}{s.session_id}/state/').json()
        assert first['next_image']['canonical_bld_id'] == '__action_card__'
        with mock.patch.object(session_selector, 'select_next',
                               return_value=(VALID[7], 'check')):
            second = auth_client.get(f'{URL}{s.session_id}/state/').json()
        assert second['next_image']['canonical_bld_id'] == VALID[7]
        s.refresh_from_db()
        assert VALID[7] in s.exposed_ids


@pytest.mark.django_db
class TestProjectSerializerTags:

    def _ser(self, project):
        return ProjectSerializer(project).data

    def test_board_tags(self, user_profile):
        p = Project.objects.create(user=user_profile, name='b', filters={
            'taste_tags': TAG_DICTS + [{'axis': 'country', 'value': 'Atlantis'}]})
        data = self._ser(p)
        assert data['taste_tags_source'] == 'board'
        assert [t['axis'] for t in data['taste_tags']] == ['country', 'material']   # invalid skipped

    def test_legacy_filters_mapped(self, user_profile):
        p = Project.objects.create(user=user_profile, name='b', filters={
            'program': 'Housing', 'location_country': 'Japan', 'location_city': 'Tokyo'})
        data = self._ser(p)
        assert data['taste_tags_source'] == 'legacy'
        assert {t['axis'] for t in data['taste_tags']} == {'use', 'country'}

    def test_none(self, user_profile):
        p = Project.objects.create(user=user_profile, name='b', filters={})
        data = self._ser(p)
        assert data['taste_tags'] == [] and data['taste_tags_source'] == 'none'

    def test_read_only_and_no_extra_queries(self, user_profile, django_assert_num_queries):
        fields = ProjectSerializer().fields
        assert fields['taste_tags'].read_only and fields['taste_tags_source'].read_only
        p = Project.objects.create(user=user_profile, name='b', filters={'taste_tags': TAG_DICTS})
        with django_assert_num_queries(0):
            ProjectSerializer(p).fields['taste_tags'].get_attribute(p)
            ProjectSerializer(p).get_taste_tags(p)

    def test_patch_cannot_write_tags(self, auth_client, user_profile):
        p = Project.objects.create(user=user_profile, name='b', filters={})
        resp = auth_client.patch(f'/api/v1/projects/{p.project_id}/',
                                 {'taste_tags': TAG_PAYLOAD, 'filters': {'taste_tags': TAG_DICTS}},
                                 format='json')
        assert resp.status_code in (200, 400)
        p.refresh_from_db()
        assert p.filters == {}


@pytest.mark.django_db
class TestLazyUpgradeOnResume:
    """A session created before this deploy (no selector marker) is upgraded the
    first time it is read, under a row lock, and then behaves like any v2 session."""

    def _legacy_session(self, user_profile, board=None, original_filters=None):
        proj = Project.objects.create(user=user_profile, name='Old board', filters=board or {})
        return AnalysisSession.objects.create(
            user=user_profile, project=proj, phase='exploring', status='active',
            pool_ids=VALID[:15], pool_scores={b: 9.0 for b in VALID[:15]},
            exposed_ids=[VALID[0]], initial_batch=VALID[:5], like_vectors=[],
            original_filters=original_filters or {'program': 'Housing'})

    def test_state_endpoint_upgrades_and_persists(self, auth_client, user_profile, env):
        s = self._legacy_session(user_profile)
        resp = auth_client.get(f'{URL}{s.session_id}/state/')
        assert resp.status_code == 200
        s.refresh_from_db()
        assert session_pool.is_v2(s)
        assert s.original_filters['round_offset'] == 0
        assert s.original_filters['program'] == 'Housing'               # old keys kept
        assert [t['axis'] for t in s.original_filters['taste_tags']] == ['use']
        assert s.initial_batch == []
        assert set(s.pool_scores.values()) == {3.0}                      # recomputed (score_ids mock), not 9.0

    def test_create_resume_guard_upgrades(self, auth_client, user_profile, env):
        s = self._legacy_session(user_profile)
        resp = auth_client.post(URL, {'project_id': str(s.project.project_id)}, format='json')
        assert resp.status_code == 200
        s.refresh_from_db()
        assert session_pool.is_v2(s)

    def test_second_read_does_not_rescore(self, auth_client, user_profile, env):
        s = self._legacy_session(user_profile)
        auth_client.get(f'{URL}{s.session_id}/state/')
        with mock.patch.object(matching, 'score_ids') as sc:
            auth_client.get(f'{URL}{s.session_id}/state/')
        sc.assert_not_called()

    def test_board_tags_preferred_when_upgrading(self, auth_client, user_profile, env):
        s = self._legacy_session(user_profile, board={'taste_tags': TAG_DICTS})
        auth_client.get(f'{URL}{s.session_id}/state/')
        s.refresh_from_db()
        assert s.original_filters['taste_tags'] == TAG_DICTS
