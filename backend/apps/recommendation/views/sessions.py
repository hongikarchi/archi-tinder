import logging
from collections import defaultdict

from django.conf import settings
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from ..models import Project, AnalysisSession
from .. import engine, event_log, services
from ._shared import _get_profile, _progress

logger = logging.getLogger('apps.recommendation')
RC = settings.RECOMMENDATION

# Known filter keys for filter_priority validation
_VALID_FILTER_KEYS = frozenset([
    'program', 'location_country', 'style', 'material',
    'min_area', 'max_area', 'year_min', 'year_max',
])


# ── Analysis Sessions ─────────────────────────────────────────────────────────

class SessionCreateView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        profile = _get_profile(request)
        if not profile:
            return Response({'detail': 'Profile not found'}, status=status.HTTP_404_NOT_FOUND)

        project_id      = request.data.get('project_id')
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

        # Resolve project (project_id may be a local ID like 'proj_xxx' -- ignore gracefully)
        project = None
        if project_id:
            try:
                project = Project.objects.filter(project_id=project_id, user=profile).first()
            except Exception:
                project = None
        if not project:
            project = Project.objects.create(user=profile, name='Untitled', filters=filters)

        # Topic 01 RRF: extract raw_query early — needed for both RRF q_text and
        # IMP-6 cache key. Coerce to None for non-string or oversized values.
        _raw_query_early = request.data.get('query') or None
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
        active_filters = filters or project.filters or {}
        pool_ids, pool_scores, current_pool_tier = engine.create_pool_with_relaxation(
            active_filters, filter_priority, seed_ids, v_initial=v_initial, q_text=q_text_param,
        )
        filter_relaxed = current_pool_tier > 1
        if filter_relaxed:
            logger.info('Session pool relaxed to tier %d: %d buildings', current_pool_tier, len(pool_ids))

        if not pool_ids:
            # Truly unrecoverable (even random pool empty)
            return Response({'detail': 'No buildings match your criteria'}, status=404)

        # Get pool embeddings
        pool_embeddings = engine.get_pool_embeddings(pool_ids)

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

        first_card = engine.get_building_card(initial_batch[0])
        prefetch_card = engine.get_building_card(initial_batch[1]) if len(initial_batch) > 1 else None
        prefetch_card_2 = engine.get_building_card(initial_batch[2]) if len(initial_batch) > 2 else None

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

        logger.info('Session created: %s (pool=%d, tiers=%d, relaxed=%s)', session.session_id, len(pool_ids), len(tiers), filter_relaxed)

        # §6 logging: session_start + pool_creation events
        raw_query = request.data.get('query') or None
        event_log.emit_event(
            'session_start',
            session=session,
            user=profile,
            query=raw_query,
            filters=active_filters,
            filter_priority=list(filter_priority or []),
            raw_query=raw_query,
            visual_description=visual_description,
            v_initial_success=v_initial is not None,
        )
        event_log.emit_event(
            'pool_creation',
            session=session,
            user=profile,
            pool_size=len(pool_ids),
            tier_used=current_pool_tier,
            filter_relaxed=filter_relaxed,
            seed_count=len(seed_ids or []),
        )

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


