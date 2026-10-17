"""Taste-start step 5b: DB-free tests for the lazy v2 upgrade (ensure_v2), the
session-local swipe counter (round_offset) and the head_ids pool option.

No database and no buildings DB: matching.* is mocked.
"""
from types import SimpleNamespace
from unittest import mock

import pytest

import apps.recommendation.views  # noqa: F401 -- load views first (services<->views import order)
from apps.recommendation.services import swipe_service
from apps.recommendation.taste_start import matching, session_pool as sp, swipe_rules
from apps.recommendation.taste_start.recognizer import make_tag

POOL = [f'B{i:05d}' for i in range(1, 11)]
JAPAN = make_tag('country', 'Japan')


def legacy_session(*, original_filters=None, board_filters=None, pool_scores=None,
                   initial_batch=None, current_round=0):
    return SimpleNamespace(
        original_filters={} if original_filters is None else original_filters,
        project=SimpleNamespace(filters={} if board_filters is None else board_filters),
        pool_ids=list(POOL),
        pool_scores={b: 9.0 for b in POOL} if pool_scores is None else pool_scores,
        initial_batch=list(POOL[:5]) if initial_batch is None else initial_batch,
        current_round=current_round,
    )


@pytest.fixture
def score_ids():
    with mock.patch.object(matching, 'score_ids',
                           side_effect=lambda tags, ids: {i: 2.0 for i in ids}) as m:
        yield m


class TestEnsureV2:

    def test_adds_marker_scores_and_clears_initial_batch(self, score_ids):
        s = legacy_session(original_filters={'image_focus': 'exterior'},
                           board_filters={'taste_tags': [JAPAN.to_dict()]})
        assert sp.ensure_v2(s) is True
        assert sp.is_v2(s)
        assert s.original_filters['selector'] == 'taste_v2'
        assert s.original_filters['round_offset'] == 0
        assert s.original_filters['image_focus'] == 'exterior'          # old keys kept
        assert [t['axis'] for t in s.original_filters['taste_tags']] == ['country']
        assert s.initial_batch == []
        assert s.pool_ids == POOL                                       # pool untouched

    def test_legacy_scores_are_recomputed_not_reused(self, score_ids):
        s = legacy_session(board_filters={'taste_tags': [JAPAN.to_dict()]})
        sp.ensure_v2(s)
        assert set(s.pool_scores) == set(POOL)
        assert set(s.pool_scores.values()) == {2.0}                      # from score_ids, not 9.0
        (tags, ids), _ = score_ids.call_args
        assert [t.axis for t in tags] == ['country'] and list(ids) == POOL

    def test_board_tags_win_over_old_filters(self, score_ids):
        s = legacy_session(original_filters={'program': 'Housing'},
                           board_filters={'taste_tags': [JAPAN.to_dict()]})
        sp.ensure_v2(s)
        assert [t['axis'] for t in s.original_filters['taste_tags']] == ['country']

    def test_falls_back_to_old_filters_when_board_has_no_tags(self, score_ids):
        s = legacy_session(original_filters={'program': 'Housing', 'location_country': 'Japan',
                                             'location_city': 'Tokyo'})
        sp.ensure_v2(s)
        axes = {t['axis'] for t in s.original_filters['taste_tags']}
        assert axes == {'use', 'country'}                                # city has no mapping

    def test_no_filters_means_no_tags_and_no_query(self):
        # real matching.score_ids: with no scored tags it returns {} without touching a DB
        s = legacy_session()
        assert sp.ensure_v2(s) is True
        assert s.original_filters['taste_tags'] == []
        assert set(s.pool_scores) == set(POOL) and set(s.pool_scores.values()) == {0.0}

    def test_invalid_stored_board_tags_are_skipped(self, score_ids):
        s = legacy_session(board_filters={'taste_tags': [
            {'axis': 'country', 'value': 'Atlantis'}, JAPAN.to_dict()]})
        sp.ensure_v2(s)
        assert [t['value'] for t in s.original_filters['taste_tags']] == ['Japan']

    def test_idempotent(self, score_ids):
        s = legacy_session(board_filters={'taste_tags': [JAPAN.to_dict()]})
        assert sp.ensure_v2(s) is True
        snapshot = (dict(s.original_filters), dict(s.pool_scores), list(s.initial_batch))
        calls = score_ids.call_count
        assert sp.ensure_v2(s) is False
        assert (s.original_filters, s.pool_scores, s.initial_batch) == snapshot
        assert score_ids.call_count == calls

    def test_promoted_legacy_session_gets_seed_round_offset(self, score_ids):
        # promote path: seeds stored with round 0, current_round starts at their count;
        # later real swipes carry round = current_round >= 1.
        likes = [{'id': f'S{i}', 'round': 0} for i in range(10)] + [{'id': 'L1', 'round': 12}]
        s = legacy_session(current_round=13)
        s.like_vectors = likes
        assert sp.ensure_v2(s) is True
        assert s.original_filters['round_offset'] == 10
        assert sp.swipes_in_session(s) == 3
        assert not swipe_rules.convergence_floor_met(sp.swipes_in_session(s))

    def test_normal_legacy_session_offset_stays_zero(self, score_ids):
        s = legacy_session(current_round=6)
        s.like_vectors = [{'id': 'L1', 'round': 2}, {'id': 'L2', 'round': 5}]
        sp.ensure_v2(s)
        assert s.original_filters['round_offset'] == 0

    def test_existing_v2_session_untouched(self, score_ids):
        s = legacy_session(original_filters={'selector': 'taste_v2', 'taste_tags': [],
                                             'round_offset': 4},
                           initial_batch=['B00001'])
        assert sp.ensure_v2(s) is False
        assert s.initial_batch == ['B00001'] and s.original_filters['round_offset'] == 4
        score_ids.assert_not_called()

    def test_ensure_v2_locked_skips_db_for_v2_sessions(self):
        s = legacy_session(original_filters={'selector': 'taste_v2'})
        assert sp.ensure_v2_locked(s) is s            # no query, same object


