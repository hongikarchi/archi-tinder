"""
session_pool.py -- Candidate pool + stored tags for taste_v2 sessions.

Spec: docs/plans/2026-10-11-taste-start-redesign.md §5-1, §6.

Storage (no DB migration):
  session.original_filters = {'selector': 'taste_v2', 'taste_tags': [...],
                              'image_focus'?: ..., 'off_tag'?: True}
  project.filters['taste_tags'] = [...]
Every stored tag is re-read through tag_io.rebuild_tag (never trusted).

Mock-patch discipline: `engine` and `matching` are imported as MODULES.
"""
import logging

import numpy as np
from django.conf import settings

from .. import engine
from . import matching
from .tag_io import rebuild_tag

logger = logging.getLogger('apps.recommendation')

SELECTOR_KEY = 'selector'
SELECTOR_V2 = 'taste_v2'


def _rc():
    return settings.RECOMMENDATION


def is_v2(session):
    """True when the session was started by the taste-start flow."""
    filters = getattr(session, 'original_filters', None)
    return isinstance(filters, dict) and filters.get(SELECTOR_KEY) == SELECTOR_V2


def tags_from_dicts(items):
    """Rebuild tags from stored dicts, silently skipping invalid ones."""
    tags = []
    for item in items if isinstance(items, list) else []:
        try:
            tags.append(rebuild_tag(item))
        except (ValueError, TypeError, KeyError):
            continue
    return tags


def stored_tags(obj):
    """Tags stored on an AnalysisSession (original_filters) or a Project (filters)."""
    if hasattr(obj, 'original_filters'):
        container = obj.original_filters
    else:
        container = getattr(obj, 'filters', None)
    if not isinstance(container, dict):
        return []
    return tags_from_dicts(container.get('taste_tags'))


def _unique(ids):
    seen, out = set(), []
    for i in ids:
        if i not in seen:
            seen.add(i)
            out.append(i)
    return out


def _diverse_ids(exclude_ids, limit):
    """Random-pool helper (same one create_pool_with_relaxation tier 3 uses),
    minus excluded ids, in sorted (deterministic) order."""
    excl = set(exclude_ids)
    raw = engine._random_pool(limit + len(excl))
    return sorted(i for i in raw if i not in excl)[:limit]


def _scores_for(tags, ids):
    """Tag scores for `ids` (exclude penalties included); 0.0 when unscored."""
    scored = matching.score_ids(tags, ids) if ids else {}
    return {i: float(scored.get(i, 0.0)) for i in ids}


def build_pool(tags, start_ids, exclude_ids):
    """(pool_ids, pool_scores) for a new v2 session. Start ids come first."""
    target = int(_rc()['bounded_pool_target'])
    start_ids = list(start_ids or [])
    excl = _unique(start_ids + list(exclude_ids or []))

    ranked = matching.ranked_pool(tags, limit=target, exclude_ids=excl)
    if ranked:
        rest = [r['canonical_bld_id'] for r in ranked]
        scores = {r['canonical_bld_id']: float(r['score']) for r in ranked}
    else:
        # No want tags (or nothing matched): diverse pool, exclude penalties still apply.
        rest = _diverse_ids(excl, target)
        scores = _scores_for(tags, rest)

    scores.update(_scores_for(tags, start_ids))
    pool_ids = _unique(start_ids + rest)
    return pool_ids, {i: scores.get(i, 0.0) for i in pool_ids}


def refresh_if_low(session, like_vectors):
    """Top up session.pool_ids when unexposed candidates fall below the threshold.

    Mutates session.pool_ids / pool_scores / current_pool_tier / original_filters
    (caller saves those fields). Returns True when the pool grew.
    """
    rc = _rc()
    pool_ids = list(session.pool_ids or [])
    exposed = set(session.exposed_ids or [])
    remaining = [p for p in pool_ids if p not in exposed]
    if len(remaining) >= int(rc['taste_v2_pool_refresh_threshold']):
        return False

    target = int(rc['bounded_pool_target'])
    tags = stored_tags(session)
    used = _unique(pool_ids + list(session.exposed_ids or []))
    used_set = set(used)

    # (a) next page of buildings matching >= 1 want tag
    page = matching.ranked_pool(tags, limit=target, exclude_ids=used)
    new_ids, new_scores = [], {}
    for r in page:
        bid = r['canonical_bld_id']
        if bid in used_set or bid in new_scores:
            continue
        new_ids.append(bid)
        new_scores[bid] = float(r['score'])

    off_tag = False
    if not new_ids:
        # (b) every tag-matching building is used up -> continue off-tag (§5-1, Q9).
        off_tag = True
        cand = []
        centroid = None
        if like_vectors:
            try:
                _, centroid = engine.compute_taste_centroids(
                    like_vectors, session.current_round,
                    multimodal_floor=session.multimodal_floor)
            except Exception:   # noqa: BLE001 -- fall back to the diverse pool
                logger.exception('taste_v2 off-tag centroid failed')
        if centroid is not None and np.all(np.isfinite(np.asarray(centroid, dtype=float))):
            cards = engine.taste_ranked_page(centroid, used, target, 0)
            cand = [c['canonical_bld_id'] for c in cards if c and c.get('canonical_bld_id')]
        if not cand:
            cand = _diverse_ids(used, target)
        for bid in cand:
            if bid not in used_set and bid not in new_scores:
                new_ids.append(bid)
                new_scores[bid] = 0.0
        new_ids = new_ids[:target]
        if new_ids:
            new_scores = _scores_for(tags, new_ids)

    if not new_ids:
        return False

    merged_scores = dict(session.pool_scores or {})
    merged_scores.update({i: new_scores[i] for i in new_ids})
    session.pool_ids = pool_ids + new_ids
    session.pool_scores = merged_scores
    session.current_pool_tier = int(session.current_pool_tier or 1) + 1
    if off_tag:
        filters = dict(session.original_filters or {})
        filters['off_tag'] = True
        session.original_filters = filters
    return True


def build_session_ctx(session, like_vectors):
    """SelectorCtx for a v2 session (reads recent swipes + dislike embeddings)."""
    from ..services.swipe_service import _recent_actions   # lazy: avoids an import cycle
    from . import session_selector

    rc = _rc()
    window = int(rc['taste_v2_dislike_window'])
    project = session.project
    disliked = [d for d in (project.disliked_ids or []) if isinstance(d, str)]
    dis_ids = disliked[-window:] if window > 0 else []
    emb = engine.get_pool_embeddings(dis_ids) if dis_ids else {}
    dis_embs = [emb[d] for d in dis_ids if d in emb]
    recent = _recent_actions(session, max(
        int(rc.get('taste_v2_skip_streak_hard', 5)),
        int(rc.get('taste_v2_consistency_window', 4)), 5))
    return session_selector.build_ctx(
        dict(session.pool_scores or {}), stored_tags(session), like_vectors,
        dis_embs, recent, session.multimodal_floor, session.current_round)