class SessionStateView(APIView):
    """
    Return the current resumable state of an active session without creating
    a new one. Used by the frontend on page refresh to restore the swipe
    session where the user left off.

    Response shape matches SwipeView so the frontend can reuse normalization.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request, session_id):
        profile = _get_profile(request)
        if not profile:
            return Response({'detail': 'Profile not found'}, status=status.HTTP_404_NOT_FOUND)

        session = AnalysisSession.objects.filter(session_id=session_id, user=profile).first()
        if not session:
            return Response({'detail': 'Session not found'}, status=status.HTTP_404_NOT_FOUND)

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
            })

        # Current card: the last card added to exposed_ids (or the first if brand-new)
        # If phase is converged, return an action card instead of a building card.
        exposed_ids = list(session.exposed_ids or [])
        pool_ids = list(session.pool_ids or [])
        initial_batch = list(session.initial_batch or [])
        like_vectors = list(session.like_vectors or [])
        current_round = session.current_round
        phase = session.phase

        if phase == 'converged':
            current_card = engine.build_action_card()
            prefetch_card = None
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
        current_card = engine.get_building_card(current_bid) if current_bid else None

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
                prefetch_card = engine.get_building_card(pf_bid) if pf_bid else None
            elif phase == 'analyzing':
                pf_id = engine.compute_mmr_next(
                    pool_ids, exposed_ids, pool_embeddings,
                    like_vectors, current_round + 1
                )
                prefetch_card = engine.get_building_card(pf_id) if pf_id else None
        except Exception:
            prefetch_card = None

        try:
            if prefetch_card and prefetch_card.get('building_id') != '__action_card__':
                temp_exposed = exposed_ids + [prefetch_card['building_id']]
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
                    prefetch_card_2 = engine.get_building_card(pf2_bid) if pf2_bid else None
                elif phase == 'analyzing':
                    pf2_id = engine.compute_mmr_next(
                        pool_ids, temp_exposed, pool_embeddings,
                        like_vectors, current_round + 2
                    )
                    prefetch_card_2 = engine.get_building_card(pf2_id) if pf2_id else None
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
        })


class SessionResultView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, session_id):
        profile = _get_profile(request)
        if not profile:
            return Response({'detail': 'Profile not found'}, status=status.HTTP_404_NOT_FOUND)
        session = AnalysisSession.objects.filter(session_id=session_id, user=profile).first()
        if not session:
            return Response({'detail': 'Session not found'}, status=status.HTTP_404_NOT_FOUND)

        # Liked buildings
        liked_ids   = list(session.swipes.filter(action='like').values_list('building_id', flat=True))
        liked_cards = [engine.get_building_card(bid) for bid in liked_ids]
        liked_cards = [c for c in liked_cards if c]

        # Use MMR-diversified results when like_vectors available
        if session.like_vectors:
            predicted_cards = engine.get_top_k_mmr(
                session.like_vectors,
                session.exposed_ids,
                k=RC['top_k_results'],
                round_num=session.current_round,
            )
        else:
            predicted_cards = engine.get_top_k_results(
                session.preference_vector,
                session.exposed_ids,
                k=RC['top_k_results'],
            )

        # Capture initial cosine order BEFORE any reorder (needed for RRF composition)
        candidate_ids_cosine_order = [c['building_id'] for c in predicted_cards]
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
            candidate_metadata = [
                {
                    'building_id': c['building_id'],
                    'name_en': c.get('name_en', ''),
                    'atmosphere': c.get('atmosphere', ''),
                    'material': c.get('material', ''),
                    'architect': c.get('architect', ''),
                    'style': c.get('style', ''),
                    'program': c.get('program', ''),
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
                card_by_id = {c['building_id']: c for c in predicted_cards}
                _gemini_top10 = new_order[:10]  # IMP-10: store Gemini top-10 for provenance
                if new_order != candidate_ids_cosine_order:
                    rerank_rank_by_id = {bid: i + 1 for i, bid in enumerate(new_order)}
                predicted_cards = [card_by_id[bid] for bid in new_order if bid in card_by_id]

        # Topic 04 (b): DPP greedy MAP at session-final top-K (with Option α composition)
        if (RC.get('dpp_topk_enabled', False)
                and len(predicted_cards) >= 2
                and session.like_vectors):
            candidate_ids = [c['building_id'] for c in predicted_cards]
            k = min(RC.get('top_k_results', 20), len(candidate_ids))
            card_by_id = {c['building_id']: c for c in predicted_cards}

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

        # IMP-10: persist top-10 lists for bookmark provenance lookup.
        # Only update if values changed (guard against repeated GET calls doing needless writes).
        _top10_fields_changed = (
            session.cosine_top10_ids != _cosine_top10
            or session.gemini_top10_ids != _gemini_top10
            or session.dpp_top10_ids != _dpp_top10
        )
        if _top10_fields_changed:
            try:
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
