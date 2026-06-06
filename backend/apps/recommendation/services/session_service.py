"""session_service.py — orchestration extracted from views/sessions.py.

Pure move: logic relocated verbatim from SessionCreateView, SessionStateView,
and SessionResultView. Zero behaviour changes. Response objects are built and
returned here so the views stay thin.

Mock-patch discipline (CRITICAL):
- engine, services, event_log imported AS MODULES so that test patches via
  `apps.recommendation.views.engine.<fn>` resolve at call time through the
  shared module object.
- NEVER `from ..engine import some_fn` — that copies the name into this
  module's namespace and breaks the patch path.
"""
import logging
from collections import defaultdict

from django.conf import settings
from django.core.cache import cache
from django.db import transaction
from rest_framework import status
from rest_framework.response import Response

from .. import engine  # noqa: import MODULE — patch path apps.recommendation.views.engine.*
from .. import event_log  # noqa: import MODULE — patch path apps.recommendation.views.event_log.*
from .. import services  # noqa: import MODULE — patch path apps.recommendation.views.services.*
from ..models import Project, AnalysisSession
from ..caches import evict_projects_list, evict_user_profile_detail, evict_project_detail
from ..perf_timing import stage
from ..views._shared import _progress

logger = logging.getLogger('apps.recommendation')
RC = settings.RECOMMENDATION

# Known filter keys for filter_priority validation (canonical_v2 schema)
_VALID_FILTER_KEYS = frozenset([
    'program', 'location_country', 'location_city', 'style', 'material',
    'year_min', 'year_max',
])
_VALID_IMAGE_FOCUS = frozenset(['exterior', 'interior', 'drawing', 'aerial', 'detail'])


# ---------------------------------------------------------------------------
# SessionCreateView orchestration
# ---------------------------------------------------------------------------

