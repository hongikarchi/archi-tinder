"""Taste-start step 3-3: taste_v2 swipe path (Postgres-backed; run via `make test-local`).

The buildings DB is never touched: matching.*, engine embeddings / card lookups and
the pool top-up fallbacks are mocked. Embeddings live in the mutable `world['emb']`
dict so a test can hand-craft similarities.
"""
import logging
import re
from unittest import mock

import numpy as np
import pytest
from django.conf import settings
from django.core.cache import cache

import apps.recommendation.views  # noqa: F401 -- load views first (services<->views import order)
from apps.recommendation import engine
from apps.recommendation.models import AnalysisSession, Project, SwipeEvent
from apps.recommendation.services import swipe_service
from apps.recommendation.taste_start import matching, session_pool, session_selector

URL = '/api/v1/analysis/sessions/'
VALID = [f'B{i:05d}' for i in range(1, 31)]
TAG_PAYLOAD = [{'axis': 'country', 'value': 'Japan', 'polarity': 'want'}]
SWIPE_VIEW = 'apps.recommendation.views.swipe'


def _random_emb():
    out = {}
    for i, b in enumerate(VALID):
        v = np.random.RandomState(i).randn(384)
        out[b] = v / np.linalg.norm(v)
    return out


def card(bid):
    return {'canonical_bld_id': bid, 'name': f'Building {bid}', 'image_url': 'x',
            'metadata': {}} if bid else None


class _RecordingThread:
    """Records thread launches instead of running them."""
    started = []

    def __init__(self, target=None, args=(), kwargs=None, daemon=None):
        self._rec = (target, args, kwargs or {})

    def start(self):
        _RecordingThread.started.append(self._rec)


@pytest.fixture
def world():
    """Mock the buildings-DB boundary. `world['emb']` / `world['ranked']` are mutable."""
    cache.clear()
    _RecordingThread.started = []
    w = {'emb': _random_emb(), 'ranked': list(VALID[3:])}

    def ranked_pool(tags, limit=150, exclude_ids=()):
        excl = set(exclude_ids)
        return [{'canonical_bld_id': b, 'score': 3.0}
                for b in w['ranked'] if b not in excl][:limit]

    def pool_emb(ids):
        return {i: w['emb'][i] for i in ids if i in w['emb']}

    rc = {'taste_v2_pool_refresh_threshold': 1, 'async_prefetch_enabled': False}
    with mock.patch.dict(settings.RECOMMENDATION, rc), \
            mock.patch.object(engine, 'get_buildings_by_ids',
                              side_effect=lambda ids: [
                                  card(i) for i in ids if i in w['emb']]), \
            mock.patch.object(engine, 'get_building_card', side_effect=card), \
            mock.patch.object(engine, 'get_pool_embeddings', side_effect=pool_emb), \
            mock.patch.object(engine, 'get_building_embedding',
                              side_effect=lambda b: w['emb'][b].tolist() if b in w['emb'] else None), \
            mock.patch.object(engine, 'taste_ranked_page', return_value=[]), \
            mock.patch.object(engine, '_random_pool', return_value=[]), \
            mock.patch.object(matching, 'ranked_pool', side_effect=ranked_pool), \
            mock.patch.object(matching, 'score_ids',
                              side_effect=lambda tags, ids: {i: 3.0 for i in ids}), \
            mock.patch(f'{SWIPE_VIEW}.threading.Thread', _RecordingThread), \
            mock.patch(f'{SWIPE_VIEW}._emit_telemetry_thread', lambda *a, **k: None):
        yield w


def create(client, start=None, **kw):
    body = {'name': 'Japan', 'raw_query': 'japan', 'taste_tags': TAG_PAYLOAD,
            'start_ids': start or VALID[:3]}
    body.update(kw)
    resp = client.post(URL, body, format='json')
    assert resp.status_code == 201, resp.content
    return resp.json()


def swipe(client, sid, bid, action, key, **extra):
    body = {'canonical_bld_id': bid, 'action': action, 'idempotency_key': key}
    body.update(extra)
    resp = client.post(f'{URL}{sid}/swipes/', body, format='json')
    assert resp.status_code == 200, resp.content
    return resp.json()


def nid(payload, key='next_image'):
    return (payload.get(key) or {}).get('canonical_bld_id')


