"""Taste-start step 3-1: pure selector (no DB). Synthetic normalized vectors."""
import numpy as np
import pytest

from apps.recommendation.taste_start import session_selector as sel
from apps.recommendation.taste_start.recognizer import make_tag

DIM = 384


def vec(*pairs):
    """Normalized 384-d vector from (axis_index, weight) pairs."""
    v = np.zeros(DIM)
    for i, w in pairs:
        v[i] = w
    return v / np.linalg.norm(v)


def e(i):
    return vec((i, 1.0))


def kinds(s, n=8):
    return [sel.card_kind(j, s)[0].upper() for j in range(n)]


def likes(vector, n):
    return [{'embedding': vector, 'round': r + 1} for r in range(n)]


def ctx(**kw):
    base = dict(pool_scores={}, w_want=3.0, n_likes=0, check_share=0.0)
    base.update(kw)
    return sel.SelectorCtx(**base)


# -- card_kind ------------------------------------------------------------------
def test_card_kind_all_check():
    assert kinds(1.0) == ['C'] * 8


def test_card_kind_half_starts_with_match():
    assert kinds(0.5) == list('MCMCMCMC')


def test_card_kind_quarter_is_mmmc():
    assert kinds(0.25) == list('MMMCMMMC')


def test_card_kind_zero_is_all_match():
    assert kinds(0.0) == ['M'] * 8


# -- check_share ------------------------------------------------------------------
def test_check_share_zero_likes_is_all_check():
    assert sel.check_share(0, [], []) == 1.0


def test_check_share_one_like():
    assert sel.check_share(1, [e(0)], ['like']) == 0.5


def test_check_share_two_consistent_likes():
    a, b = vec((0, 1), (1, 0.2)), vec((0, 1), (2, 0.2))
    assert sel.check_share(2, [a, b], ['like', 'like']) == 0.25


def test_check_share_two_inconsistent_likes():
    assert sel.check_share(2, [e(0), e(1)], ['like', 'like']) == 0.5


def test_check_share_uses_last_window_only():
    old = [e(5), e(6), e(7)]
    recent = [e(0), vec((0, 1), (1, 0.1)), vec((0, 1), (2, 0.1)), vec((0, 1), (3, 0.1))]
    assert sel.check_share(7, old + recent, []) == 0.25


def test_skip_streak_three_raises_to_half():
    a, b = vec((0, 1), (1, 0.2)), vec((0, 1), (2, 0.2))
    acts = ['like', 'like', 'dislike', 'dislike', 'dislike']
    assert sel.check_share(2, [a, b], acts) == 0.5


def test_skip_streak_five_is_all_check():
    a, b = vec((0, 1), (1, 0.2)), vec((0, 1), (2, 0.2))
    assert sel.check_share(2, [a, b], ['dislike'] * 5) == 1.0


def test_non_trailing_skips_do_not_count():
    a, b = vec((0, 1), (1, 0.2)), vec((0, 1), (2, 0.2))
    acts = ['dislike'] * 4 + ['like']
    assert sel.check_share(2, [a, b], acts) == 0.25


# -- start cards --------------------------------------------------------------------
def test_start_cards_served_in_order_skipping_exposed():
    emb = {k: e(i) for i, k in enumerate('abcdef')}
    pool = list('abcdef')
    assert sel.select_next(pool, [], emb, ['a', 'b', 'c'], ctx()) == ('a', 'start')
    assert sel.select_next(pool, ['a'], emb, ['a', 'b', 'c'], ctx()) == ('b', 'start')
    assert sel.select_next(pool, ['a', 'c'], emb, ['a', 'b', 'c'], ctx()) == ('b', 'start')
    # start cards are served even when absent from the candidate pool / emb
    assert sel.select_next([], [], {}, ['x'], ctx()) == ('x', 'start')


# -- MATCH --------------------------------------------------------------------------
def _match_setup(n_likes):
    like = e(0)
    emb = {
        'start': e(9),
        'A': vec((5, 1.0), (6, 0.2)),               # tag-perfect, unrelated to likes
        'B': vec((0, 0.9), (7, 0.436)),             # cos ~0.9 to the like, no tag
    }
    c = ctx(pool_scores={'A': 3.0, 'B': 0.0}, w_want=3.0, n_likes=n_likes,
            like_vectors=likes(like, n_likes), current_round=n_likes + 1)
    return emb, c


