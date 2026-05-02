import hashlib
import logging
import threading

import numpy as np
from django.conf import settings
from django.core.cache import cache
from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from ..models import Project, AnalysisSession, SwipeEvent
from .. import engine, event_log
from ._shared import _get_profile, _progress, _liked_id_only

logger = logging.getLogger('apps.recommendation')
RC = settings.RECOMMENDATION


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


# ── IMP-8: async prefetch background thread ───────────────────────────────────

def _async_prefetch_thread(
    session_id, cache_round, phase,
    pool_ids_snap, exposed_ids_snap, pool_embeddings_snap,
    like_vectors_snap, initial_batch_snap, current_round_snap,
):
    """IMP-8 (Spec v1.6 §11.1): background thread to compute prefetch cards
    after primary swipe response returns. Result cached for telemetry / future
    Half-B optimization (currently primary path does NOT consume the cache --
    see design notes in commit body).

    Snapshots are passed as args (NOT the session object) because the session
    may have been further mutated by the time the bg thread runs; prefetch
    should reflect the state at swipe-response-emit time.

    CPython GIL note: engine module globals (_building_embedding_cache,
    _last_embedding_call_stats) are shared across threads. Dict ops are GIL-
    protected so the embedding cache is safe to read/write concurrently. The
    primary thread reads _last_embedding_call_stats before spawning (line ~716
    in SwipeView.post) so the swipe event payload is already captured.

    Race handling: if the next swipe arrives before this thread finishes, the
    primary path runs standalone (cache miss) -- same behavior as today.
    This is purely opportunistic and never blocks correctness.
    """
    from django.db import connection as _db_connection

    _db_connection.close()  # release parent thread's connection; bg thread gets its own
    try:
        prefetch_card = None
        prefetch_card_2 = None

        # Compute prefetch_card (round+1 equivalent)
        if phase == 'exploring':
            exposed_set = set(exposed_ids_snap)
            if current_round_snap + 1 < len(initial_batch_snap):
                pf_bid = initial_batch_snap[current_round_snap + 1]
                if pf_bid and pf_bid not in exposed_set:
                    prefetch_card = engine.get_building_card(pf_bid)
                else:
                    pf_bid = engine.farthest_point_from_pool(pool_ids_snap, exposed_ids_snap, pool_embeddings_snap)
                    prefetch_card = engine.get_building_card(pf_bid) if pf_bid else None
            else:
                pf_bid = engine.farthest_point_from_pool(pool_ids_snap, exposed_ids_snap, pool_embeddings_snap)
                prefetch_card = engine.get_building_card(pf_bid) if pf_bid else None
        elif phase == 'analyzing':
            pf_id = engine.compute_mmr_next(
                pool_ids_snap, exposed_ids_snap, pool_embeddings_snap,
                like_vectors_snap, current_round_snap + 1
            )
            prefetch_card = engine.get_building_card(pf_id) if pf_id else None

        # Compute prefetch_card_2 (round+2 equivalent)
        if prefetch_card and prefetch_card.get('building_id') != '__action_card__':
            temp_exposed = exposed_ids_snap + [prefetch_card['building_id']]
            if phase == 'exploring':
                exposed_set_2 = set(temp_exposed)
                if current_round_snap + 2 < len(initial_batch_snap):
                    pf2_bid = initial_batch_snap[current_round_snap + 2]
                    if pf2_bid and pf2_bid not in exposed_set_2:
                        prefetch_card_2 = engine.get_building_card(pf2_bid)
                    else:
                        pf2_bid = engine.farthest_point_from_pool(pool_ids_snap, temp_exposed, pool_embeddings_snap)
                        prefetch_card_2 = engine.get_building_card(pf2_bid) if pf2_bid else None
                else:
                    pf2_bid = engine.farthest_point_from_pool(pool_ids_snap, temp_exposed, pool_embeddings_snap)
                    prefetch_card_2 = engine.get_building_card(pf2_bid) if pf2_bid else None
            elif phase == 'analyzing':
                pf2_id = engine.compute_mmr_next(
                    pool_ids_snap, temp_exposed, pool_embeddings_snap,
                    like_vectors_snap, current_round_snap + 2
                )
                prefetch_card_2 = engine.get_building_card(pf2_id) if pf2_id else None

        result = {
            'prefetch_card_id': prefetch_card.get('building_id') if prefetch_card else None,
            'prefetch_card_2_id': prefetch_card_2.get('building_id') if prefetch_card_2 else None,
            'computed_at': timezone.now().isoformat(),
        }
        cache_key = f'prefetch:{session_id}:{cache_round}'
        cache_timeout = settings.RECOMMENDATION.get('async_prefetch_cache_timeout_seconds', 60)
        cache.set(cache_key, result, timeout=cache_timeout)
        logger.debug('IMP-8 async prefetch cached: key=%s', cache_key)
    except Exception as exc:
        # Cache stays empty; next swipe runs standalone path -- no failure event needed.
        # This is purely opportunistic optimization; primary path is always the source of truth.
        logger.warning('IMP-8 async prefetch thread failed: %s', exc)
    finally:
        _db_connection.close()  # release bg thread's own connection