def kinds_from(caplog):
    found = (re.search(r'kind=(\w+|-)', r.getMessage())
             for r in caplog.records if 'SWIPE TIMING' in r.getMessage())
    return [m.group(1) for m in found if m]


@pytest.mark.django_db
class TestV2SwipeFlow:

    def test_start_cards_then_check_cards_without_likes(self, auth_client, user_profile, world, caplog):
        caplog.set_level(logging.INFO, logger='apps.recommendation')
        sid = create(auth_client)['session_id']
        r1 = swipe(auth_client, sid, VALID[0], 'dislike', 'k1')
        r2 = swipe(auth_client, sid, VALID[1], 'dislike', 'k2')
        r3 = swipe(auth_client, sid, VALID[2], 'dislike', 'k3')
        assert nid(r1) == VALID[1] and nid(r2) == VALID[2]
        assert nid(r3) not in VALID[:3] and nid(r3) is not None
        assert kinds_from(caplog) == ['start', 'start', 'check']

    def test_one_like_alternates_match_and_check(self, auth_client, user_profile, world, caplog):
        caplog.set_level(logging.INFO, logger='apps.recommendation')
        sid = create(auth_client)['session_id']
        nxt = VALID[0]
        for n, action in enumerate(['like', 'dislike', 'dislike', 'dislike', 'dislike', 'dislike']):
            nxt = nid(swipe(auth_client, sid, nxt, action, f'k{n}'))
        # cards 4..6 follow 1 like -> share 0.5 -> match, check, match; the 5th
        # consecutive skip (swipe 6) forces an all-check card.
        assert kinds_from(caplog) == ['start', 'start', 'match', 'check', 'match', 'check']

    def test_phase_moves_to_analyzing_on_first_like(self, auth_client, user_profile, world):
        sid = create(auth_client)['session_id']
        swipe(auth_client, sid, VALID[0], 'like', 'k1')
        assert AnalysisSession.objects.get(session_id=sid).phase == 'analyzing'

    def test_no_convergence_before_eight_swipes(self, auth_client, user_profile, world):
        sid = create(auth_client)['session_id']
        nxt, converged_at, resp = VALID[0], None, None
        with mock.patch.object(engine, 'check_convergence', return_value=True):
            for n in range(1, 9):
                resp = swipe(auth_client, sid, nxt, 'like', f'k{n}')
                phase = AnalysisSession.objects.get(session_id=sid).phase
                if phase == 'converged' and converged_at is None:
                    converged_at = n
                nxt = nid(resp)
                if n < 8:
                    assert phase == 'analyzing', f'converged too early at swipe {n}'
        assert converged_at == 8
        assert nid(resp) == '__action_card__'

    def test_dislike_history_lowers_similar_match_candidate(self, auth_client, user_profile, world):
        def basis(i):
            v = np.zeros(384)
            v[i] = 1.0
            return v

        def mix(i, j):
            return (basis(i) + basis(j)) / np.sqrt(2)

        def run(with_dislike):
            AnalysisSession.objects.all().delete()
            Project.objects.all().delete()
            cache.clear()
            world['emb'] = {'S1': basis(0), 'S2': basis(1), 'S3': basis(2),
                            'C1': mix(0, 5), 'C2': mix(0, 6), 'DX': basis(5)}
            world['ranked'] = ['C1', 'C2']
            sid = create(auth_client, start=['S1', 'S2', 'S3'])['session_id']
            if with_dislike:
                p = AnalysisSession.objects.get(session_id=sid).project
                p.disliked_ids = ['DX']              # a skip from earlier on the same board
                p.save(update_fields=['disliked_ids'])
            swipe(auth_client, sid, 'S1', 'like', 'k1')
            swipe(auth_client, sid, 'S2', 'dislike', 'k2')
            return nid(swipe(auth_client, sid, 'S3', 'dislike', 'k3'))

        assert run(with_dislike=False) == 'C1'     # tie -> pool order
        assert run(with_dislike=True) == 'C2'      # C1 resembles a skipped building

    def test_recent_actions_queried_once_per_swipe(self, auth_client, user_profile, world):
        sid = create(auth_client)['session_id']
        for n, (bid, action) in enumerate([(VALID[0], 'like'), (VALID[1], 'dislike')]):
            with mock.patch.object(swipe_service, '_recent_actions',
                                   wraps=swipe_service._recent_actions) as ra:
                swipe(auth_client, sid, bid, action, f'k{n}')
            assert ra.call_count == 1

    def test_action_card_flow_unchanged(self, auth_client, user_profile, world):
        sid = create(auth_client)['session_id']
        s = AnalysisSession.objects.get(session_id=sid)
        s.phase = 'converged'
        s.exposed_ids = VALID[:3]
        s.save(update_fields=['phase', 'exposed_ids'])
        r = swipe(auth_client, sid, VALID[0], 'like', 'k1')
        assert nid(r) == '__action_card__'
        r = swipe(auth_client, sid, '__action_card__', 'dislike', 'k2')
        assert nid(r) not in (None, '__action_card__')
        s.refresh_from_db()
        assert s.action_card_shown is True
        r = swipe(auth_client, sid, nid(r), 'like', 'k3')
        assert r['next_image'] is not None          # converged-continue serves real cards
        r = swipe(auth_client, sid, '__action_card__', 'like', 'k4')
        assert r['is_analysis_completed'] is True and r['next_image'] is None