def test_match_weight_shifts_from_tag_to_likes():
    emb, c1 = _match_setup(1)
    assert sel.select_next(['A', 'B'], ['start'], emb, ['start'], c1) == ('A', 'match')
    emb, c6 = _match_setup(6)
    assert sel.select_next(['A', 'B'], ['start'], emb, ['start'], c6) == ('B', 'match')


def test_dislike_lowers_nearby_candidate():
    like = e(0)
    emb = {'start': e(9), 'C1': vec((0, 1), (1, 1)), 'C2': vec((0, 1), (2, 1))}
    base = dict(pool_scores={'C1': 3.0, 'C2': 3.0}, w_want=3.0, n_likes=1,
                like_vectors=likes(like, 1), current_round=2)
    tied = ctx(**base)
    assert sel.select_next(['C1', 'C2'], ['start'], emb, ['start'], tied)[0] == 'C1'
    disliked = ctx(dislike_vectors=[e(1)], **base)
    assert sel.select_next(['C1', 'C2'], ['start'], emb, ['start'], disliked)[0] == 'C2'


def test_no_want_tags_means_zero_tag_weight():
    # w_want == 0: tag score is ignored, pure likes relevance decides.
    like = e(0)
    emb = {'start': e(9), 'A': e(5), 'B': vec((0, 0.9), (7, 0.436))}
    c = ctx(pool_scores={'A': 99.0}, w_want=0.0, n_likes=1,
            like_vectors=likes(like, 1), current_round=2)
    assert sel.select_next(['A', 'B'], ['start'], emb, ['start'], c) == ('B', 'match')


def test_match_with_zero_likes_falls_back_to_check():
    emb = {'start': e(0), 'near': vec((0, 1), (1, 0.1)), 'far': e(5)}
    c = ctx(pool_scores={'near': 3.0, 'far': 3.0}, n_likes=0, check_share=0.0)
    bid, kind = sel.select_next(['near', 'far'], ['start'], emb, ['start'], c)
    assert (bid, kind) == ('far', 'check')


def test_empty_candidates_returns_none():
    emb = {'start': e(0)}
    bid, kind = sel.select_next(['start'], ['start'], emb, ['start'], ctx(check_share=1.0))
    assert bid is None and kind == 'check'


def test_candidates_without_embedding_are_skipped():
    emb = {'start': e(0), 'ok': e(5)}
    bid, _ = sel.select_next(['ghost', 'ok'], ['start'], emb, ['start'], ctx(check_share=1.0))
    assert bid == 'ok'


# -- CHECK --------------------------------------------------------------------------
def _check_setup(scores, w_want=3.0):
    emb = {
        'start': e(0),
        'a': vec((0, 0.9), (1, 0.436)),    # near the start card, full tag
        'b': vec((0, 0.1), (2, 0.995)),    # far-ish, full tag
        'c': vec((0, -1.0)),               # farthest overall, low tag
    }
    return emb, ctx(pool_scores=scores, w_want=w_want, check_share=1.0)


def test_check_picks_farthest_within_tag_band():
    emb, c = _check_setup({'a': 3.0, 'b': 3.0, 'c': 0.3})
    assert sel.select_next(['a', 'b', 'c'], ['start'], emb, ['start'], c) == ('b', 'check')


def test_check_falls_back_to_all_when_no_tag_info():
    emb, c = _check_setup({}, w_want=3.0)           # all tag scores 0 -> everyone in band
    assert sel.select_next(['a', 'b', 'c'], ['start'], emb, ['start'], c)[0] == 'c'
    emb, c = _check_setup({'a': 3.0}, w_want=0.0)   # no want tags -> no band
    assert sel.select_next(['a', 'b', 'c'], ['start'], emb, ['start'], c)[0] == 'c'


def test_check_is_deterministic_without_exposed_embeddings():
    emb = {'x': e(1), 'y': e(2)}
    c = ctx(check_share=1.0)
    assert sel.select_next(['x', 'y'], ['ghost'], emb, [], c)[0] == 'x'


# -- build_ctx ----------------------------------------------------------------------
def test_build_ctx_w_want_ignores_exclude_and_unbuilt_ok():
    tags = [make_tag('country', 'Japan'), make_tag('material', 'wood'),
            make_tag('material', 'brick', polarity='exclude'),
            make_tag('built', 'unbuilt_ok')]
    c = sel.build_ctx({'a': 5.0}, tags, [], [], [], None, 1)
    assert c.w_want == 5.0            # country 3 + material 2
    assert c.n_likes == 0 and c.check_share == 1.0