# ── Images ────────────────────────────────────────────────────────────────────

class DiverseRandomView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        cards = engine.get_diverse_random(n=10)
        return Response(cards)


class BuildingBatchView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        ids = request.data.get('building_ids', [])
        if not ids:
            return Response([])
        if not isinstance(ids, list) or len(ids) > 200:
            return Response({'detail': 'building_ids must be a list of at most 200 items'}, status=status.HTTP_400_BAD_REQUEST)
        cards = engine.get_buildings_by_ids(ids)
        return Response(cards)


# ── Bookmark ──────────────────────────────────────────────────────────────────

class ProjectBookmarkView(APIView):
    """
    POST /api/v1/projects/<project_id>/bookmark/

    Toggle bookmark on a building in the result page top-K. Updates
    Project.saved_ids (list[{id, saved_at}]) and emits a bookmark event
    per spec §6 + §8 + Spec v1.2 SPEC-UPDATED.

    Request body:
        {
          "card_id":    "<building_id>",          # required; string, max 20 chars
          "action":     "save" | "unsave",        # required
          "rank":       <int 1-100>,              # required; 1-indexed result-page position
          "session_id": "<uuid>"                  # optional; for event association
        }

    Response 200:
        {
          "saved_ids": ["B00042", ...],   # full list of currently bookmarked building IDs
          "count": <int>                  # length of saved_ids
        }
    """
    permission_classes = [IsAuthenticated]

    def post(self, request, project_id):
        profile = _get_profile(request)
        if profile is None:
            return Response({'detail': 'unauthenticated'}, status=status.HTTP_401_UNAUTHORIZED)

        try:
            project = Project.objects.get(project_id=project_id, user=profile)
        except Project.DoesNotExist:
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

        # --- Toggle saved_ids ---
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

        # --- rank_corpus: IMP-10 sub-task A (Spec v1.7 §11.1 / Investigation 08 H1) ---
        # When the session has v_initial (HyDE was on), compute the corpus-wide cosine rank
        # of this card vs the HyDE vector. pgvector <=> ranking in SQL; O(N) corpus scan.
        # On any exception: rank_corpus stays None (observability, never blocks bookmark).
        # Sessions without v_initial (HyDE flag off) → rank_corpus stays None as before.
        rank_corpus = None
        if session is not None and getattr(session, 'v_initial', None) is not None:
            try:
                rank_corpus = engine.compute_corpus_rank(card_id, session.v_initial)
            except Exception as _rank_exc:
                # Telemetry failure must never block the bookmark
                logger.warning(
                    'ProjectBookmarkView: compute_corpus_rank failed for card %s: %s',
                    card_id, _rank_exc,
                )
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


# ── Swipe ─────────────────────────────────────────────────────────────────────

