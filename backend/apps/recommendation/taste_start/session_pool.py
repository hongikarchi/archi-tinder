"""
session_pool.py -- Candidate pool + stored tags for taste_v2 sessions.

Spec: docs/decisions/2026-10-11-taste-start-redesign.md §5-1, §6.

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
from django.db import transaction

from .. import engine
from . import legacy_filters, matching
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


def build_pool(tags, start_ids, exclude_ids, head_ids=None):
    """(pool_ids, pool_scores) for a new v2 session. Start ids come first,
    then `head_ids` (e.g. client seed ids, kept in the pool), then the ranked rest."""
    target = int(_rc()['bounded_pool_target'])
    start_ids = list(start_ids or [])
    head_ids = list(head_ids or [])
    excl = _unique(start_ids + head_ids + list(exclude_ids or []))

    ranked = matching.ranked_pool(tags, limit=target, exclude_ids=excl)
    if ranked:
        rest = [r['canonical_bld_id'] for r in ranked]
        scores = {r['canonical_bld_id']: float(r['score']) for r in ranked}
    else:
        # No want tags (or nothing matched): diverse pool, exclude penalties still apply.
        rest = _diverse_ids(excl, target)
        scores = _scores_for(tags, rest)

    scores.update(_scores_for(tags, _unique(start_ids + head_ids)))
    pool_ids = _unique(start_ids + head_ids + rest)
    return pool_ids, {i: scores.get(i, 0.0) for i in pool_ids}


UPGRADE_FIELDS = ['original_filters', 'pool_scores', 'initial_batch']


def ensure_v2(session):
    """Lazily upgrade a pre-v2 (marker-less) session in memory. Returns True if changed.

    Tags come from the board's stored v2 tags if present, else from the session's
    old filters. pool_scores are recomputed (legacy scores use another scale),
    initial_batch is cleared (unexposed legacy start cards are not re-served) and
    the selector marker + round_offset=0 are set. The CALLER saves UPGRADE_FIELDS
    inside the transaction / row lock it already holds (see ensure_v2_locked).
    """
    if is_v2(session):
        return False
    old = dict(session.original_filters) if isinstance(session.original_filters, dict) else {}
    project = getattr(session, 'project', None)
    tags = stored_tags(project) if project is not None else []
    if not tags:
        tags = legacy_filters.filters_to_tags(old)
    session.pool_scores = _scores_for(tags, list(session.pool_ids or []))
    session.original_filters = {
        **old, SELECTOR_KEY: SELECTOR_V2,
        'taste_tags': [t.to_dict() for t in tags], 'round_offset': 0,
    }
    session.initial_batch = []
    return True


def ensure_v2_locked(session):
    """ensure_v2 for entry points without a row lock: re-reads the session under
    select_for_update, upgrades + saves, returns the (fresh) session."""
    if is_v2(session):
        return session
    from ..models import AnalysisSession   # lazy: keeps this module import-light
    with transaction.atomic():
        locked = (AnalysisSession.objects.select_for_update()
                  .select_related('project').get(pk=session.pk))
        if ensure_v2(locked):
            locked.save(update_fields=UPGRADE_FIELDS)
    return locked


def round_offset(session):
    """Swipes already made before this session started (promote seeds)."""
    filters = getattr(session, 'original_filters', None)
    try:
        return int((filters or {}).get('round_offset', 0) or 0)
    except (TypeError, ValueError, AttributeError):
        return 0


def swipes_in_session(session):
    return max(0, int(session.current_round or 0) - round_offset(session))


def refresh_if_low(session, like_vectors, *, force=False):
    """Top up session.pool_ids when unexposed candidates fall below the threshold.

    Mutates session.pool_ids / pool_scores / current_pool_tier / original_filters
    (caller saves those fields). Returns True when the pool grew.
    `force=True` skips the threshold check (used when the selector found nothing
    selectable although the pool still lists unexposed ids, e.g. no embeddings).
    """
    rc = _rc()
    pool_ids = list(session.pool_ids or [])
    exposed = set(session.exposed_ids or [])
    remaining = [p for p in pool_ids if p not in exposed]
    if not force and len(remaining) >= int(rc['taste_v2_pool_refresh_threshold']):
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


def recent_actions_window():
    """How many trailing swipe actions the selector context needs."""
    rc = _rc()
    return max(int(rc.get('taste_v2_skip_streak_hard', 5)),
               int(rc.get('taste_v2_consistency_window', 4)), 5)


def build_session_ctx(session, like_vectors, *, project=None, recent_actions=None):
    """SelectorCtx for a v2 session (reads dislike embeddings).

    Pass `project` / `recent_actions` (oldest first, >= recent_actions_window()
    long) to avoid extra queries; otherwise they are fetched here.
    """
    from . import session_selector

    rc = _rc()
    window = int(rc['taste_v2_dislike_window'])
    if project is None:
        project = session.project
    disliked = [d for d in (project.disliked_ids or []) if isinstance(d, str)]
    dis_ids = disliked[-window:] if window > 0 else []
    emb = engine.get_pool_embeddings(dis_ids) if dis_ids else {}
    dis_embs = [emb[d] for d in dis_ids if d in emb]
    if recent_actions is None:
        from ..services.swipe_service import _recent_actions   # lazy: avoids an import cycle
        recent_actions = _recent_actions(session, recent_actions_window())
    return session_selector.build_ctx(
        dict(session.pool_scores or {}), stored_tags(session), like_vectors,
        dis_embs, recent_actions, session.multimodal_floor, session.current_round)