@pytest.mark.django_db
class TestV2PoolRefresh:

    def test_refresh_fields_persisted(self, auth_client, user_profile, world):
        with mock.patch.dict(settings.RECOMMENDATION, {
                'bounded_pool_target': 3, 'taste_v2_pool_refresh_threshold': 5}):
            sid = create(auth_client)['session_id']
            before = AnalysisSession.objects.get(session_id=sid)
            n_before, tier_before = len(before.pool_ids), before.current_pool_tier
            swipe(auth_client, sid, VALID[0], 'dislike', 'k1')
            swipe(auth_client, sid, VALID[1], 'dislike', 'k2')
        after = AnalysisSession.objects.get(session_id=sid)
        assert len(after.pool_ids) > n_before
        assert after.current_pool_tier >= max(2, tier_before)
        assert set(after.pool_scores) >= set(after.pool_ids)

    def test_off_tag_flag_persisted(self, auth_client, user_profile, world):
        sid = create(auth_client)['session_id']
        s = AnalysisSession.objects.get(session_id=sid)
        extra = [f'X{i}' for i in range(5)]
        world['emb'].update({b: np.eye(384)[100 + i] for i, b in enumerate(extra)})
        world['ranked'] = []                       # every tag-matching building is used up
        with mock.patch.object(engine, '_random_pool', return_value=extra):
            s.exposed_ids = list(s.pool_ids)       # 0 unexposed -> refresh triggers
            s.save(update_fields=['exposed_ids'])
            swipe(auth_client, sid, VALID[0], 'dislike', 'k1')
        s.refresh_from_db()
        assert s.original_filters.get('off_tag') is True
        assert session_pool.is_v2(s) and set(extra) <= set(s.pool_ids)

    def test_unembeddable_pool_ids_do_not_strand_the_user(self, auth_client, user_profile, world):
        sid = create(auth_client, start=VALID[:3])['session_id']
        s = AnalysisSession.objects.get(session_id=sid)
        ghosts = [f'G{i:04d}' for i in range(4)]          # in the pool, but no embedding
        s.pool_ids = VALID[:3] + ghosts
        s.pool_scores = {b: 3.0 for b in s.pool_ids}
        s.exposed_ids = VALID[:3]
        s.save(update_fields=['pool_ids', 'pool_scores', 'exposed_ids'])
        world['ranked'] = VALID[3:8]                      # fresh, embeddable ids exist
        r = swipe(auth_client, sid, VALID[0], 'dislike', 'k1')
        assert nid(r) in VALID[3:8]


