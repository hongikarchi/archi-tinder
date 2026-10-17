"""swipe_service.py — orchestration extracted from views/swipe.py.

Pure move: buffer helpers and view-body orchestration relocated verbatim
from SwipeView and ProjectBookmarkView.  Zero behaviour changes.

Mock-patch discipline (CRITICAL):
- engine, event_log imported AS MODULES so that test patches via
  ``apps.recommendation.views.engine.<fn>`` resolve at call time through
  the shared module object.
- NEVER ``from ..engine import some_fn`` — that copies the name and
  breaks the patch path.
- threading.Thread is NOT imported here; it stays in views/swipe.py so
  ``apps.recommendation.views.swipe.threading.Thread`` remains patchable.
- _emit_telemetry_thread is NOT moved here; it stays in views/swipe.py
  so ``apps.recommendation.views.swipe._emit_telemetry_thread`` remains
  patchable.
"""
import hashlib
import logging

import numpy as np
from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import IntegrityError, connections, transaction
from django.utils import timezone
from rest_framework import status
from rest_framework.response import Response

from .. import engine  # noqa: import MODULE — patch via apps.recommendation.views.engine.*
from .. import event_log  # noqa: import MODULE
from ..models import Project, AnalysisSession, SwipeEvent
from ..caches import (
    evict_projects_list,
    evict_discovery_feed,
    evict_user_profile_detail,
    evict_project_detail,
    evict_swipe_caches_after_commit,
)
from ..views._shared import _progress, _liked_id_only
from .hydration import hydrate_like_vectors, cache_embedding
from ..taste_start import session_pool, session_selector, swipe_rules

logger = logging.getLogger('apps.recommendation')
RC = settings.RECOMMENDATION

# ── Action-card sentinel (TASTE-FLOW action card) ─────────────────────────────
_ACTION_CARD_ID = '__action_card__'


def _build_action_card():
    """Return the synthetic action-card next_image payload.

    The frontend normalises next_image via api/images.js.  It already
    recognises card_type='action' / canonical_bld_id='__action_card__'.
    This sentinel is never a real building and must never reach the
    buildings DB, like_vectors, or exposed_ids.
    """
    return {
        'canonical_bld_id': _ACTION_CARD_ID,
        'card_type': 'action',
        'action_card_message': '취향이 충분히 모였어요!',
        'action_card_subtitle': (
            '오른쪽으로 스와이프하면 취향 리포트를 볼 수 있어요 '
            '· 왼쪽으로 넘기면 계속 탐색해요'
        ),
    }


def _merge_buffer_into_exposed(exposed_ids, client_buffer_ids):
    """
    Merge client_buffer_ids into exposed_ids, preserving order and deduplicating.
    Returns a new list (does not mutate input).
    """
    if not client_buffer_ids:
        return list(exposed_ids)
    exposed_set = set(exposed_ids)
    merged = list(exposed_ids)
    for bid in client_buffer_ids:
        if bid and bid != '__action_card__' and bid not in exposed_set:
            merged.append(bid)
            exposed_set.add(bid)
    return merged


def _building_id_is_trusted(session, canonical_bld_id):
    """True when canonical_bld_id is provably a publishable building without a DB check.

    pool_ids are produced by is_publishable-gated queries, so a pool member needs
    no per-swipe existence SELECT. Two client-controlled leaks make the naive
    "pool_ids or exposed_ids" rule unsafe, so they are excluded:
      - original_seed_ids: client `seed_ids` are injected into pool_ids unvalidated
        (session create only checks type/length).
      - exposed_ids: client_buffer_ids are merged into it unvalidated.
    Every server-selected exposed id is a pool member anyway, so exposed_ids adds
    nothing legitimate. Trade-off: a building flipped non-publishable after pool
    creation is still accepted for that session.
    """
    if canonical_bld_id in (session.original_seed_ids or []):
        return False
    return canonical_bld_id in (session.pool_ids or [])


def _recent_actions(session, window):
    return list(
        reversed(
            list(
                session.swipes.order_by('-created_at')
                .values_list('action', flat=True)[:window]
            )
        )
    )


_V2_FORCED_REFRESH_ATTEMPTS = 3


