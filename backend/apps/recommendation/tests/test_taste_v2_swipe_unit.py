"""Taste-start step 3-3: DB-free tests for the v2 swipe-path helpers."""
from types import SimpleNamespace
from unittest import mock

import numpy as np
import pytest
from django.conf import settings

import apps.recommendation.views  # noqa: F401 -- load views first (services<->views import order)
from apps.recommendation.services import swipe_service
from apps.recommendation.taste_start import session_pool as sp
from apps.recommendation.taste_start import session_selector as sel
from apps.recommendation.taste_start import swipe_rules
from apps.recommendation.taste_start.recognizer import make_tag

DIM = 384


def e(i):
    v = np.zeros(DIM)
    v[i] = 1.0
    return v


IDS = [f'B{i:05d}' for i in range(1, 21)]
EMB = {b: e(i) for i, b in enumerate(IDS)}


# -- phase / convergence rules -------------------------------------------------
def test_analyzing_threshold_default_is_one_like():
    assert not swipe_rules.should_enter_analyzing(0)
    assert swipe_rules.should_enter_analyzing(1)
    assert swipe_rules.should_enter_analyzing(5)


def test_analyzing_threshold_follows_setting():
    with mock.patch.dict(settings.RECOMMENDATION, {'taste_v2_analyzing_min_likes': 3}):
        assert not swipe_rules.should_enter_analyzing(2)
        assert swipe_rules.should_enter_analyzing(3)


def test_convergence_floor_is_eight_swipes():
    assert not swipe_rules.convergence_floor_met(7)
    assert swipe_rules.convergence_floor_met(8)
    with mock.patch.dict(settings.RECOMMENDATION, {'taste_v2_convergence_min_swipes': 4}):
        assert swipe_rules.convergence_floor_met(4)


# -- lookahead exposure lists (select_next mocked) ------------------------------
@pytest.fixture
def fake_select():
    calls = []
    order = iter(IDS[10:])

    def fn(pool, exposed, emb, batch, ctx):
        calls.append(list(exposed))
        return next(order), 'check'

    with mock.patch.object(sel, 'select_next', side_effect=fn):
        yield calls


def test_lookahead_sync_exposure_lists(fake_select):
    pf1, pf2 = swipe_rules.lookahead(IDS, ['x'], EMB, [], sel.SelectorCtx())
    assert (pf1, pf2) == (IDS[10], IDS[11])
    assert fake_select == [['x'], ['x', IDS[10]]]


def test_lookahead_async_skips_the_next_swipes_own_card(fake_select):
    pf1, pf2 = swipe_rules.lookahead(IDS, ['x'], EMB, [], sel.SelectorCtx(), skip_next=True)
    # a = IDS[10] is the next swipe's own card; the cached slots are the two after it
    assert (pf1, pf2) == (IDS[11], IDS[12])
    assert fake_select == [['x'], ['x', IDS[10]], ['x', IDS[10], IDS[11]]]


def test_lookahead_stops_when_nothing_selectable():
    with mock.patch.object(sel, 'select_next', return_value=(None, 'check')):
        assert swipe_rules.lookahead(IDS, [], EMB, [], sel.SelectorCtx()) == (None, None)
        assert swipe_rules.lookahead(IDS, [], EMB, [], sel.SelectorCtx(),
                                     skip_next=True) == (None, None)


def test_lookahead_real_selector_no_duplicates_and_start_cards_first():
    ctx = sel.SelectorCtx(w_want=3.0, n_likes=0, check_share=1.0,
                          pool_scores={b: 3.0 for b in IDS})
    batch = IDS[:3]
    pf1, pf2 = swipe_rules.lookahead(IDS, [IDS[0]], EMB, batch, ctx)
    assert (pf1, pf2) == (IDS[1], IDS[2])                      # remaining start cards
    pf1, pf2 = swipe_rules.lookahead(IDS, IDS[:3], EMB, batch, ctx)
    assert pf1 and pf2 and pf1 != pf2
    assert not ({pf1, pf2} & set(IDS[:3]))