@pytest.mark.django_db
class TestV2Prefetch:

    def test_sync_prefetch_ids_distinct(self, auth_client, user_profile, world):
        sid = create(auth_client)['session_id']
        r = swipe(auth_client, sid, VALID[0], 'dislike', 'k1')
        assert r['prefetch_strategy'] == 'sync'
        assert nid(r) == VALID[1] and nid(r, 'prefetch_image') == VALID[2]   # remaining start cards
        r = swipe(auth_client, sid, VALID[1], 'dislike', 'k2')
        ids = [nid(r), nid(r, 'prefetch_image'), nid(r, 'prefetch_image_2')]
        assert ids[0] == VALID[2]
        assert all(ids) and len(set(ids)) == 3
        assert not ({ids[1], ids[2]} & set(VALID[:3]))

    def test_async_prefetch_thread_caches_v2_ids(self, auth_client, user_profile, world):
        sid = create(auth_client)['session_id']
        with mock.patch.dict(settings.RECOMMENDATION, {'async_prefetch_enabled': True}), \
                mock.patch('django.db.connections.close_all'):
            r1 = swipe(auth_client, sid, VALID[0], 'dislike', 'k1')
            assert r1['prefetch_strategy'] == 'async-thread'
            threads = [t for t in _RecordingThread.started
                       if getattr(t[0], '__name__', '') == '_async_prefetch_thread']
            assert len(threads) == 1
            target, args, kwargs = threads[0]
            assert kwargs['selector_ctx_snap'] is not None
            target(*args, **kwargs)
            cached = cache.get(f'prefetch:{sid}:2')
            assert cached and cached['prefetch_card_id'] and cached['prefetch_card_2_id']
            assert cached['prefetch_card_id'] != cached['prefetch_card_2_id']
            assert not ({cached['prefetch_card_id'], cached['prefetch_card_2_id']}
                        & set(VALID[:3]))
            r2 = swipe(auth_client, sid, VALID[1], 'dislike', 'k2')
        assert nid(r2) == VALID[2]
        assert nid(r2, 'prefetch_image') == cached['prefetch_card_id']
        ids = [i for i in (nid(r2), nid(r2, 'prefetch_image'), nid(r2, 'prefetch_image_2')) if i]
        assert len(set(ids)) == len(ids)


@pytest.mark.django_db
class TestLegacySessionUpgradedOnSwipe:
    """A marker-less (pre-deploy) session is upgraded under the swipe's row lock and
    then goes through the v2 selector -- nothing legacy is left on the swipe path."""

    def _legacy_session(self, user_profile, phase='exploring'):
        proj = Project.objects.create(user=user_profile, name='Old board', filters={})
        return AnalysisSession.objects.create(
            user=user_profile, project=proj, phase=phase, status='active',
            pool_ids=VALID[:20], pool_scores={b: 9.0 for b in VALID[:20]},
            exposed_ids=[VALID[0]], initial_batch=VALID[:5], like_vectors=[],
            original_filters={'program': 'Housing'})

    def test_first_swipe_upgrades_and_uses_selector(self, auth_client, user_profile, world):
        s = self._legacy_session(user_profile)
        with mock.patch.object(session_selector, 'select_next',
                               wraps=session_selector.select_next) as sel:
            r = swipe(auth_client, str(s.session_id), VALID[0], 'like', 'leg1')
        assert sel.call_count >= 1
        assert r['next_image'] is not None
        s.refresh_from_db()
        assert session_pool.is_v2(s)
        assert s.initial_batch == []                         # legacy start cards not re-served
        assert s.original_filters['round_offset'] == 0
        assert s.phase == 'analyzing'                        # first like
        assert SwipeEvent.objects.filter(session=s).count() == 1

    def test_extend_upgrades_a_converged_legacy_session(self, auth_client, user_profile, world):
        s = self._legacy_session(user_profile, phase='converged')
        resp = auth_client.post(
            f'{URL}{s.session_id}/swipes/',
            {'canonical_bld_id': VALID[0], 'action': 'like', 'extend': True}, format='json')
        assert resp.status_code == 200
        s.refresh_from_db()
        assert session_pool.is_v2(s) and s.initial_batch == []
        assert s.phase == 'analyzing'


@pytest.mark.django_db
class TestPromotedSessionConvergenceFloor:

    def test_floor_counts_swipes_in_this_session(self, auth_client, user_profile, world):
        """current_round starts at the seeded like count; only own swipes count."""
        sid = create(auth_client)['session_id']
        s = AnalysisSession.objects.get(session_id=sid)
        s.current_round = 10
        s.original_filters = {**s.original_filters, 'round_offset': 10}
        s.phase = 'analyzing'
        s.save(update_fields=['current_round', 'original_filters', 'phase'])
        nxt = VALID[0]
        with mock.patch.object(engine, 'check_convergence', return_value=True):
            for n in range(1, 9):
                resp = swipe(auth_client, sid, nxt, 'like', f'f{n}')
                phase = AnalysisSession.objects.get(session_id=sid).phase
                assert phase == ('converged' if n == 8 else 'analyzing'), f'swipe {n}'
                nxt = nid(resp)