def create_session(request, profile, recent_cutoff):
    """Orchestrate session creation.

    ``recent_cutoff`` is computed by the caller (views/sessions.py) as
    ``timezone.now() - timedelta(seconds=30)`` so that the
    ``apps.recommendation.views.sessions.timezone`` mock.patch target in
    test_session_create_dedupe.py remains effective.

    All other orchestration (input validation, dedupe, pool creation,
    initial-batch selection, DB writes, cache eviction, event emission)
    lives here verbatim from the original view body.
    """
    project_id      = request.data.get('project_id')
    project_name    = (request.data.get('name') or '').strip()[:100] or 'Untitled'
    filters         = request.data.get('filters') or {}

    # Validate and sanitize filter_priority: must be a list of known filter key strings, max 10
    raw_priority = request.data.get('filter_priority') or []
    if not isinstance(raw_priority, list):
        raw_priority = []
    filter_priority = [k for k in raw_priority if isinstance(k, str) and k in _VALID_FILTER_KEYS][:10]

    # Validate and sanitize seed_ids: must be a list of strings, max 50
    raw_seeds = request.data.get('seed_ids') or []
    if not isinstance(raw_seeds, list):
        raw_seeds = []
    seed_ids = [s for s in raw_seeds if isinstance(s, str) and len(s) <= 20][:50]

    # raw_query: accept 'raw_query' (new FE key) with 'query' fallback for old clients.
    # Separate from _raw_query_early below (which is coerced to None > 1000 chars for RRF).
    raw_query = (request.data.get('raw_query') or request.data.get('query') or '').strip()[:2000]

    # Fix 2: resolve project_id early so dedupe can skip when client targets a specific project.
    # If project_id is provided and matches an owned Project, the user intent is unambiguous
    # ("new session on THIS project") -- dedupe is inappropriate in that case.
    project = None
    if project_id:
        try:
            project = Project.objects.filter(project_id=project_id, user=profile).first()
        except Exception:
            project = None

    # Dedupe guard (2026-05-26 Codex retest INFRA-DEPLOY-3 follow-up):
    # If the same user has an active session created in the last 30s with the
    # same name + raw_query + filters, the inbound POST is most likely a duplicate
    # caused by client-side retry-on-timeout (the frontend's earlier behavior).
    # Reuse the existing session instead of creating a second Project/Session pair.
    # Only runs when client did NOT supply a valid project_id (implicit project intent).
    # See sessions.js startSession; core.js retry loop; tests/test_session_create_dedupe.py.
    if project is None:
        existing_session = (
            AnalysisSession.objects.filter(
                user=profile,
                created_at__gte=recent_cutoff,
                project__name=project_name,
                project__raw_query=raw_query,
            )
            .order_by('-created_at')
            .first()
        )
        # Verify filters match (filters is JSONField, no direct lookup; compare in Python)
        if existing_session and existing_session.project.filters == (filters or {}):
            with stage('dedupe_return_existing', session_id=str(existing_session.session_id)):
                initial_batch = list(existing_session.initial_batch or [])
                image_focus = (existing_session.original_filters or {}).get('image_focus')
                first_card = (
                    engine.get_building_card(initial_batch[0], image_focus=image_focus)
                    if initial_batch else None
                )
                logger.info(
                    'Session create dedupe hit: returning existing session %s for user %s '
                    '(name=%r raw_query=%r)',
                    existing_session.session_id, profile.id, project_name,
                    raw_query[:40] if raw_query else '',
                )
                # Defensive eviction: in case a concurrent request populated a stale
                # entry between this dedupe lookup and the response.
                evict_projects_list(profile.id)
                evict_user_profile_detail(profile.user.id)
                return Response({
                    'session_id': str(existing_session.session_id),
                    'project_id': str(existing_session.project.project_id),
                    'session_status': existing_session.status,
                    'next_image': first_card,
                    'prefetch_image': None,
                    'prefetch_image_2': None,
                    'progress': _progress(existing_session),
                    'filter_relaxed': False,
                    'deduped': True,
                }, status=status.HTTP_200_OK)

    # Fix 3: project creation deferred to after pool fetch to avoid orphan rows.
    # (was: Project.objects.create here when project is None)

    # Topic 01 RRF: extract raw_query early — needed for both RRF q_text and
    # IMP-6 cache key. Accept 'raw_query' (FE key, sessions.js:25) with
    # 'query' fallback for old clients — mirrors the line-54 dual-key dispatch.
    # Coerce to None for non-string or oversized values.
    _raw_query_early = request.data.get('raw_query') or request.data.get('query') or None
    if _raw_query_early and not isinstance(_raw_query_early, str):
        _raw_query_early = None
    # Security: coerce oversized queries to None (RRF wants a focused query, not an essay)
    if _raw_query_early and len(_raw_query_early) > 1000:
        _raw_query_early = None
    q_text_param = _raw_query_early if RC.get('hybrid_retrieval_enabled', False) else None

    # V_initial: IMP-6 late-bind path (flag ON) or HyDE sync path (flag OFF)
    visual_description = request.data.get('visual_description') or None
    if visual_description is not None and (
        not isinstance(visual_description, str) or len(visual_description) > 5000
    ):
        visual_description = None
    v_initial = None
    with stage('v_initial'):
        if RC.get('stage_decouple_enabled', False):
            # IMP-6 Commit 1: late-bind path — try Django cache for Stage 2 product.
            # Cache miss (Commit 1: Stage 2 not yet implemented) returns None.
            # Filter-only pool creation follows per spec v1.5 Topic 01 graceful-degrade
            # (BM25-only RRF; rank-level fusion is order-independent, no structural issue).
            v_initial = services.get_cached_v_initial(request.user.id, _raw_query_early)
        elif RC.get('hyde_vinitial_enabled', False) and visual_description:
            # IMP-6 OFF: existing sync HyDE V_initial path — byte-identical to pre-IMP-6
            v_initial = services.embed_visual_description(
                visual_description,
                session=None,  # session not yet created
                user=profile,
            )

    # Create bounded pool with weighted scoring (3-tier relaxation fallback via helper)
    # Fix 3: project may be None here (deferred create) -- use request filters directly.
    active_filters = dict(filters or (project.filters if project else None) or {})

    # image_focus: rider on filters dict (NOT a WHERE-clause filter, but
    # threads through to _row_to_card so cards get the user-picked cover).
    # Accept either from explicit `image_focus` param OR from filters['image_focus'].
    req_focus = request.data.get('image_focus')
    if isinstance(req_focus, str) and req_focus in _VALID_IMAGE_FOCUS:
        active_filters['image_focus'] = req_focus
    elif active_filters.get('image_focus') not in _VALID_IMAGE_FOCUS:
        active_filters.pop('image_focus', None)

    with stage('create_pool', filter_keys=','.join(sorted(active_filters.keys()))):
        pool_ids, pool_scores, current_pool_tier = engine.create_pool_with_relaxation(
            active_filters, filter_priority, seed_ids,
            v_initial=v_initial, q_text=q_text_param,
        )
    filter_relaxed = current_pool_tier > 1
    if filter_relaxed:
        logger.info('Session pool relaxed to tier %d: %d buildings', current_pool_tier, len(pool_ids))

    if not pool_ids:
        # Truly unrecoverable (even random pool empty)
        return Response({'detail': 'No buildings match your criteria'}, status=404)

    with stage('get_pool_embeddings', pool_size=len(pool_ids)):
        pool_embeddings = engine.get_pool_embeddings(pool_ids)

    with stage('build_initial_batch'):
        # Tier-ordered initial_batch: farthest-point within highest score tier first
        tiers = defaultdict(list)
        for bid in pool_ids:
            tiers[pool_scores.get(bid, 0)].append(bid)

        initial_batch = []
        exposed_temp = []
        for score in sorted(tiers.keys(), reverse=True):
            tier_ids = list(tiers[score])  # copy so we can mutate
            while len(initial_batch) < RC['initial_explore_rounds'] and tier_ids:
                next_bid = engine.farthest_point_from_pool(tier_ids, exposed_temp, pool_embeddings)
                if next_bid:
                    initial_batch.append(next_bid)
                    exposed_temp.append(next_bid)
                    tier_ids.remove(next_bid)
                else:
                    break
            if len(initial_batch) >= RC['initial_explore_rounds']:
                break

        # Guard: if initial_batch is empty (shouldn't happen), fall back
        if not initial_batch:
            initial_batch = pool_ids[:1]

    with stage('fetch_initial_cards', n=min(3, len(initial_batch))):
        _initial_cards = engine.get_buildings_by_ids(
            initial_batch[:3], image_focus=active_filters.get('image_focus')
        )
    first_card      = _initial_cards[0] if len(_initial_cards) > 0 else None
    prefetch_card   = _initial_cards[1] if len(_initial_cards) > 1 else None
    prefetch_card_2 = _initial_cards[2] if len(_initial_cards) > 2 else None

    with stage('session_insert'):
        # Fix 3: auto-create Project only after pool/initial_batch succeeded.
        # Deferred from the old position (~line 113) to avoid orphan Project rows
        # when create_pool_with_relaxation fails or returns empty (404 branch above).
        # Fix 2: wrap both creates in a savepoint so a session-insert failure
        # rolls back the project create, leaving no orphan row.
        with transaction.atomic():
            if project is None:
                project = Project.objects.create(
                    user=profile, name=project_name, filters=filters, raw_query=raw_query,
                )
            session = AnalysisSession.objects.create(
                user                     = profile,
                project                  = project,
                phase                    = 'exploring',
                pool_ids                 = pool_ids,
                pool_scores              = pool_scores,
                current_round            = 0,
                preference_vector        = [],
                exposed_ids              = [initial_batch[0]],
                initial_batch            = initial_batch,
                like_vectors             = [],
                convergence_history      = [],
                previous_pref_vector     = [],
                original_filters         = active_filters,
                original_filter_priority = list(filter_priority or []),
                original_seed_ids        = list(seed_ids or []),
                current_pool_tier        = current_pool_tier,
                v_initial                = v_initial,
                original_q_text          = q_text_param,  # Topic 01 RRF: persisted for re-relaxation
            )

    # Fix 1: evict /projects/ cache after new session+project created.
    # The cache includes latest_session_meta and project counts; stale up to 60s otherwise.
    evict_projects_list(profile.id)
    evict_user_profile_detail(profile.user.id)
    # BACK-BOARD-PERF-1: evict project detail — latest_session_id changes on session create.
    evict_project_detail(str(project.project_id))

    # F4: seed prefetch cache for round 1 (first swipe's cache-read key).
    # IMP-8 consumer (swipe.py L764) reads prefetch:{sid}:{saved_current_round}
    # where saved_current_round = session.current_round AFTER first swipe's
    # increment (0 → 1). Without this seed, first swipe always misses.
    # Cache value shape mirrors _async_prefetch_thread's write (swipe.py L151-155).
    _pf_seed = {
        'prefetch_card_id': initial_batch[1] if len(initial_batch) > 1 else None,
        'prefetch_card_2_id': initial_batch[2] if len(initial_batch) > 2 else None,
    }
    cache.set(
        f'prefetch:{session.session_id}:1',
        _pf_seed,
        timeout=RC.get('async_prefetch_cache_timeout_seconds', 60),
    )

    logger.info('Session created: %s (pool=%d, tiers=%d, relaxed=%s)', session.session_id, len(pool_ids), len(tiers), filter_relaxed)

    # §6 logging: session_start + pool_creation. Keep this synchronous:
    # emit_event_batch is best-effort, and using the established request
    # connection avoids thread-local DB connection setup failures.
    with stage('emit_events'):
        event_log.emit_event_batch([
            {
                'event_type': 'session_start',
                'session': session,
                'user': profile,
                'query': raw_query or None,
                'filters': active_filters,
                'filter_priority': list(filter_priority or []),
                'raw_query': raw_query or None,
                'visual_description': visual_description,
                'v_initial_success': v_initial is not None,
            },
            {
                'event_type': 'pool_creation',
                'session': session,
                'user': profile,
                'pool_size': len(pool_ids),
                'tier_used': current_pool_tier,
                'filter_relaxed': filter_relaxed,
                'seed_count': len(seed_ids or []),
            },
        ])

    return Response({
        'session_id':      str(session.session_id),
        'project_id':      str(project.project_id),
        'session_status':  session.status,
        'next_image':      first_card,
        'prefetch_image':  prefetch_card,
        'prefetch_image_2': prefetch_card_2,
        'progress':        _progress(session),
        'filter_relaxed':  filter_relaxed,
    }, status=status.HTTP_201_CREATED)


