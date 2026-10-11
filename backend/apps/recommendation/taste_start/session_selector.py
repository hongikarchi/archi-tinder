"""
session_selector.py -- Pure-numpy next-card selector for the taste_v2 swipe flow.

NO database access. Spec: docs/decisions/2026-10-11-taste-start-redesign.md §5-3.
Settings (`settings.RECOMMENDATION`) are read at call time so tests can override.

Cards after the start cards alternate between two kinds by a stateless rule
(`card_kind`):
  match  highest  w_tag*tag_norm + w_like*relevance - dislike_pen*dislike - lambda*redundancy
  check  farthest-from-everything-seen inside the tag-score band
"""
import math
from dataclasses import dataclass, field

import numpy as np
from django.conf import settings

from .. import engine
from . import matching

_EPS = 1e-9


def _rc():
    return settings.RECOMMENDATION


@dataclass
class SelectorCtx:
    pool_scores: dict = field(default_factory=dict)   # id -> tag score
    w_want: float = 0.0                               # sum of want-tag weights
    w_excl: float = 0.0                               # sum of exclude-tag weights x penalty factor
    n_likes: int = 0
    check_share: float = 1.0
    dislike_vectors: list = field(default_factory=list)   # np arrays, most recent last
    multimodal_floor: object = None
    like_vectors: list = field(default_factory=list)      # [{'embedding', 'round', ...}]
    current_round: int = 0


# -- check share ---------------------------------------------------------------
def _mean_pairwise_cos(embeddings):
    arr = np.stack([np.asarray(e, dtype=float) for e in embeddings])
    norms = np.linalg.norm(arr, axis=1, keepdims=True)
    arr = arr / np.where(norms == 0, 1.0, norms)
    sim = arr @ arr.T
    n = len(arr)
    return float((sim.sum() - np.trace(sim)) / (n * (n - 1)))


def check_share(n_likes, like_embeddings, recent_actions):
    """Share of check cards (0..1) from likes and the trailing skip streak (§5-3)."""
    rc = _rc()
    if n_likes <= 0:
        s = 1.0
    elif n_likes == 1:
        s = float(rc['taste_v2_check_share_one_like'])
    else:
        window = int(rc['taste_v2_consistency_window'])
        recent = list(like_embeddings)[-window:]
        if (len(recent) >= 2 and _mean_pairwise_cos(recent)
                >= float(rc['taste_v2_consistent_min_cos'])):
            s = float(rc['taste_v2_check_share_consistent'])
        else:
            s = float(rc['taste_v2_check_share_inconsistent'])

    streak = 0
    for action in reversed(list(recent_actions or [])):
        if action != 'dislike':
            break
        streak += 1
    if streak >= int(rc['taste_v2_skip_streak_hard']):
        s = 1.0
    elif streak >= int(rc['taste_v2_skip_streak']):
        s = max(s, 0.5)
    return s


def card_kind(j, s):
    """'check' or 'match' for the j-th (0-based) card after the start cards.

    CHECK iff floor((j+1)*s) - floor(j*s) >= 1  (eps guards float error), so
    s=1 -> all check, s=.5 -> M C M C ..., s=.25 -> M M M C ...
    """
    if s >= 1.0:
        return 'check'
    if s <= 0.0:
        return 'match'
    return 'check' if (math.floor((j + 1) * s + _EPS) - math.floor(j * s + _EPS)) >= 1 else 'match'


# -- context -------------------------------------------------------------------
def build_ctx(pool_scores, tags, like_vectors, dislike_embeddings, recent_actions,
              multimodal_floor, current_round):
    """Build a SelectorCtx from session-like inputs (no DB)."""
    weights = _rc()['taste_tag_weights']
    w_want = float(sum(float(weights.get(t.axis, 1))
                       for t in matching.scored_tags(tags or []) if t.polarity != 'exclude'))
    w_excl = float(sum(float(weights.get(t.axis, 1))
                       for t in matching.scored_tags(tags or []) if t.polarity == 'exclude'))
    w_excl *= float(_rc().get('taste_exclude_penalty_factor', 1.0))
    dislikes = [engine._finite_unit_vector(d) for d in (dislike_embeddings or [])]
    dislikes = [d for d in dislikes if d is not None]
    like_vectors = list(like_vectors or [])
    like_embs = [lv['embedding'] for lv in like_vectors]
    n_likes = len(like_vectors)
    return SelectorCtx(
        pool_scores=dict(pool_scores or {}),
        w_want=w_want,
        w_excl=w_excl,
        n_likes=n_likes,
        check_share=check_share(n_likes, like_embs, recent_actions),
        dislike_vectors=dislikes,
        multimodal_floor=multimodal_floor,
        like_vectors=like_vectors,
        current_round=current_round,
    )