def _v2_select_card(session, hydrated_lv, project, recent_actions):
    """taste_v2 card pick (replaces the phase-based legacy selection).

    Builds the SelectorCtx from the already-fetched `recent_actions` (no extra
    query), picks via session_selector.select_next, and if nothing is selectable
    while the pool may still hold unusable ids (e.g. no embeddings) force-tops-up
    the pool and retries (up to _V2_FORCED_REFRESH_ATTEMPTS times, while each
    top-up still grows the pool).

    Returns (next_bid | None, kind, ctx, pool_embeddings, embedding_stats,
    pool_refreshed). The ctx is built BEFORE the pool-embedding fetch so the
    dislike-embedding lookup does not clobber the swipe-selection cache stats.
    """
    ctx = session_pool.build_session_ctx(
        session, hydrated_lv, project=project, recent_actions=recent_actions)
    pool_embeddings = engine.get_pool_embeddings(session.pool_ids)
    stats = engine.get_last_embedding_call_stats() or {}
    initial_batch = list(session.initial_batch or [])
    bid, kind = session_selector.select_next(
        session.pool_ids, session.exposed_ids, pool_embeddings, initial_batch, ctx)
    refreshed = False
    for _ in range(_V2_FORCED_REFRESH_ATTEMPTS):
        if bid is not None or not session_pool.refresh_if_low(
                session, hydrated_lv, force=True):
            break
        refreshed = True
        ctx.pool_scores = dict(session.pool_scores or {})
        pool_embeddings = engine.get_pool_embeddings(session.pool_ids)
        bid, kind = session_selector.select_next(
            session.pool_ids, session.exposed_ids, pool_embeddings, initial_batch, ctx)
    return bid, kind, ctx, pool_embeddings, stats, refreshed


# ── View body orchestration ───────────────────────────────────────────────────

def handle_bookmark(request, profile, project_id):
    """Orchestrate ProjectBookmarkView.post body.

    Verbatim from the original view: validate → atomic toggle → cache eviction →
    session provenance lookup → event emission → response.
    """
    # Existence check outside the lock — cheap 404 guard before acquiring row lock.
    if not Project.objects.filter(project_id=project_id, user=profile).exists():
        return Response({'detail': 'project not found'}, status=status.HTTP_404_NOT_FOUND)

    card_id = request.data.get('card_id')
    action = request.data.get('action')
    rank = request.data.get('rank')
    session_id = request.data.get('session_id')

    # --- Validate inputs ---
    if not card_id or not isinstance(card_id, str) or len(card_id) > 20:
        return Response({'detail': 'invalid card_id'}, status=status.HTTP_400_BAD_REQUEST)
    if action not in ('save', 'unsave'):
        return Response(
            {'detail': "action must be 'save' or 'unsave'"},
            status=status.HTTP_400_BAD_REQUEST,
        )
    if not isinstance(rank, int) or rank < 1 or rank > 100:
        return Response(
            {'detail': 'rank must be integer in [1, 100]'},
            status=status.HTTP_400_BAD_REQUEST,
        )

    # --- Validate building exists and is publishable (save path only) ---
    # unsave must always succeed so a later-unpublished building can be removed
    # from saved_ids (gating it would trap the id forever).
    if action == 'save':
        with connections['buildings'].cursor() as cur:
            cur.execute(
                'SELECT 1 FROM canonical_v2_buildings'
                ' WHERE canonical_bld_id = %s AND is_publishable = true',
                [card_id],
            )
            if not cur.fetchone():
                return Response({'detail': 'building not found'}, status=status.HTTP_404_NOT_FOUND)

    # --- Toggle saved_ids (atomic read-modify-write to prevent lost updates) ---
    with transaction.atomic():
        try:
            project = Project.objects.select_for_update().get(
                project_id=project_id, user=profile,
            )
        except Project.DoesNotExist:
            return Response({'detail': 'project not found'}, status=status.HTTP_404_NOT_FOUND)

        existing = list(project.saved_ids or [])
        existing_by_id = {
            e['id']: e
            for e in existing
            if isinstance(e, dict) and 'id' in e
        }

        if action == 'save':
            if card_id not in existing_by_id:
                existing.append({'id': card_id, 'saved_at': timezone.now().isoformat()})
        else:  # unsave
            existing = [
                e for e in existing
                if not (isinstance(e, dict) and e.get('id') == card_id)
            ]

        project.saved_ids = existing
        project.save(update_fields=['saved_ids', 'updated_at'])

    evict_projects_list(profile.id)
    evict_discovery_feed(profile.id)
    # Profile detail boards payload uses saved_ids for cover/thumbnails;
    # bookmark mutation must invalidate. Missed in initial PR — code-review catch.
    evict_user_profile_detail(profile.user_id)
    evict_project_detail(str(project_id))

    # --- Resolve optional session for event association ---
    session = None
    if session_id:
        try:
            session = AnalysisSession.objects.filter(
                session_id=session_id, user=profile,
            ).first()
        except (ValueError, ValidationError, Exception):
            session = None

    # --- Compute rank_zone per Spec v1.2 §6 implementation requirement #4 ---
    rank_zone = 'primary' if rank <= 10 else 'secondary'

    # --- rank_corpus: deferred (Finding #14b) ---
    # compute_corpus_rank() does a full O(N) pgvector scan (~39k rows) synchronously,
    # blocking the bookmark response. rank_corpus is telemetry-only (stored in
    # SessionEvent.payload); it is not returned to the client and has no correctness
    # impact on bookmarking. Setting to None here; move to a background task when
    # Celery/task-queue is available.
    # TODO(Finding #14b): compute_corpus_rank deferred — add background task here.
    rank_corpus = None

    # --- Provenance booleans per Spec v1.2 / IMP-10 sub-task A (Topic 02/04 attribution) ---
    # Read from session.cosine_top10_ids / gemini_top10_ids / dpp_top10_ids set by
    # SessionResultView at result-page load time.
    # Legacy sessions (created before migration 0013) have None → all False (same as before).
    # New sessions have accurate provenance once SessionResultView has been called.
    if session is not None:
        provenance = {
            'in_cosine_top10': card_id in (session.cosine_top10_ids or []),
            'in_gemini_top10': card_id in (session.gemini_top10_ids or []),
            'in_dpp_top10': card_id in (session.dpp_top10_ids or []),
        }
    else:
        provenance = {
            'in_cosine_top10': False,
            'in_gemini_top10': False,
            'in_dpp_top10': False,
        }

    # --- Emit bookmark SessionEvent ---
    event_log.emit_event(
        'bookmark',
        session=session,
        user=profile,
        card_id=card_id,
        action=action,
        rank=rank,
        rank_zone=rank_zone,
        rank_corpus=rank_corpus,
        provenance=provenance,
    )

    saved_id_list = [e['id'] for e in existing if isinstance(e, dict) and 'id' in e]
    return Response({
        'saved_ids': saved_id_list,
        'count': len(saved_id_list),
    })