class SwipeView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, session_id):
        profile = _get_profile(request)
        if not profile:
            return Response({'detail': 'Profile not found'}, status=status.HTTP_404_NOT_FOUND)

        session = AnalysisSession.objects.filter(session_id=session_id, user=profile).first()
        if not session:
            return Response({'detail': 'Session not found'}, status=status.HTTP_404_NOT_FOUND)
        if session.status == 'completed':
            return Response({'detail': 'Session already completed'}, status=status.HTTP_400_BAD_REQUEST)

        building_id     = request.data.get('building_id')
        action          = request.data.get('action')
        idempotency_key = request.data.get('idempotency_key', '')

        # Validate and sanitize client_buffer_ids: list of building_ids the frontend has
        # prefetched in its visible queue (not yet swiped). Merging these into exposed_ids
        # prevents the backend from re-selecting cards the user already has loaded,
        # which eliminates frontend/backend queue drift ("card stuck" + "same card twice" bugs).
        raw_buffer = request.data.get('client_buffer_ids') or []
        if not isinstance(raw_buffer, list):
            raw_buffer = []
        client_buffer_ids = [
            s for s in raw_buffer
            if isinstance(s, str) and 0 < len(s) <= 20 and s != '__action_card__'
        ][:10]

        if not building_id:
            return Response({'detail': 'building_id is required'}, status=status.HTTP_400_BAD_REQUEST)
        if action not in ('like', 'dislike'):
            return Response({'detail': 'action must be like or dislike'}, status=status.HTTP_400_BAD_REQUEST)

        # Idempotency check -- if already processed, return accepted so frontend treats it as success
        if idempotency_key and SwipeEvent.objects.filter(idempotency_key=idempotency_key, session=session).exists():
            logger.info('Duplicate swipe ignored: %s', idempotency_key)
            return Response({'accepted': True, 'detail': 'duplicate'}, status=status.HTTP_200_OK)

        # SPECIAL: action card handling
        if building_id == '__action_card__':
            if action == 'like':
                # Complete the session
                with transaction.atomic():
                    session.status = 'completed'
                    session.phase = 'completed'
                    session.save(update_fields=['status', 'phase'])

                # §6 logging: session_end (user_confirm = user clicked "View results")
                all_swipes = list(session.swipes.values_list('action', flat=True))
                # IMP-10 / Spec v1.8 §6: aggregate per-session clustering stats
                _clustering_agg = event_log.aggregate_session_clustering_stats(session.session_id)
                event_log.emit_event(
                    'session_end',
                    session=session,
                    user=profile,
                    end_reason='user_confirm',
                    total_swipes=session.current_round,
                    likes_count=all_swipes.count('like'),
                    loves_count=0,  # Sprint 3 A-1 will populate this from intensity field
                    dislikes_count=all_swipes.count('dislike'),
                    cluster_count_distribution=_clustering_agg['cluster_count_distribution'],
                    silhouette_score_p50=_clustering_agg['silhouette_score_p50'],
                )

                return Response({
                    'accepted': True,
                    'session_status': 'completed',
                    'progress': _progress(session),
                    'next_image': None,
                    'prefetch_image': None,
                    'prefetch_image_2': None,
                    'is_analysis_completed': True,
                    'confidence': None,
                })
            else:
                # Reset and keep going
                with transaction.atomic():
                    session.convergence_history = []
                    session.previous_pref_vector = []
                    session.phase = 'analyzing'
                    # Merge client buffer into exposed so we don't re-show cards the
                    # frontend already has in its queue.
                    if client_buffer_ids:
                        session.exposed_ids = _merge_buffer_into_exposed(session.exposed_ids, client_buffer_ids)
                    # Pool exhaustion guard for "더 swipe" path (§5.6 + §6 A4):
                    # User is extending past auto-stop — pool is most likely exhausted here.
                    # Mutates session.pool_ids/pool_scores/current_pool_tier in-place if needed.
                    engine.refresh_pool_if_low(session, threshold=5)
                    session.save(update_fields=[
                        'phase', 'convergence_history', 'previous_pref_vector', 'exposed_ids',
                        'pool_ids', 'pool_scores', 'current_pool_tier',
                    ])
                    # Fall through to select next card below
                    # (skip normal swipe recording for action card)
                    pool_embeddings = engine.get_pool_embeddings(session.pool_ids)
                    next_card_id = engine.compute_mmr_next(
                        session.pool_ids, session.exposed_ids, pool_embeddings,
                        session.like_vectors, session.current_round
                    )
                    next_card = engine.get_building_card(next_card_id) if next_card_id else None
                    if next_card:
                        session.exposed_ids = session.exposed_ids + [next_card['building_id']]
                        session.save(update_fields=['exposed_ids'])

                    # Prefetch
                    prefetch_card = None
                    if next_card:
                        try:
                            pf_id = engine.compute_mmr_next(
                                session.pool_ids, session.exposed_ids, pool_embeddings,
                                session.like_vectors, session.current_round + 1
                            )
                            prefetch_card = engine.get_building_card(pf_id) if pf_id else None
                        except Exception:
                            pass

                    # Prefetch 2
                    prefetch_card_2 = None
                    if prefetch_card and prefetch_card.get('building_id') != '__action_card__':
                        try:
                            temp_exposed = session.exposed_ids + [prefetch_card['building_id']]
                            if session.phase == 'exploring':
                                if session.current_round + 2 < len(session.initial_batch):
                                    pf2_bid = session.initial_batch[session.current_round + 2]
                                    prefetch_card_2 = engine.get_building_card(pf2_bid)
                                else:
                                    pf2_bid = engine.farthest_point_from_pool(session.pool_ids, temp_exposed, pool_embeddings)
                                    prefetch_card_2 = engine.get_building_card(pf2_bid) if pf2_bid else None
                            elif session.phase == 'analyzing':
                                pf2_id = engine.compute_mmr_next(
                                    session.pool_ids, temp_exposed, pool_embeddings,
                                    session.like_vectors, session.current_round + 2
                                )
                                prefetch_card_2 = engine.get_building_card(pf2_id) if pf2_id else None
                        except Exception:
                            prefetch_card_2 = None

                return Response({
                    'accepted': True,
                    'session_status': session.status,
                    'progress': _progress(session),
                    'next_image': next_card,
                    'prefetch_image': prefetch_card,
                    'prefetch_image_2': prefetch_card_2,
                    'is_analysis_completed': False,
                    'confidence': None,  # history cleared on reset; hide bar until new window fills
                })

        # NORMAL SWIPE PROCESSING
        import time as _time
        _t_start = _time.perf_counter()
        _timing_marks = {}  # step_name -> elapsed_ms from _t_start

        def _mark(step):
            _timing_marks[step] = round((_time.perf_counter() - _t_start) * 1000, 2)

        with transaction.atomic():
            # Lock session row to prevent concurrent swipe corruption
            session = AnalysisSession.objects.select_for_update().get(
                session_id=session_id, user=profile
            )
            _mark('lock_acquired')

            # 1. Get embedding and update preference vector
            embedding = engine.get_building_embedding(building_id)
            _mark('embed_done')
            if embedding:
                session.preference_vector = engine.update_preference_vector(
                    session.preference_vector, embedding, action
                )

            # 2. Record swipe
            SwipeEvent.objects.create(
                session=session, building_id=building_id,
                action=action, idempotency_key=idempotency_key,
            )

            # 3. Update project liked/disliked lists
            project = session.project
            if action == 'like':
                existing_ids = _liked_id_only(project.liked_ids)
                if building_id not in existing_ids:
                    # Default intensity 1.0 for plain Like. Love (intensity 1.8) lands in Sprint 3 A-1
                    # when the frontend wires up the up-swipe gesture; for now all backend writes
                    # use 1.0 unless the request explicitly carries an intensity field (future-proofing).
                    try:
                        raw_intensity = request.data.get('intensity', 1.0)
                        intensity = float(raw_intensity) if raw_intensity is not None else 1.0
                    except (TypeError, ValueError):
                        intensity = 1.0
                    intensity = max(0.0, min(2.0, intensity))
                    project.liked_ids = project.liked_ids + [{'id': building_id, 'intensity': intensity}]
                # Append to session.like_vectors
                if embedding:
                    session.like_vectors = session.like_vectors + [{'embedding': embedding, 'round': session.current_round}]
            else:
                if building_id not in project.disliked_ids:
                    project.disliked_ids = project.disliked_ids + [building_id]
            project.save(update_fields=['liked_ids', 'disliked_ids'])

            # 4. Increment round
            session.current_round += 1

            # 5. Convergence -- use K-Means global centroid during analyzing, pref_vector during exploring.
            # Note: Delta-V is appended on EVERY analyzing swipe (not gated by action == 'like'),
            # so `convergence_window` counts rounds, not likes. On a dislike the centroid still
            # shifts slightly due to recency-weight drift, so Delta-V is smaller but non-zero.
            # Known bias: dislike Delta-V < like Delta-V may pull the moving average down on
            # dislike-heavy sequences. Acceptable per research/spec/requirements.md Section 11
            # Tier A Topic 10 Option A; revisit with data if problematic.
            if session.phase == 'analyzing' and session.like_vectors:
                _, global_centroid = engine.compute_taste_centroids(
                    session.like_vectors, session.current_round
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

            # 6. Phase transitions
            like_count = len(session.like_vectors)

            if session.phase == 'exploring' and like_count >= RC.get('min_likes_for_clustering', 3):
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

            if session.phase == 'analyzing' and engine.check_convergence(
                session.convergence_history, RC.get('convergence_threshold', 0.08), RC.get('convergence_window', 3)
            ):
                session.phase = 'converged'
                logger.info('Session %s: analyzing -> converged', session.session_id)

            # 6b. Pool exhaustion guard (§5.6 + §6 implementation requirement A4):
            # If remaining pool < 5 buildings, escalate to next filter relaxation tier
            # to extend the pool with new candidates before card selection.
            # refresh_pool_if_low mutates session.pool_ids/pool_scores/current_pool_tier
            # in-place when escalation fires.
            _tier_before_refresh = session.current_pool_tier
            if session.phase not in ('converged', 'completed'):
                engine.refresh_pool_if_low(session, threshold=5)
            _pool_escalation_fired = session.current_pool_tier != _tier_before_refresh

            # 7. Check pool exhaustion (hard-empty fallback after refresh attempt)
            remaining = [pid for pid in session.pool_ids if pid not in set(session.exposed_ids)]
            if not remaining and session.phase not in ('converged', 'completed'):
                session.phase = 'converged'
                logger.info('Session %s: pool exhausted -> converged', session.session_id)

            # 8. Card selection by phase
            pool_embeddings = engine.get_pool_embeddings(session.pool_ids)
            # Capture IMP-7 cache stats immediately after the primary get_pool_embeddings call.
            # The dislike-fallback branch below may call get_pool_embeddings again (for dislike_ids),
            # which would overwrite _last_embedding_call_stats. Reading here preserves swipe-selection stats.
            _embedding_stats = engine.get_last_embedding_call_stats() or {}

            if session.phase == 'converged':
                next_card = engine.build_action_card()
            elif session.phase == 'exploring':
                # Use initial_batch for early rounds, then farthest-point
                # Note: if the user's current_round lands on an initial_batch slot that was
                # already merged in from client_buffer_ids, pick the next valid position instead.
                exposed_set = set(session.exposed_ids)
                next_card = None
                if session.current_round < len(session.initial_batch):
                    next_bid = session.initial_batch[session.current_round]
                    if next_bid and next_bid not in exposed_set:
                        next_card = engine.get_building_card(next_bid)
                    else:
                        # Fall through to farthest-point selection (initial_batch slot exhausted)
                        next_bid = engine.farthest_point_from_pool(session.pool_ids, session.exposed_ids, pool_embeddings)
                        next_card = engine.get_building_card(next_bid) if next_bid else None
                else:
                    # Check for consecutive dislikes
                    recent_swipes = list(session.swipes.order_by('-created_at').values_list('action', flat=True)[:RC.get('max_consecutive_dislikes', 5)])
                    consecutive_dislikes = 0
                    for s in recent_swipes:
                        if s == 'dislike':
                            consecutive_dislikes += 1
                        else:
                            break

                    if consecutive_dislikes >= RC.get('max_consecutive_dislikes', 5):
                        # Batch-fetch dislike embeddings (single query instead of N individual calls)
                        dislike_ids = project.disliked_ids[-10:]
                        dislike_embeds = []
                        if dislike_ids:
                            dislike_emb_map = engine.get_pool_embeddings(dislike_ids)
                            dislike_embeds = [dislike_emb_map[did] for did in dislike_ids if did in dislike_emb_map]
                        fallback_id = engine.get_dislike_fallback(session.pool_ids, session.exposed_ids, pool_embeddings, dislike_embeds)
                        if fallback_id:
                            session.exposed_ids = session.exposed_ids + [fallback_id]
                        next_card = engine.get_building_card(fallback_id) if fallback_id else None
                    else:
                        next_bid = engine.farthest_point_from_pool(session.pool_ids, session.exposed_ids, pool_embeddings)
                        next_card = engine.get_building_card(next_bid) if next_bid else None
            elif session.phase == 'analyzing':
                next_card_id = engine.compute_mmr_next(
                    session.pool_ids, session.exposed_ids, pool_embeddings,
                    session.like_vectors, session.current_round
                )
                next_card = engine.get_building_card(next_card_id) if next_card_id else None
                if not next_card:
                    # Pool exhausted during analyzing
                    next_card = engine.build_action_card()
                    session.phase = 'converged'
            else:
                next_card = None

            if next_card and next_card.get('building_id') != '__action_card__':
                bid = next_card['building_id']
                if bid not in session.exposed_ids:
                    session.exposed_ids = session.exposed_ids + [bid]

            _mark('select_done')

            # Save session BEFORE prefetch so concurrent requests see updated exposed_ids.
            # pool_ids/pool_scores/current_pool_tier included unconditionally to persist
            # any in-place mutations from refresh_pool_if_low (A4 pool exhaustion guard).
            session.save(update_fields=[
                'preference_vector', 'current_round', 'exposed_ids',
                'phase', 'like_vectors', 'convergence_history', 'previous_pref_vector',
                'pool_ids', 'pool_scores', 'current_pool_tier',
            ])

            # Save copies for prefetch calculation outside transaction
            saved_pool_ids = list(session.pool_ids)
            saved_exposed_ids = list(session.exposed_ids)
            saved_like_vectors = list(session.like_vectors) if session.like_vectors else []
            saved_initial_batch = list(session.initial_batch) if session.initial_batch else []
            saved_current_round = session.current_round
            saved_phase = session.phase
            # Cache pool_embeddings -- same pool_ids, no need to re-fetch outside transaction
            saved_pool_embeddings = pool_embeddings

        # 9. Prefetch (outside transaction -- no lock held)
        # Reuse cached pool_embeddings from step 8 (pool_ids unchanged)
        #
        # IMP-8 (Spec v1.6 §11.1): when async_prefetch_enabled=True, spawn a
        # background daemon thread to compute prefetch cards and write to Django
        # cache. Primary response returns immediately with prefetch_image=None
        # (frontend handles null prefetches gracefully -- existing behavior at
        # session end / dislike-fallback paths). The cache write is for
        # telemetry / future Half-B optimization; primary path does NOT consume
        # the cache in this implementation.
        #
        # When async_prefetch_enabled=False (default), the existing sync path
        # runs unchanged -- no threads, no cache pressure, byte-identical behavior.
        prefetch_strategy = 'sync'  # updated to 'async-thread' when IMP-8 path runs
        prefetch_card = None
        prefetch_card_2 = None
        if settings.RECOMMENDATION.get('async_prefetch_enabled', False) and (
            next_card and next_card.get('building_id') != '__action_card__'
        ):
            # IMP-8 async path: spawn bg thread; return None prefetches immediately.
            # cache_round = saved_current_round + 1 so the key uniquely identifies
            # "the prefetch for the NEXT swipe after this one".
            t = threading.Thread(
                target=_async_prefetch_thread,
                args=(
                    str(session.session_id),
                    saved_current_round + 1,     # cache_round key
                    saved_phase,
                    saved_pool_ids,
                    saved_exposed_ids,
                    saved_pool_embeddings,
                    saved_like_vectors,
                    saved_initial_batch,
                    saved_current_round,
                ),
                daemon=True,
            )
            t.start()
            prefetch_strategy = 'async-thread'
            # prefetch_card and prefetch_card_2 stay None -- frontend handles gracefully
        elif next_card and next_card.get('building_id') != '__action_card__':
            # Existing sync prefetch path (unchanged when flag is OFF)
            try:
                if saved_phase == 'exploring':
                    exposed_set = set(saved_exposed_ids)
                    if saved_current_round + 1 < len(saved_initial_batch):
                        pf_bid = saved_initial_batch[saved_current_round + 1]
                        if pf_bid and pf_bid not in exposed_set:
                            prefetch_card = engine.get_building_card(pf_bid)
                        else:
                            pf_bid = engine.farthest_point_from_pool(saved_pool_ids, saved_exposed_ids, saved_pool_embeddings)
                            prefetch_card = engine.get_building_card(pf_bid) if pf_bid else None
                    else:
                        pf_bid = engine.farthest_point_from_pool(saved_pool_ids, saved_exposed_ids, saved_pool_embeddings)
                        prefetch_card = engine.get_building_card(pf_bid) if pf_bid else None
                elif saved_phase == 'analyzing':
                    pf_id = engine.compute_mmr_next(
                        saved_pool_ids, saved_exposed_ids, saved_pool_embeddings,
                        saved_like_vectors, saved_current_round + 1
                    )
                    prefetch_card = engine.get_building_card(pf_id) if pf_id else None
            except Exception:
                prefetch_card = None

            # Prefetch 2 (round+2)
            if prefetch_card and prefetch_card.get('building_id') != '__action_card__':
                try:
                    temp_exposed = saved_exposed_ids + [prefetch_card['building_id']]
                    if saved_phase == 'exploring':
                        exposed_set = set(temp_exposed)
                        if saved_current_round + 2 < len(saved_initial_batch):
                            pf2_bid = saved_initial_batch[saved_current_round + 2]
                            if pf2_bid and pf2_bid not in exposed_set:
                                prefetch_card_2 = engine.get_building_card(pf2_bid)
                            else:
                                pf2_bid = engine.farthest_point_from_pool(saved_pool_ids, temp_exposed, saved_pool_embeddings)
                                prefetch_card_2 = engine.get_building_card(pf2_bid) if pf2_bid else None
                        else:
                            pf2_bid = engine.farthest_point_from_pool(saved_pool_ids, temp_exposed, saved_pool_embeddings)
                            prefetch_card_2 = engine.get_building_card(pf2_bid) if pf2_bid else None
                    elif saved_phase == 'analyzing':
                        pf2_id = engine.compute_mmr_next(
                            saved_pool_ids, temp_exposed, saved_pool_embeddings,
                            saved_like_vectors, saved_current_round + 2
                        )
                        prefetch_card_2 = engine.get_building_card(pf2_id) if pf2_id else None
                except Exception:
                    prefetch_card_2 = None

        _mark('prefetch_done')
        _mark('total')

        # §6 logging: derive timing deltas (guarded with max(0,...) against missed marks)
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
            _rank_in_pool = session.pool_ids.index(building_id)
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
        event_log.emit_swipe_event(
            session=session,
            user=profile,
            direction=action,
            card_id=building_id,
            intensity=_intensity,
            rank_in_pool=_rank_in_pool,
            timing_breakdown=_timing_breakdown,
            idempotency_key=idempotency_key,
            # IMP-7 cache telemetry fields (spec v1.6 §6)
            cache_hit=_cache_misses == 0,
            cache_source='precompute' if _cache_misses == 0 else 'fresh',
            cache_partial_miss_count=_cache_misses,
            prefetch_strategy=prefetch_strategy,  # 'sync' (default) or 'async-thread' (IMP-8)
            db_call_count=None,              # IMP-9 verify; null until connection-level instrumentation added
            pool_escalation_fired=_pool_escalation_fired,
            pool_signature_hash=_pool_sig,
        )

        # Compute user-facing confidence for response (C-1)
        confidence = engine.compute_confidence(
            session.convergence_history,
            RC.get('convergence_threshold', 0.08),
            window=RC.get('convergence_window', 3),
        )

        # Emit confidence_update event (Spec v1.2 §6 + dislike-bias telemetry)
        if confidence is not None:
            # Best-effort dominant attrs from pref_vector: top-K dims by absolute magnitude.
            # Returns dimension indices for now; Sprint 4 will wire attribute-name mapping.
            dominant_attrs = []
            if session.preference_vector:
                pref = np.asarray(session.preference_vector, dtype=float)
                if pref.size > 0:
                    top_idxs = np.argsort(np.abs(pref))[-3:][::-1]
                    dominant_attrs = [int(i) for i in top_idxs]
            # IMP-10 / Spec v1.8 §6: 4 new Topic 06 clustering telemetry fields.
            # Read stats set by compute_taste_centroids (called inside convergence path
            # above at line ~646 via compute_taste_centroids, or via compute_mmr_next).
            # We read immediately after card-selection to capture the most recent call;
            # stats are set unconditionally by compute_taste_centroids on every execution.
            _clustering_stats = engine.get_last_clustering_stats() or {}
            event_log.emit_event(
                'confidence_update',
                session=session,
                user=profile,
                confidence=round(float(confidence), 4),
                dominant_attrs=dominant_attrs,
                action=action,  # 'like' or 'dislike' -- Spec v1.2 dislike-bias telemetry
                # Topic 06 fields (Spec v1.8 §6)
                cluster_count_used=_clustering_stats.get('cluster_count_used'),
                silhouette_score=_clustering_stats.get('silhouette_score'),
                soft_relevance_used=_clustering_stats.get('soft_relevance_used', False),
                n_likes_at_decision=_clustering_stats.get('n_likes_at_decision'),
            )

        return Response({
            'accepted': True,
            'session_status': session.status,
            'progress': _progress(session),
            'next_image': next_card,
            'prefetch_image': prefetch_card,
            'prefetch_image_2': prefetch_card_2,
            'is_analysis_completed': False,
            'confidence': confidence,  # float [0,1] or null per spec C-1
        })