# ---------------------------------------------------------------------------
# SessionStateView orchestration
# ---------------------------------------------------------------------------

def get_session_state(request, session):
    """Orchestrate session-state retrieval. Verbatim from SessionStateView.get."""
    # Completed session: tell the frontend to go to results
    if session.status == 'completed' or session.phase == 'completed':
        return Response({
            'session_id':      str(session.session_id),
            'project_id':      str(session.project.project_id),
            'session_status':  session.status,
            'next_image':      None,
            'prefetch_image':  None,
            'prefetch_image_2': None,
            'progress':        _progress(session),
            'filter_relaxed':  False,
            'is_analysis_completed': True,
            'can_continue':    False,
        })

    # Current card: the last card added to exposed_ids (or the first if brand-new)
    # If phase is converged, return an action card instead of a building card.
    exposed_ids = list(session.exposed_ids or [])
    pool_ids = list(session.pool_ids or [])
    initial_batch = list(session.initial_batch or [])
    like_vectors = list(session.like_vectors or [])
    current_round = session.current_round
    phase = session.phase
    image_focus = (session.original_filters or {}).get('image_focus')

    if phase == 'converged':
        residual = len([pid for pid in pool_ids if pid not in set(exposed_ids)]) if pool_ids else 0
        can_continue = (residual >= 1) and (session.extended_rounds < 5)
        prefetch_card = None
        prefetch_card_2 = None
        return Response({
            'session_id':      str(session.session_id),
            'project_id':      str(session.project.project_id),
            'session_status':  session.status,
            'next_image':      None,
            'prefetch_image':  prefetch_card,
            'prefetch_image_2': prefetch_card_2,
            'progress':        _progress(session),
            'filter_relaxed':  False,
            'is_analysis_completed': True,
            'can_continue':    can_continue,
        })

    # Recover the "current card" shown to the user.
    # Optional query param `current=<building_id>` lets the frontend hint which card it
    # was actually displaying (via instant-swap buffering). Without the hint we fall back
    # to exposed_ids[-1], which is the backend's last-selected next_image -- this may be
    # 1-2 cards ahead of what the user was looking at, but progress is still preserved.
    current_hint = request.query_params.get('current', '').strip()
    current_bid = None
    pool_set = set(pool_ids)
    if current_hint and (current_hint in set(exposed_ids) or current_hint in pool_set):
        current_bid = current_hint
        # If hint card wasn't in exposed_ids, add it so prefetch excludes it
        if current_bid not in set(exposed_ids):
            exposed_ids = exposed_ids + [current_bid]
    elif exposed_ids:
        current_bid = exposed_ids[-1]
    elif initial_batch:
        current_bid = initial_batch[0]
    current_card = engine.get_building_card(current_bid, image_focus=image_focus) if current_bid else None

    # Compute prefetch + prefetch_2 using current exposed_ids (already includes current_bid)
    pool_embeddings = engine.get_pool_embeddings(pool_ids) if pool_ids else {}

    prefetch_card = None
    prefetch_card_2 = None
    exposed_set = set(exposed_ids)
    try:
        if phase == 'exploring':
            # Use the next entries from initial_batch if still in range and not already exposed
            pf_bid = None
            for idx in range(current_round + 1, len(initial_batch)):
                cand = initial_batch[idx]
                if cand and cand not in exposed_set:
                    pf_bid = cand
                    break
            if pf_bid is None:
                pf_bid = engine.farthest_point_from_pool(pool_ids, exposed_ids, pool_embeddings)
            prefetch_card = engine.get_building_card(pf_bid, image_focus=image_focus) if pf_bid else None
        elif phase == 'analyzing':
            pf_id = engine.compute_mmr_next(
                pool_ids, exposed_ids, pool_embeddings,
                like_vectors, current_round + 1,
                multimodal_floor=session.multimodal_floor,
            )
            prefetch_card = engine.get_building_card(pf_id, image_focus=image_focus) if pf_id else None
    except Exception:
        prefetch_card = None

    try:
        if prefetch_card and prefetch_card.get('canonical_bld_id') != '__action_card__':
            temp_exposed = exposed_ids + [prefetch_card['canonical_bld_id']]
            temp_set = set(temp_exposed)
            if phase == 'exploring':
                pf2_bid = None
                for idx in range(current_round + 1, len(initial_batch)):
                    cand = initial_batch[idx]
                    if cand and cand not in temp_set:
                        pf2_bid = cand
                        break
                if pf2_bid is None:
                    pf2_bid = engine.farthest_point_from_pool(pool_ids, temp_exposed, pool_embeddings)
                prefetch_card_2 = engine.get_building_card(pf2_bid, image_focus=image_focus) if pf2_bid else None
            elif phase == 'analyzing':
                pf2_id = engine.compute_mmr_next(
                    pool_ids, temp_exposed, pool_embeddings,
                    like_vectors, current_round + 2,
                    multimodal_floor=session.multimodal_floor,
                )
                prefetch_card_2 = engine.get_building_card(pf2_id, image_focus=image_focus) if pf2_id else None
    except Exception:
        prefetch_card_2 = None

    return Response({
        'session_id':      str(session.session_id),
        'project_id':      str(session.project.project_id),
        'session_status':  session.status,
        'next_image':      current_card,
        'prefetch_image':  prefetch_card,
        'prefetch_image_2': prefetch_card_2,
        'progress':        _progress(session),
        'filter_relaxed':  False,
        'can_continue':    False,
    })