def handle_swipe_extend(request, profile, session, session_id, client_buffer_ids):
    """Handle the S3 extend-session short-circuit path of SwipeView.post.

    Returns a Response directly.  Verbatim from the original view body.
    """
    with transaction.atomic():
        session = AnalysisSession.objects.select_for_update().get(
            session_id=session_id, user=profile
        )
        if session.phase not in ('converged', 'completed'):
            residual_noop = len([
                pid for pid in session.pool_ids
                if pid not in set(session.exposed_ids)
            ]) if session.pool_ids else 0
            can_continue_noop = (residual_noop >= 1)
            return Response({
                'accepted': True,
                'session_status': session.status,
                'progress': _progress(session),
                'next_image': None,
                'prefetch_image': None,
                'prefetch_image_2': None,
                'is_analysis_completed': session.phase in ('converged', 'completed'),
                'can_continue': can_continue_noop and session.phase in ('converged', 'completed'),
                'confidence': None,
            })

        _upgraded = session_pool.ensure_v2(session)
        session.phase = 'analyzing'
        session.convergence_history = []
        # Seed previous_pref_vector from the current centroid so delta_v tracking
        # resumes on the first post-extend swipe. Clearing to [] (old behaviour)
        # made compute_confidence always return None in the extended session.
        if session.like_vectors:
            _hydrated_lv_extend = hydrate_like_vectors(session)
            _, global_centroid = engine.compute_taste_centroids(
                _hydrated_lv_extend, session.current_round,
                multimodal_floor=session.multimodal_floor,
            )
            session.previous_pref_vector = global_centroid.tolist()
        else:
            _hydrated_lv_extend = []
            session.previous_pref_vector = []

        if client_buffer_ids:
            session.exposed_ids = _merge_buffer_into_exposed(session.exposed_ids, client_buffer_ids)

        _extend_fields = [
            'phase', 'convergence_history', 'previous_pref_vector',
            'exposed_ids', 'pool_ids', 'pool_scores', 'current_pool_tier',
            'original_filters',
        ]
        if _upgraded:
            _extend_fields.append('initial_batch')
        # Pool top-up + card pick via the v2 selector.
        session_pool.refresh_if_low(session, _hydrated_lv_extend)
        next_card_id = _v2_select_card(
            session, _hydrated_lv_extend, session.project,
            _recent_actions(session, session_pool.recent_actions_window()),
        )[0]
        next_card = engine.get_building_card(next_card_id) if next_card_id else None
        if next_card:
            session.exposed_ids = session.exposed_ids + [next_card['canonical_bld_id']]

        session.save(update_fields=_extend_fields)

    residual_after = len([
        pid for pid in session.pool_ids if pid not in set(session.exposed_ids)
    ]) if session.pool_ids else 0
    return Response({
        'accepted': True,
        'session_status': session.status,
        'progress': _progress(session),
        'next_image': next_card,
        'prefetch_image': None,
        'prefetch_image_2': None,
        'is_analysis_completed': next_card is None,
        'can_continue': (residual_after >= 1),
        'confidence': None,
    })