# -- selection -----------------------------------------------------------------
def _tag_norm(candidates, ctx):
    """Per-candidate tag term. Want tags: score/w_want in [-1, 1]. Exclude-only:
    score/w_excl in [-1, 0] (pure penalty). No tags: zeros."""
    raw = np.array([float(ctx.pool_scores.get(c, 0.0)) for c in candidates])
    if ctx.w_want > 0:
        return np.clip(raw / ctx.w_want, -1.0, 1.0)
    if ctx.w_excl > 0:
        return np.clip(raw / ctx.w_excl, -1.0, 0.0)
    return np.zeros(len(candidates))


def _max_cos(C, others, floor=None):
    """(N,) max cosine of each row of C to the rows of `others`; zeros if none.
    `floor` clamps the result from below (e.g. 0 so a negative never becomes a bonus)."""
    if not len(others):
        return np.zeros(C.shape[0])
    M = np.stack([np.asarray(o, dtype=float) for o in others])
    out = np.nan_to_num(C @ M.T).max(axis=1)
    return out if floor is None else np.maximum(out, floor)


def _relevance(C, ctx):
    rc = _rc()
    centroids, _ = engine.compute_taste_centroids(
        ctx.like_vectors, ctx.current_round, multimodal_floor=ctx.multimodal_floor)
    sim = np.nan_to_num(C @ np.stack(centroids).T)   # (N, K)
    if rc.get('soft_relevance_enabled', False) and len(centroids) > 1:
        shifted = sim - sim.max(axis=1, keepdims=True)
        w = np.exp(shifted)
        w = w / w.sum(axis=1, keepdims=True)
        return (sim * w).sum(axis=1)
    return sim.max(axis=1)


def _match_pick(candidates, emb, exposed_ids, ctx):
    rc = _rc()
    C = np.stack([np.asarray(emb[c], dtype=float) for c in candidates])
    tag_norm = _tag_norm(candidates, ctx)

    alpha = min(1.0, ctx.n_likes / max(1, int(rc['taste_v2_like_saturation'])))
    if ctx.w_want <= 0:
        w_tag = 0.0
    else:
        w_tag = 1.0 + (float(rc['taste_v2_tag_weight_end']) - 1.0) * alpha
    w_like = 1.0 - w_tag

    rel = _relevance(C, ctx)
    window = int(rc['taste_v2_dislike_window'])
    dis = _max_cos(C, ctx.dislike_vectors[-window:] if window > 0 else [], floor=0.0)
    exposed_valid = [emb[e] for e in exposed_ids if e in emb]
    red = _max_cos(C, exposed_valid)

    lam = float(rc.get('mmr_penalty', 0.3))
    if rc.get('mmr_lambda_ramp_enabled', False):
        n_ref = max(1, rc.get('mmr_lambda_ramp_n_ref', 10))
        lam *= min(1.0, len(exposed_ids) / n_ref)

    if ctx.w_want > 0:
        tag_term = w_tag * tag_norm
    else:
        tag_term = tag_norm   # exclude-only: penalty at weight 1.0 (zeros if no tags)
    score = (tag_term + w_like * rel
             - float(rc['taste_v2_dislike_penalty']) * dis - lam * red)
    return candidates[int(np.argmax(score))]


def _check_pick(candidates, emb, exposed_ids, ctx):
    rc = _rc()
    band = candidates
    if ctx.w_want > 0 or ctx.w_excl > 0:
        tag_norm = _tag_norm(candidates, ctx)
        best = float(tag_norm.max())
        # best > 0: keep >= ratio x best; best <= 0: keep the least-penalised.
        floor = float(rc['taste_v2_check_min_tag_ratio']) * best if best > 0 else best
        keep = [c for c, t in zip(candidates, tag_norm) if t >= floor - _EPS]
        band = keep or candidates
    if not any(e in emb for e in exposed_ids):
        return band[0]   # nothing to be far from: deterministic first (no random)
    return engine.farthest_point_from_pool(band, exposed_ids, emb)


def select_next(pool_ids, exposed_ids, emb, initial_batch, ctx):
    """Pick the next card: returns (building_id | None, kind in start/match/check)."""
    exposed_set = set(exposed_ids)
    for bid in initial_batch:
        if bid not in exposed_set:
            return bid, 'start'

    j = len(exposed_set - set(initial_batch))
    kind = card_kind(j, ctx.check_share)
    if kind == 'match' and ctx.n_likes == 0:
        kind = 'check'

    candidates = [c for c in pool_ids if c not in exposed_set and c in emb]
    if not candidates:
        return None, kind
    if kind == 'match':
        return _match_pick(candidates, emb, exposed_ids, ctx), kind
    return _check_pick(candidates, emb, exposed_ids, ctx), kind