class TestRoundOffset:

    def test_swipes_in_session_subtracts_offset(self):
        s = SimpleNamespace(current_round=13, original_filters={'round_offset': 10})
        assert sp.round_offset(s) == 10
        assert sp.swipes_in_session(s) == 3

    def test_missing_or_bad_offset_is_zero(self):
        assert sp.swipes_in_session(SimpleNamespace(current_round=5, original_filters={})) == 5
        assert sp.swipes_in_session(SimpleNamespace(current_round=5, original_filters=None)) == 5
        bad = SimpleNamespace(current_round=5, original_filters={'round_offset': 'x'})
        assert sp.swipes_in_session(bad) == 5

    def test_never_negative(self):
        s = SimpleNamespace(current_round=2, original_filters={'round_offset': 10})
        assert sp.swipes_in_session(s) == 0

    def test_promoted_session_needs_eight_swipes_of_its_own(self):
        """Seeded likes (current_round starts at 10) must not satisfy the floor."""
        s = SimpleNamespace(current_round=10, original_filters={'round_offset': 10})
        for n in range(1, 9):
            s.current_round = 10 + n
            assert swipe_rules.convergence_floor_met(sp.swipes_in_session(s)) is (n >= 8)

    def test_plain_session_floor_unchanged(self):
        s = SimpleNamespace(current_round=8, original_filters={})
        assert swipe_rules.convergence_floor_met(sp.swipes_in_session(s))


class TestBuildPoolHeadIds:

    def test_head_ids_follow_start_ids_and_stay_in_pool(self):
        ranked = [{'canonical_bld_id': b, 'score': 1.0} for b in POOL[3:]]
        with mock.patch.object(matching, 'ranked_pool', return_value=ranked) as rp, \
                mock.patch.object(matching, 'score_ids',
                                  side_effect=lambda t, ids: {i: 1.0 for i in ids}):
            pool, scores = sp.build_pool([JAPAN], [POOL[0]], [], head_ids=['SEED1', POOL[1], 'SEED2'])
        assert pool[:4] == [POOL[0], 'SEED1', POOL[1], 'SEED2']
        assert set(scores) == set(pool) and len(set(pool)) == len(pool)
        assert {POOL[0], 'SEED1', POOL[1], 'SEED2'} <= set(rp.call_args.kwargs['exclude_ids'])

    def test_no_head_ids_is_unchanged(self):
        ranked = [{'canonical_bld_id': b, 'score': 1.0} for b in POOL[3:]]
        with mock.patch.object(matching, 'ranked_pool', return_value=ranked), \
                mock.patch.object(matching, 'score_ids',
                                  side_effect=lambda t, ids: {i: 1.0 for i in ids}):
            pool, _ = sp.build_pool([JAPAN], POOL[:3], [])
        assert pool == POOL


class TestSyncPrefetchSignatureTolerance:

    def test_legacy_positional_call_without_ctx_returns_none_pair(self):
        out = swipe_service.compute_sync_prefetch(
            'exploring', ['B00001'], ['B00001', 'B00002'], 0, POOL, {}, [])
        assert out == (None, None)

    def test_ctx_switches_to_selector_lookahead(self):
        with mock.patch.object(swipe_rules, 'lookahead', return_value=('B00004', 'B00005')) as la:
            out = swipe_service.compute_sync_prefetch(
                'analyzing', ['B00001'], [], 3, POOL, {}, [], selector_ctx=object())
        assert out == ('B00004', 'B00005')
        assert la.call_count == 1

    def test_lookahead_error_degrades_to_none_pair(self):
        with mock.patch.object(swipe_rules, 'lookahead', side_effect=RuntimeError('boom')):
            out = swipe_service.compute_sync_prefetch(
                selector_ctx=object(), saved_pool_ids=POOL)
        assert out == (None, None)