def handle_swipe_normal(
    request, profile, session, session_id,
    canonical_bld_id, action, idempotency_key, client_buffer_ids,
):
    """Handle the normal swipe path of SwipeView.post.

    Returns either a Response (on error / concurrent-duplicate path) or a
    plain dict with transaction results.  The view unpacks the dict and handles
    the post-transaction prefetch + thread spawning with local patch targets
    (``apps.recommendation.views.swipe.threading.Thread`` and
    ``apps.recommendation.views.swipe._emit_telemetry_thread``).
    """
    import time as _time
    _t_start = _time.perf_counter()
    _timing_marks = {}  # step_name -> elapsed_ms from _t_start

    def _mark(step):
        _timing_marks[step] = round((_time.perf_counter() - _t_start) * 1000, 2)

    # Validate building exists and is publishable before acquiring the row lock.
    # '__action_card__' is a synthetic sentinel — never hits the buildings DB.
    # Pool members (server-produced, publishable-gated; client seeds excluded) skip
    # the per-swipe buildings SELECT 1 — see _building_id_is_trusted.
    _is_action_card = canonical_bld_id == _ACTION_CARD_ID
    if (
        canonical_bld_id and not _is_action_card
        and not _building_id_is_trusted(session, canonical_bld_id)
    ):
        with connections['buildings'].cursor() as cur:
            cur.execute(
                'SELECT 1 FROM canonical_v2_buildings'
                ' WHERE canonical_bld_id = %s AND is_publishable = true',
                [canonical_bld_id],
            )
            if not cur.fetchone():
                return Response({'detail': 'building not found'}, status=status.HTTP_404_NOT_FOUND)

    with transaction.atomic():
        # Lock session row to prevent concurrent swipe corruption
        session = AnalysisSession.objects.select_for_update().get(
            session_id=session_id, user=profile
        )
        _mark('lock_acquired')
        # Every session runs on the taste_v2 rule: upgrade marker-less (pre-deploy)
        # sessions lazily, under this row lock.
        _v2_upgraded = session_pool.ensure_v2(session)
        # Keep Project JSON lists synchronized per existing API contract.
        # Lock order: Session -> Project (bookmark POST takes only Project).
        project = Project.objects.select_for_update().get(pk=session.project_id)

        # 1. Get embedding and update preference vector
        # Action-card swipe: no building involved — skip embedding entirely.
        embedding = None
        if not _is_action_card:
            embedding = engine.get_building_embedding(canonical_bld_id)
        _mark('embed_done')
        if embedding:
            session.preference_vector = engine.update_preference_vector(
                session.preference_vector, embedding, action
            )

        # 2. Record swipe — nested savepoint to handle concurrent duplicate races.
        # Two concurrent requests with the same idempotency_key can both pass the
        # pre-check at line ~424 before either has committed. The savepoint ensures
        # the outer atomic block stays healthy when the constraint fires on the second.
        # Action-card swipes are not real buildings — do NOT create a SwipeEvent row
        # (avoids FK/unique constraint failures and keeps taste data clean).
        if not _is_action_card:
            try:
                with transaction.atomic():  # savepoint
                    SwipeEvent.objects.create(
                        session=session, canonical_bld_id=canonical_bld_id,
                        action=action, idempotency_key=idempotency_key,
                    )
            except IntegrityError:
                # Concurrent duplicate raced past the pre-check. Bail out — the other
                # request already committed the row. Re-read session for latest state.
                logger.info('Concurrent duplicate swipe caught at create: %s', idempotency_key)
                session.refresh_from_db()
                return Response({
                    'accepted': True,
                    'session_status': session.status,
                    'progress': _progress(session),
                    'next_image': None,
                    'prefetch_image': None,
                    'prefetch_image_2': None,
                    'is_analysis_completed': session.status == 'completed',
                    'can_continue': False,
                    'confidence': None,
                    'detail': 'duplicate',
                })

        # 3. Update project liked/disliked lists and in-session like vectors.
        # Action-card swipe must never pollute liked_ids / disliked_ids / like_vectors.
        if not _is_action_card:
            if action == 'like':
                existing_ids = _liked_id_only(project.liked_ids)
                if canonical_bld_id not in existing_ids:
                    try:
                        raw_intensity = request.data.get('intensity', 1.0)
                        intensity = float(raw_intensity) if raw_intensity is not None else 1.0
                    except (TypeError, ValueError):
                        intensity = 1.0
                    intensity = max(0.0, min(2.0, intensity))
                    project.liked_ids = project.liked_ids + [
                        {'id': canonical_bld_id, 'intensity': intensity}
                    ]
                if embedding:
                    # New shape: store only {id, round} — no 384-float payload in the
                    # session row.  Populate the embedding cache immediately while we
                    # still have `embedding` in hand so same-process hydration always hits.
                    cache_embedding(canonical_bld_id, embedding)
                    session.like_vectors = session.like_vectors + [
                        {'id': canonical_bld_id, 'round': session.current_round}
                    ]
            else:
                if canonical_bld_id not in project.disliked_ids:
                    project.disliked_ids = project.disliked_ids + [canonical_bld_id]
            project.save(update_fields=['liked_ids', 'disliked_ids', 'updated_at'])
            # Taste + discovery feed + /projects/ list (counts changed) + project
            # detail: one batched delete_many, deferred to after COMMIT so the
            # cache round trips happen outside the session/project row locks.
            evict_swipe_caches_after_commit(profile.id, project.project_id)

        # 4. Increment round (action-card swipe does NOT count as a real round)
        if not _is_action_card:
            session.current_round += 1

        # 5. Convergence -- use K-Means global centroid during analyzing, pref_vector during exploring.
        # Note: Delta-V is appended on EVERY analyzing swipe (not gated by action == 'like'),
        # so `convergence_window` counts rounds, not likes. On a dislike the centroid still
        # shifts slightly due to recency-weight drift, so Delta-V is smaller but non-zero.
        # Known bias: dislike Delta-V < like Delta-V may pull the moving average down on
        # dislike-heavy sequences. Acceptable per research/spec/requirements.md Section 11
        # Tier A Topic 10 Option A; revisit with data if problematic.
        # Action-card swipe: skip convergence tracking (no taste data recorded).
        #
        # Hydrate like_vectors once here; reused by all convergence + MMR calls below.
        # Hydration is cheap when embeddings are already in Django cache (like-time set).
        _hydrated_lv = hydrate_like_vectors(session) if session.like_vectors else []
        if session.like_vectors and len(_hydrated_lv) < len(session.like_vectors):
            logger.warning(
                'Session %s: %d like_vectors stored but %d hydrated — dropped likes with missing embeddings',
                session.session_id, len(session.like_vectors), len(_hydrated_lv),
            )
        if not _is_action_card:
            if session.phase == 'analyzing' and _hydrated_lv:
                _, global_centroid = engine.compute_taste_centroids(
                    _hydrated_lv, session.current_round,
                    multimodal_floor=session.multimodal_floor,
                )
                centroid_list = global_centroid.tolist()
                if session.previous_pref_vector:
                    delta_v = engine.compute_convergence(centroid_list, session.previous_pref_vector)
                    if delta_v is not None:
                        session.convergence_history = session.convergence_history + [delta_v]
                session.previous_pref_vector = centroid_list
            elif session.phase == 'exploring':
                if session.preference_vector and session.previous_pref_vector:
                    delta_v = engine.compute_convergence(
                        session.preference_vector, session.previous_pref_vector
                    )
                    if delta_v is not None:
                        session.convergence_history = session.convergence_history + [delta_v]
                session.previous_pref_vector = list(session.preference_vector) if session.preference_vector else []

        # 5a. Merge client buffer into exposed_ids BEFORE card selection.
        # This prevents the backend from re-selecting any card the frontend
        # already has in its visible queue (fixes queue drift bugs).
        if client_buffer_ids:
            session.exposed_ids = _merge_buffer_into_exposed(session.exposed_ids, client_buffer_ids)

        # 6. Phase transitions (skip for action-card swipe — phase is already 'converged'
        # and no new taste evidence was recorded, so transitions would be spurious).
        if not _is_action_card:
            like_count = len(_hydrated_lv) if _hydrated_lv is not None else len(session.like_vectors)

            if session.phase == 'exploring' and swipe_rules.should_enter_analyzing(like_count):
                session.phase = 'analyzing'
                # Reset convergence state: the analyzing phase tracks Delta-V between K-Means
                # centroids, but `previous_pref_vector` currently holds the exploring-phase
                # preference_vector (a different physical quantity). Clearing both prevents
                # the first analyzing Delta-V from being a cross-metric centroid-vs-pref_vector
                # distance. Matches the reset pattern in the "Reset and keep going" action-card
                # path above. See research/spec/requirements.md Section 11 Tier A Topic 10.
                session.convergence_history = []
                session.previous_pref_vector = []
                logger.info('Session %s: exploring -> analyzing (likes=%d)', session.session_id, like_count)

        _convergence_window = RC.get('convergence_window', 3)
        _recent_action_window = max(_convergence_window, session_pool.recent_actions_window())
        _recent_actions_window = _recent_actions(session, _recent_action_window)
        _recent_convergence_actions = _recent_actions_window[-_convergence_window:]
        if not _is_action_card and session.phase == 'analyzing' and (
            swipe_rules.convergence_floor_met(session_pool.swipes_in_session(session))
        ) and engine.check_convergence(
            session.convergence_history,
            RC.get('convergence_threshold', 0.13),
            _convergence_window,
            _recent_convergence_actions,
            RC.get('convergence_min_recent_likes', 0),
        ):
            session.phase = 'converged'
            logger.info('Session %s: analyzing -> converged', session.session_id)

        # 6b. Pool exhaustion guard (§5.6 + §6 implementation requirement A4):
        # If remaining pool < 5 buildings, escalate to next filter relaxation tier
        # to extend the pool with new candidates before card selection.
        # refresh_pool_if_low mutates session.pool_ids/pool_scores/current_pool_tier
        # in-place when escalation fires.
        _tier_before_refresh = session.current_pool_tier
        _pool_refreshed_v2 = False
        if session.phase not in ('converged', 'completed'):
            _pool_refreshed_v2 = session_pool.refresh_if_low(session, _hydrated_lv)
        _pool_escalation_fired = session.current_pool_tier != _tier_before_refresh

        # 7. Check pool exhaustion (hard-empty fallback after refresh attempt)
        remaining = [pid for pid in session.pool_ids if pid not in set(session.exposed_ids)]
        if not remaining and session.phase not in ('converged', 'completed'):
            session.phase = 'converged'
            logger.info('Session %s: pool exhausted -> converged', session.session_id)

        # 8. Card selection (taste_v2 selector for every session)
        _selector_ctx = None
        _card_kind = '-'
        _v2_bid = None
        # Does this swipe pick a real card? (mirrors the branch chain below)
        if _is_action_card:
            _v2_wants_card = action != 'like'
        elif session.phase == 'converged':
            _v2_wants_card = bool(session.action_card_shown)
        else:
            _v2_wants_card = session.phase in ('exploring', 'analyzing')
        if _v2_wants_card:
            (_v2_bid, _card_kind, _selector_ctx, pool_embeddings,
             _embedding_stats, _v2_refreshed) = _v2_select_card(
                session, _hydrated_lv, project, _recent_actions_window)
            _pool_refreshed_v2 = _pool_refreshed_v2 or _v2_refreshed
            _pool_escalation_fired = session.current_pool_tier != _tier_before_refresh
        else:
            pool_embeddings = engine.get_pool_embeddings(session.pool_ids)
            # Capture IMP-7 cache stats right after the primary get_pool_embeddings call.
            _embedding_stats = engine.get_last_embedding_call_stats() or {}

        # ID selection only — DB fetch deferred to post-transaction batch call.
        #
        # TASTE-FLOW: When converged, do NOT force-end the session.
        # Emit the action-card sentinel so the frontend offers "결과 보러 가기"
        # without auto-navigating.  The sentinel is never added to exposed_ids or
        # fetched from the buildings DB.
        #
        # Action-card 'pass' (LEFT = keep exploring): select the next real card
        # from the pool, as if convergence hadn't happened.  If pool is empty,
        # the view sets is_analysis_completed.
        #
        # Action-card 'like' (RIGHT = go to report): the view returns
        # is_analysis_completed=True so the frontend navigates to the report.
        # We fall through to next_bid=None here; the view special-cases this.
        if _is_action_card and action == 'like':
            # User chose the report: signal completion to the view.
            next_bid = None
            _action_card_accepted = True
        elif _is_action_card and action == 'dislike':
            # LEFT swipe on the action card = keep exploring: pick the next real card.
            # action_card_shown is already True, so the prompt is never re-offered.
            next_bid = _v2_bid
            _action_card_accepted = False
        elif session.phase == 'converged':
            # TASTE-FLOW emit-once: show the action card only the FIRST time
            # convergence is reached.  Afterwards serve real cards (converged-continue).
            if not session.action_card_shown:
                next_bid = _ACTION_CARD_ID
                session.action_card_shown = True
                _action_card_accepted = False
            else:
                _action_card_accepted = False
                next_bid = _v2_bid
        elif session.phase in ('exploring', 'analyzing'):
            _action_card_accepted = False
            next_bid = _v2_bid
            if not next_bid:
                # Nothing selectable even after a forced top-up: the DB is truly spent.
                session.phase = 'converged'
                logger.info('Session %s: taste_v2 pool exhausted -> converged', session.session_id)
        else:
            _action_card_accepted = False
            next_bid = None

        # Add real cards to exposed_ids; the action-card sentinel is NEVER added.
        if next_bid and next_bid != _ACTION_CARD_ID and next_bid not in session.exposed_ids:
            session.exposed_ids = session.exposed_ids + [next_bid]

        _mark('select_done')

        # Save session BEFORE prefetch so concurrent requests see updated exposed_ids.
        # pool_ids/pool_scores/current_pool_tier included unconditionally to persist
        # any in-place mutations from refresh_pool_if_low (A4 pool exhaustion guard).
        _save_fields = [
            'preference_vector', 'current_round', 'exposed_ids',
            'phase', 'like_vectors', 'convergence_history', 'previous_pref_vector',
            'pool_ids', 'pool_scores', 'current_pool_tier',
            'action_card_shown',
        ]
        if _pool_refreshed_v2 or _v2_upgraded:
            _save_fields.append('original_filters')   # off_tag flag / v2 marker
        if _v2_upgraded:
            _save_fields.append('initial_batch')      # cleared by the lazy upgrade
        session.save(update_fields=_save_fields)

        # Save copies for prefetch calculation outside transaction.
        # saved_like_vectors is already hydrated (via _hydrated_lv computed above)
        # so compute_sync_prefetch can pass it directly to engine functions.
        saved_pool_ids = list(session.pool_ids)
        saved_exposed_ids = list(session.exposed_ids)
        saved_like_vectors = list(_hydrated_lv)
        saved_initial_batch = list(session.initial_batch) if session.initial_batch else []
        saved_current_round = session.current_round
        saved_phase = session.phase
        saved_multimodal_floor = session.multimodal_floor
        # Cache pool_embeddings -- same pool_ids, no need to re-fetch outside transaction
        saved_pool_embeddings = pool_embeddings
        saved_recent_actions = list(_recent_actions_window)
        # taste_v2 only: plain-data selector snapshot for the prefetch lookahead
        saved_selector_ctx = _selector_ctx

    # Return the data needed by the view for the post-transaction prefetch + response
    return {
        'session': session,
        'project': project,
        'next_bid': next_bid,
        'saved_pool_ids': saved_pool_ids,
        'saved_exposed_ids': saved_exposed_ids,
        'saved_like_vectors': saved_like_vectors,
        'saved_initial_batch': saved_initial_batch,
        'saved_current_round': saved_current_round,
        'saved_phase': saved_phase,
        'saved_multimodal_floor': saved_multimodal_floor,
        'saved_pool_embeddings': saved_pool_embeddings,
        'saved_recent_actions': saved_recent_actions,
        'saved_selector_ctx': saved_selector_ctx,
        '_card_kind': _card_kind,
        'pool_embeddings': pool_embeddings,
        '_embedding_stats': _embedding_stats,
        '_pool_escalation_fired': _pool_escalation_fired,
        '_timing_marks': _timing_marks,
        '_t_start': _t_start,
        # True when user RIGHT-swiped the action card (chose the report)
        '_action_card_accepted': _action_card_accepted,
    }