# ---------------------------------------------------------------------------
# SessionResultView orchestration
# ---------------------------------------------------------------------------

def get_session_result(session):
    """Orchestrate session-result computation. Verbatim from SessionResultView.get."""
    # Liked buildings (batch fetch — cache-aware, preserves order, applies is_publishable gate)
    liked_ids   = list(session.swipes.filter(action='like').values_list('canonical_bld_id', flat=True))
    liked_cards = engine.get_buildings_by_ids(liked_ids)
    liked_cards = [c for c in liked_cards if c]

    # Use MMR-diversified results when like_vectors available
    if session.like_vectors:
        predicted_cards = engine.get_top_k_mmr(
            session.like_vectors,
            session.exposed_ids,
            k=RC['top_k_results'],
            round_num=session.current_round,
            multimodal_floor=session.multimodal_floor,
            question_bias_vector=session.question_bias_vector,
        )
    else:
        predicted_cards = engine.get_top_k_results(
            session.preference_vector,
            session.exposed_ids,
            k=RC['top_k_results'],
            question_bias_vector=session.question_bias_vector,
        )

    # Topic 04(b) DPP: when flag ON, over-fetch candidates so DPP MAP can actually narrow.
    # Without over-fetch, n == k and DPP's early-return branch fires (no-op).
    # Cosine/Gemini top-10 provenance fields slice the first top_k_results entries
    # of the over-fetched set so their semantics match pre-fix.
    _overfetch_mult = RC.get('dpp_overfetch_multiplier', 3) if RC.get('dpp_topk_enabled', False) else 1
    if _overfetch_mult > 1 and session.like_vectors:
        # Re-fetch with larger k via the MMR branch (already used when like_vectors exist)
        predicted_cards = engine.get_top_k_mmr(
            session.like_vectors,
            session.exposed_ids,
            k=RC['top_k_results'] * _overfetch_mult,
            round_num=session.current_round,
            multimodal_floor=session.multimodal_floor,
            question_bias_vector=session.question_bias_vector,
        )

    # Capture initial cosine order BEFORE any reorder (needed for RRF composition)
    candidate_ids_cosine_order = [c['canonical_bld_id'] for c in predicted_cards]
    rerank_rank_by_id = None  # populated only when Topic 02 ran with a real reorder

    # IMP-10 sub-task A / Spec v1.7 §11.1: track top-10 sets for bookmark provenance.
    # cosine_top10 is always captured here (pre-rerank); other channels only when their flag ran.
    # Sessions created before migration 0013 have None for all three fields (backward-compat).
    # Note: SessionResultView is a GET but writes these fields once per result view.
    # Writes are idempotent (same result on repeated calls) -- no semantic problem.
    _cosine_top10 = candidate_ids_cosine_order[:10]
    _gemini_top10 = None   # populated below only when rerank actually reordered
    _dpp_top10 = None       # populated below only when DPP ran

    # Topic 02: Gemini setwise rerank (session-end, off swipe hot path)
    if RC.get('gemini_rerank_enabled', False) and len(predicted_cards) >= 2:
        # Pass cards in the shape rerank_candidates expects: canonical_bld_id +
        # name (top-level) and metadata.axis_* (as produced by engine._row_to_card).
        candidate_metadata = [
            {
                'canonical_bld_id': c['canonical_bld_id'],
                'name': c.get('name', ''),
                'metadata': c.get('metadata') or {},
            }
            for c in predicted_cards
        ]
        liked_summary = services._liked_summary_for_rerank(session.project.liked_ids)
        new_order = services.rerank_candidates(candidate_metadata, liked_summary)

        # Capture both ranks for potential RRF fusion (Topic 02 ∩ 04 Option α).
        # Sentinel: only set rerank_rank_by_id when rerank produced a real reorder.
        # If rerank returned input order (failure / no-op), DPP falls back to cosine q.
        # IMP-10 fix: _gemini_top10 reflects "Gemini ranked it" regardless of whether
        # order changed -- provenance = "Gemini ran", not "Gemini moved it".
        if new_order and set(new_order) == set(candidate_ids_cosine_order):
            card_by_id = {c['canonical_bld_id']: c for c in predicted_cards}
            _gemini_top10 = new_order[:10]  # IMP-10: store Gemini top-10 for provenance
            if new_order != candidate_ids_cosine_order:
                rerank_rank_by_id = {bid: i + 1 for i, bid in enumerate(new_order)}
            predicted_cards = [card_by_id[bid] for bid in new_order if bid in card_by_id]

    # Topic 04 (b): DPP greedy MAP at session-final top-K (with Option α composition)
    if (RC.get('dpp_topk_enabled', False)
            and len(predicted_cards) >= 2
            and session.like_vectors):
        candidate_ids = [c['canonical_bld_id'] for c in predicted_cards]
        k = min(RC.get('top_k_results', 20), len(candidate_ids))
        card_by_id = {c['canonical_bld_id']: c for c in predicted_cards}

        if rerank_rank_by_id is not None:
            # Option α composition: q = min-max-rescaled RRF fusion
            # (Investigation 07 + Investigation 14 §q derivation)
            cosine_rank_by_id = {bid: i + 1 for i, bid in enumerate(candidate_ids_cosine_order)}
            K_RRF = 60  # Investigation 07 standard k=60
            fused = {
                bid: (1.0 / (K_RRF + cosine_rank_by_id[bid])) + (1.0 / (K_RRF + rerank_rank_by_id[bid]))
                for bid in candidate_ids
                if bid in cosine_rank_by_id and bid in rerank_rank_by_id
            }
            if fused:
                fmin = min(fused.values())
                fmax = max(fused.values())
                if fmax > fmin:
                    q_values = {
                        bid: 0.01 + 0.99 * (fused[bid] - fmin) / (fmax - fmin)
                        for bid in fused
                    }
                else:
                    q_values = {bid: 0.5 for bid in fused}  # all-equal edge case
            else:
                q_values = {}
            dpp_order = engine.compute_dpp_topk(
                predicted_cards, session.like_vectors, k=k, q_override=q_values or None
            )
        else:
            # Standalone Topic 04: q derived from max centroid cosine inside compute_dpp_topk
            dpp_order = engine.compute_dpp_topk(predicted_cards, session.like_vectors, k=k)

        _dpp_top10 = dpp_order[:10]  # IMP-10: store DPP top-10 for provenance
        predicted_cards = [card_by_id[bid] for bid in dpp_order if bid in card_by_id]

    # Guard: ensure predicted_cards is exactly top_k_results items at response time.
    # DPP path already narrows to k; non-DPP over-fetch=1 never grows.
    # Defensive slice handles any edge case where over-fetch candidate leaks through.
    predicted_cards = predicted_cards[:RC.get('top_k_results', 20)]

    # IMP-10: persist top-10 lists for bookmark provenance lookup.
    # Atomic check-then-write inside transaction.atomic() (Finding #16). Two
    # concurrent GET callers cannot race a partial update — the multi-field
    # save is atomic. Lock-free: writes are IDEMPOTENT (same input → same
    # top-10 values), so a duplicate write is a no-op, not corruption.
    try:
        with transaction.atomic():
            _top10_fields_changed = (
                session.cosine_top10_ids != _cosine_top10
                or session.gemini_top10_ids != _gemini_top10
                or session.dpp_top10_ids != _dpp_top10
            )
            if _top10_fields_changed:
                session.cosine_top10_ids = _cosine_top10
                session.gemini_top10_ids = _gemini_top10
                session.dpp_top10_ids = _dpp_top10
                session.save(update_fields=['cosine_top10_ids', 'gemini_top10_ids', 'dpp_top10_ids'])
    except Exception as _exc:
        logger.warning(
            'SessionResultView: failed to persist top10 lists for session %s: %s',
            session.session_id, _exc,
        )

    return Response({
        'session_id':          str(session.session_id),
        'session_status':      session.status,
        'liked_images':        liked_cards,
        'predicted_images':    predicted_cards,
        'predicted_like_count': len(predicted_cards),
        'analysis_report':     session.project.analysis_report,
        'generated_at':        session.created_at.isoformat(),
    })