# -- session_pool: force refresh + ctx without extra queries ---------------------
def _v2_session(pool, exposed):
    tags = [make_tag('country', 'Japan')]
    return SimpleNamespace(
        pool_ids=list(pool), exposed_ids=list(exposed), pool_scores={p: 1.0 for p in pool},
        current_pool_tier=1, current_round=3, multimodal_floor=None, session_id='s1',
        original_filters={'selector': 'taste_v2', 'taste_tags': [t.to_dict() for t in tags]})


def test_refresh_force_skips_threshold():
    s = _v2_session(IDS[:15], [])        # 15 remaining < 20 default threshold
    with mock.patch.object(sp, 'matching') as matching:
        matching.ranked_pool.return_value = [{'canonical_bld_id': 'NEW1', 'score': 2.0}]
        with mock.patch.dict(settings.RECOMMENDATION, {'taste_v2_pool_refresh_threshold': 5}):
            assert sp.refresh_if_low(s, []) is False         # 15 >= 5
            assert sp.refresh_if_low(s, [], force=True) is True
    assert s.pool_ids[-1] == 'NEW1' and s.current_pool_tier == 2


def test_build_session_ctx_uses_given_recent_actions_and_project():
    s = _v2_session(IDS[:5], [])
    project = SimpleNamespace(disliked_ids=[IDS[3], 'junk', IDS[4]])
    with mock.patch.object(sp.engine, 'get_pool_embeddings',
                           side_effect=lambda ids: {i: EMB[i] for i in ids if i in EMB}) as gpe:
        ctx = sp.build_session_ctx(s, [], project=project,
                                   recent_actions=['dislike'] * 5)
    assert gpe.call_args.args[0] == [IDS[3], 'junk', IDS[4]]
    assert len(ctx.dislike_vectors) == 2
    assert ctx.check_share == 1.0 and ctx.n_likes == 0
    assert ctx.w_want == 3.0


def test_recent_actions_window_covers_selector_needs():
    assert sp.recent_actions_window() >= 5


def _run_v2_select(select_results, refresh_results):
    session = SimpleNamespace(pool_ids=['a'], exposed_ids=[], pool_scores={},
                              initial_batch=[])
    ctx = SimpleNamespace(pool_scores={})
    sp_ = swipe_service.session_pool
    with mock.patch.object(sp_, 'build_session_ctx', return_value=ctx), \
            mock.patch.object(swipe_service.engine, 'get_pool_embeddings',
                              return_value={}), \
            mock.patch.object(swipe_service.engine, 'get_last_embedding_call_stats',
                              return_value={}), \
            mock.patch.object(swipe_service.session_selector, 'select_next',
                              side_effect=select_results) as sel_m, \
            mock.patch.object(sp_, 'refresh_if_low',
                              side_effect=refresh_results) as ref_m:
        out = swipe_service._v2_select_card(session, [], None, [])
    return out, sel_m, ref_m


def test_v2_select_card_retries_forced_refresh_until_card_found():
    out, sel_m, ref_m = _run_v2_select(
        [(None, '-'), (None, '-'), ('B1', 'check')], [True, True])
    assert out[0] == 'B1' and out[1] == 'check' and out[5] is True
    assert ref_m.call_count == 2 and sel_m.call_count == 3
    assert all(c.kwargs.get('force') is True for c in ref_m.call_args_list)


def test_v2_select_card_stops_when_refresh_returns_nothing():
    out, sel_m, ref_m = _run_v2_select([(None, '-'), (None, '-')], [True, False])
    assert out[0] is None and out[5] is True
    assert ref_m.call_count == 2 and sel_m.call_count == 2


def test_v2_select_card_caps_forced_refresh_attempts():
    out, sel_m, ref_m = _run_v2_select([(None, '-')] * 4, [True] * 5)
    assert out[0] is None and out[5] is True
    assert ref_m.call_count == 3 and sel_m.call_count == 4


def test_v2_select_card_no_refresh_when_card_selected():
    out, sel_m, ref_m = _run_v2_select([('B1', 'start')], [True])
    assert out[0] == 'B1' and out[5] is False
    assert ref_m.call_count == 0