def test_build_ctx_check_share_from_likes_and_actions():
    lv = likes(e(0), 1)
    c = sel.build_ctx({}, [], lv, [e(1)], ['like'], None, 2)
    assert c.n_likes == 1 and c.check_share == 0.5 and c.w_want == 0.0
    assert len(c.dislike_vectors) == 1


@pytest.mark.parametrize('s', [0.1, 0.3, 0.6, 0.75])
def test_card_kind_check_count_matches_share(s):
    n = 40
    checks = sum(sel.card_kind(j, s) == 'check' for j in range(n))
    assert abs(checks - n * s) <= 1


# -- review fixes: exclude-only, negative clamp, duplicate exposed, dislike norm ----
def test_exclude_only_penalty_affects_match():
    like = e(0)
    emb = {'start': e(9), 'P': vec((0, 1), (1, 1)), 'Q': vec((0, 1), (2, 1))}
    c = ctx(pool_scores={'P': -2.0, 'Q': 0.0}, w_want=0.0, w_excl=2.0, n_likes=1,
            like_vectors=likes(like, 1), current_round=2)
    # P and Q are equally close to the like; the penalty must push P down.
    assert sel.select_next(['P', 'Q'], ['start'], emb, ['start'], c) == ('Q', 'match')


def test_exclude_only_check_prefers_unpenalised():
    emb = {'start': e(0), 'near_ok': vec((0, 1), (1, 1)), 'far_bad': e(5)}
    c = ctx(pool_scores={'near_ok': 0.0, 'far_bad': -2.0}, w_want=0.0, w_excl=2.0,
            check_share=1.0)
    assert sel.select_next(['near_ok', 'far_bad'], ['start'], emb, ['start'], c) == ('near_ok', 'check')


def test_negative_tag_scores_not_clamped_to_neutral():
    # want hit (+3) minus bigger exclude hit (-5) = -2 must rank below neutral 0.
    like = e(0)
    emb = {'start': e(9), 'N': vec((0, 1), (1, 1)), 'Z': vec((0, 1), (2, 1))}
    c = ctx(pool_scores={'N': -2.0, 'Z': 0.0}, w_want=3.0, w_excl=5.0, n_likes=1,
            like_vectors=likes(like, 1), current_round=2)
    assert sel.select_next(['N', 'Z'], ['start'], emb, ['start'], c)[0] == 'Z'


def test_check_band_when_all_penalised_keeps_least_penalised():
    emb = {'start': e(0), 'a': e(5), 'b': e(6), 'c': e(7)}
    c = ctx(pool_scores={'a': -3.0, 'b': -1.0, 'c': -1.0}, w_want=3.0, check_share=1.0)
    bid, _ = sel.select_next(['a', 'b', 'c'], ['start'], emb, ['start'], c)
    assert bid in ('b', 'c')


def test_duplicate_exposed_ids_do_not_shift_card_kind():
    # s=.5, one start card; exposed has start + 'x' twice -> j = 1 -> check.
    emb = {'start': e(0), 'x': e(1), 'p': e(2), 'q': e(3)}
    c = ctx(pool_scores={}, w_want=0.0, n_likes=1, check_share=0.5,
            like_vectors=likes(e(0), 1), current_round=2)
    _, kind = sel.select_next(['p', 'q'], ['start', 'x'], emb, ['start'], c)
    assert kind == 'check'
    _, kind_dup = sel.select_next(['p', 'q'], ['start', 'x', 'x'], emb, ['start'], c)
    assert kind_dup == 'check'   # without de-dup j would be 2 -> match


def test_build_ctx_normalises_dislikes_and_w_excl():
    tags = [make_tag('country', 'Japan'), make_tag('material', 'brick', polarity='exclude')]
    c = sel.build_ctx({}, tags, [], [e(1) * 5.0], [], None, 1)
    assert c.w_want == 3.0 and c.w_excl == 2.0
    assert abs(np.linalg.norm(c.dislike_vectors[0]) - 1.0) < 1e-9


def test_negative_dislike_similarity_is_not_a_bonus():
    like = e(0)
    emb = {'start': e(9), 'C1': vec((0, 1), (1, 1)), 'C2': vec((0, 1), (2, 1))}
    # dislike is opposite to C2 only -> without the floor C2 would gain a bonus.
    c = ctx(pool_scores={'C1': 3.0, 'C2': 3.0}, w_want=3.0, n_likes=1,
            like_vectors=likes(like, 1), current_round=2,
            dislike_vectors=[vec((2, -1.0), (5, 0.01))])
    assert sel.select_next(['C1', 'C2'], ['start'], emb, ['start'], c)[0] == 'C1'