def build_swipe_telemetry(
    request, session, profile, action, canonical_bld_id, idempotency_key,
    _embedding_stats, _pool_escalation_fired, _timing_marks, prefetch_strategy,
    saved_recent_actions,
):
    """Build the telemetry kwargs dicts for the swipe + confidence_update events.

    Called by SwipeView.post after prefetch, before spawning the telemetry thread.
    Pure data assembly — no DB writes, no threads.
    """
    _timing_breakdown = {
        'lock_ms':     max(0, _timing_marks.get('lock_acquired', 0)),
        'embed_ms':    max(0, _timing_marks.get('embed_done', 0) - _timing_marks.get('lock_acquired', 0)),
        'select_ms':   max(0, _timing_marks.get('select_done', 0) - _timing_marks.get('embed_done', 0)),
        'prefetch_ms': max(0, _timing_marks.get('prefetch_done', 0) - _timing_marks.get('select_done', 0)),
        'total_ms':    max(0, _timing_marks.get('total', 0)),
    }
    # intensity was computed inside the action=='like' branch; initialize to None for dislike
    _intensity = None
    if action == 'like':
        try:
            raw_intensity = request.data.get('intensity', 1.0)
            _intensity = float(raw_intensity) if raw_intensity is not None else 1.0
            _intensity = max(0.0, min(2.0, _intensity))
        except (TypeError, ValueError):
            _intensity = 1.0
    _rank_in_pool = None
    try:
        _rank_in_pool = session.pool_ids.index(canonical_bld_id)
    except (ValueError, AttributeError):
        pass
    # IMP-7 §6 swipe telemetry extensions
    _cache_misses = _embedding_stats.get('cache_misses', 1)
    _pool_sig = None
    try:
        _pool_sig = hashlib.sha256(
            ','.join(sorted(session.pool_ids)).encode()
        ).hexdigest()[:16]
    except Exception:
        pass

    confidence = engine.compute_confidence(
        session.convergence_history,
        RC.get('convergence_threshold', 0.13),
        window=RC.get('convergence_window', 3),
        recent_actions=saved_recent_actions[-RC.get('convergence_window', 3):],
        min_recent_likes=RC.get('convergence_min_recent_likes', 0),
    )

    _swipe_telem = dict(
        session=session, user=profile, direction=action, card_id=canonical_bld_id,
        intensity=_intensity, rank_in_pool=_rank_in_pool,
        timing_breakdown=_timing_breakdown, idempotency_key=idempotency_key,
        cache_hit=_cache_misses == 0,
        cache_source='precompute' if _cache_misses == 0 else 'fresh',
        cache_partial_miss_count=_cache_misses,
        prefetch_strategy=prefetch_strategy,
        db_call_count=None,
        pool_escalation_fired=_pool_escalation_fired,
        pool_signature_hash=_pool_sig,
    )
    _confidence_telem = None
    if confidence is not None:
        dominant_attrs = []
        if session.preference_vector:
            pref = np.asarray(session.preference_vector, dtype=float)
            if pref.size > 0:
                top_idxs = np.argsort(np.abs(pref))[-3:][::-1]
                dominant_attrs = [int(i) for i in top_idxs]
        _clustering_stats = engine.get_last_clustering_stats() or {}
        _confidence_telem = dict(
            session=session, user=profile,
            confidence=round(float(confidence), 4),
            dominant_attrs=dominant_attrs,
            action=action,
            cluster_count_used=_clustering_stats.get('cluster_count_used'),
            silhouette_score=_clustering_stats.get('silhouette_score'),
            soft_relevance_used=_clustering_stats.get('soft_relevance_used', False),
            n_likes_at_decision=_clustering_stats.get('n_likes_at_decision'),
        )

    return _swipe_telem, _confidence_telem, confidence, _timing_breakdown, _cache_misses


def compute_sync_prefetch(
    saved_phase=None, saved_exposed_ids=None, saved_initial_batch=None,
    saved_current_round=None, saved_pool_ids=None, saved_pool_embeddings=None,
    saved_like_vectors=None, saved_multimodal_floor=None,
    *, selector_ctx=None,
):
    """Compute prefetch IDs on the sync path (CPU-only, no DB).

    Returns (pf_bid, pf2_bid) from the taste_v2 selector lookahead. The legacy
    phase/round/like-vector positionals are accepted (and ignored) so older
    callers keep working; `selector_ctx` is what drives the pick.
    """
    if selector_ctx is None:
        return None, None
    try:
        return swipe_rules.lookahead(
            saved_pool_ids or [], saved_exposed_ids or [], saved_pool_embeddings or {},
            saved_initial_batch or [], selector_ctx,
        )
    except Exception:
        return None, None
