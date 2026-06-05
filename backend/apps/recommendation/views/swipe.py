import logging
import threading

from django.conf import settings
from django.core.cache import cache
from django.utils import timezone
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from ..models import AnalysisSession, SwipeEvent
from .. import engine, event_log
from ._shared import _get_profile, _progress
from ..services.swipe_service import _merge_buffer_into_exposed  # noqa: F401 — re-exported via views/__init__.py
from ..services.swipe_service import (
    handle_bookmark,
    handle_swipe_extend,
    handle_swipe_normal,
    build_swipe_telemetry,
    compute_sync_prefetch,
    handle_question_response,
)

logger = logging.getLogger('apps.recommendation')
RC = settings.RECOMMENDATION


# ── Async telemetry thread ────────────────────────────────────────────────────

def _emit_telemetry_thread(swipe_kwargs, confidence_kwargs):
    """Fire-and-forget: emit swipe + confidence_update events off the hot path.
    Saves ~4 DB round-trips (~1200ms on Neon) from the swipe response time.
    """
    from django.db import connections as _connections
    _connections.close_all()
    try:
        event_log.emit_swipe_event(**swipe_kwargs)
        if confidence_kwargs is not None:
            event_log.emit_event('confidence_update', **confidence_kwargs)
    except Exception as exc:
        logger.warning('Telemetry thread failed: %s', exc)
    finally:
        _connections.close_all()


# ── IMP-8: async prefetch background thread ───────────────────────────────────

def _async_prefetch_thread(
    session_id, cache_round, phase,
    pool_ids_snap, exposed_ids_snap, pool_embeddings_snap,
    like_vectors_snap, initial_batch_snap, current_round_snap,
    question_bias_vector_snap=None,
):
    """IMP-8 (Spec v1.6 §11.1): background thread to compute prefetch cards
    after primary swipe response returns. Result cached for the NEXT swipe's
    primary path. The consumer at the top of swipe handling
    (cache.get('prefetch:{sid}:{round}')) reads what this thread wrote on the
    prior swipe, then hydrates next_card + prefetch_card_2 from the cached IDs
    (PR #134 PERF-PREFETCH-CHAIN).

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
    from django.db import connections as _connections

    _connections.close_all()  # release parent thread's connections; bg thread gets its own
    try:
        # Cache stores IDs only — no card hydration needed in thread.
        # Earlier impl called engine.get_building_card() just to extract
        # canonical_bld_id back; but pf_bid IS canonical_bld_id (compute_mmr_next
        # returns IDs, initial_batch[idx] is an ID, farthest_point_from_pool
        # returns an ID). Removing the DB roundtrips drops thread runtime
        # ~700ms → ~50ms (compute_mmr_next/farthest_point are pure Python),
        # dramatically improving cache hit rate for fast swipers (cache writes
        # before next swipe arrives). Consumer at swipe.py:764 calls
        # engine.get_buildings_by_ids([next, pf, pf2]) in 1 batch RTT anyway.
        pf_bid = None
        pf2_bid = None

        # Compute prefetch_card_id (T+1 swipe's prefetch slot, i.e. round+2 from
        # snapshot perspective). The main thread at T+1 selects next_card =
        # initial_batch[current_round_snap+1]; the cache consumer needs the ID
        # that fills the *prefetch* slot of that same response, which is index +2.
        if phase == 'exploring':
            exposed_set = set(exposed_ids_snap)
            if current_round_snap + 2 < len(initial_batch_snap):
                cand = initial_batch_snap[current_round_snap + 2]
                if cand and cand not in exposed_set:
                    pf_bid = cand
                else:
                    pf_bid = engine.farthest_point_from_pool(pool_ids_snap, exposed_ids_snap, pool_embeddings_snap)
            else:
                pf_bid = engine.farthest_point_from_pool(pool_ids_snap, exposed_ids_snap, pool_embeddings_snap)
        elif phase == 'analyzing':
            pf_bid = engine.compute_mmr_next(
                pool_ids_snap, exposed_ids_snap, pool_embeddings_snap,
                like_vectors_snap, current_round_snap + 2,
                question_bias_vector=question_bias_vector_snap,
            )

        # Compute prefetch_card_2_id (T+1 swipe's prefetch_2 slot, i.e. round+3
        # from snapshot perspective). Skip if pf_bid is None (end-of-stream).
        # Action-card sentinel '__action_card__' is never emitted by compute_mmr_next
        # or initial_batch (both produce real building IDs), so no explicit guard
        # needed — the `if pf_bid` already excludes empty/None.
        if pf_bid:
            temp_exposed = exposed_ids_snap + [pf_bid]
            if phase == 'exploring':
                exposed_set_2 = set(temp_exposed)
                if current_round_snap + 3 < len(initial_batch_snap):
                    cand2 = initial_batch_snap[current_round_snap + 3]
                    if cand2 and cand2 not in exposed_set_2:
                        pf2_bid = cand2
                    else:
                        pf2_bid = engine.farthest_point_from_pool(pool_ids_snap, temp_exposed, pool_embeddings_snap)
                else:
                    pf2_bid = engine.farthest_point_from_pool(pool_ids_snap, temp_exposed, pool_embeddings_snap)
            elif phase == 'analyzing':
                pf2_bid = engine.compute_mmr_next(
                    pool_ids_snap, temp_exposed, pool_embeddings_snap,
                    like_vectors_snap, current_round_snap + 3,
                    question_bias_vector=question_bias_vector_snap,
                )

        result = {
            'prefetch_card_id': pf_bid,
            'prefetch_card_2_id': pf2_bid,
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
        _connections.close_all()  # release bg thread's own connections


# ── Images ────────────────────────────────────────────────────────────────────

class DiverseRandomView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        cards = engine.get_diverse_random(n=10)
        return Response(cards)


class BuildingBatchView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        # Accept either canonical_bld_ids (new) or building_ids (legacy).
        ids = request.data.get('canonical_bld_ids') or request.data.get('building_ids') or []
        if not ids:
            return Response([])
        if not isinstance(ids, list) or len(ids) > 200:
            from rest_framework import status
            return Response(
                {'detail': 'canonical_bld_ids must be a list of at most 200 items'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if not all(isinstance(i, str) and i for i in ids):
            from rest_framework import status
            return Response(
                {'detail': 'canonical_bld_ids elements must be non-empty strings'},
                status=status.HTTP_400_BAD_REQUEST,
            )
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
            from rest_framework import status
            return Response({'detail': 'unauthenticated'}, status=status.HTTP_401_UNAUTHORIZED)
        return handle_bookmark(request, profile, project_id)


# ── Swipe ─────────────────────────────────────────────────────────────────────

class SwipeView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, session_id):
        from rest_framework import status as drf_status

        profile = _get_profile(request)
        if not profile:
            return Response({'detail': 'Profile not found'}, status=drf_status.HTTP_404_NOT_FOUND)

        session = AnalysisSession.objects.filter(session_id=session_id, user=profile).first()
        if not session:
            return Response({'detail': 'Session not found'}, status=drf_status.HTTP_404_NOT_FOUND)
        if session.status == 'completed':
            return Response({'detail': 'Session already completed'}, status=drf_status.HTTP_400_BAD_REQUEST)

        # Accept both 'canonical_bld_id' (new) and 'building_id' (legacy) for one
        # frontend rollout cycle. Treat both identically; pick whichever is set.
        canonical_bld_id = request.data.get('canonical_bld_id') or request.data.get('building_id')
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
            if isinstance(s, str) and 0 < len(s) <= 20
        ][:10]

        extend_requested = bool(request.data.get('extend', False))

        if not extend_requested and not canonical_bld_id:
            return Response({'detail': 'canonical_bld_id is required'}, status=drf_status.HTTP_400_BAD_REQUEST)
        if not extend_requested and action not in ('like', 'dislike'):
            return Response({'detail': 'action must be like or dislike'}, status=drf_status.HTTP_400_BAD_REQUEST)

        # S3 extend-session short-circuit. Extend is NOT a real swipe and must not
        # mutate like/ranking state (no SwipeEvent, no like_vectors, no round bump).
        if extend_requested:
            return handle_swipe_extend(request, profile, session, session_id, client_buffer_ids)

        # Idempotency check -- if already processed, return full payload so FE state machine
        # can read progress/next_image/is_analysis_completed without hitting undefined fields.
        if idempotency_key and SwipeEvent.objects.filter(
            idempotency_key=idempotency_key, session=session
        ).exists():
            logger.info('Duplicate swipe ignored: %s', idempotency_key)
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
            }, status=drf_status.HTTP_200_OK)

        # NORMAL SWIPE PROCESSING
        result = handle_swipe_normal(
            request, profile, session, session_id,
            canonical_bld_id, action, idempotency_key, client_buffer_ids,
        )

        # handle_swipe_normal returns a Response on error paths (duplicate race).
        if isinstance(result, Response):
            return result

        # Unpack transaction result
        session            = result['session']
        next_bid           = result['next_bid']
        saved_pool_ids     = result['saved_pool_ids']
        saved_exposed_ids  = result['saved_exposed_ids']
        saved_like_vectors = result['saved_like_vectors']
        saved_initial_batch = result['saved_initial_batch']
        saved_current_round = result['saved_current_round']
        saved_phase         = result['saved_phase']
        saved_pool_embeddings = result['saved_pool_embeddings']
        saved_recent_actions  = result['saved_recent_actions']
        _embedding_stats      = result['_embedding_stats']
        _pool_escalation_fired = result['_pool_escalation_fired']
        _timing_marks         = result['_timing_marks']
        question_trigger      = result['question_trigger']
        saved_question_bias_vector = result.get('saved_question_bias_vector')

        import time as _time
        _t_start = result['_t_start']

        def _mark(step):
            _timing_marks[step] = round((_time.perf_counter() - _t_start) * 1000, 2)

        # 9. Card fetch + prefetch (outside transaction — no lock held)
        # All building IDs were resolved inside the transaction (step 8).
        # DB fetches are batched here: 3 sequential RTTs → 1 RTT.
        #
        # Paths:
        #   next_bid is None  → converged/exhausted; next_card stays None
        #     (S3: no end-of-stream card — frontend renders end-screen on is_analysis_completed).
        #   async_prefetch_enabled=True  → reads prefetch:{sid}:{round} cache populated
        #     by the previous swipe's background thread (PERF-PREFETCH-CHAIN), hydrates
        #     next_card + prefetch_card_2 from cached IDs, and spawns this swipe's
        #     background thread to populate the cache for the next swipe.
        #   sync (default)  → compute pf_bid + pf2_bid (CPU-only), then
        #     fetch all three IDs in a single get_buildings_by_ids call (1 RTT).
        prefetch_strategy = 'sync'
        next_card = None
        prefetch_card = None
        prefetch_card_2 = None

        if next_bid is None:
            # converged / pool-exhausted — no DB fetch needed; next_card stays None
            pass

        elif settings.RECOMMENDATION.get('async_prefetch_enabled', False):
            # IMP-8 async path (PERF-PREFETCH-CHAIN): consume prior swipe's thread
            # cache write BEFORE spawning this swipe's thread, then batch-fetch
            # next + prefetch + prefetch_2 in a single get_buildings_by_ids RTT.
            #
            # Key algebra:
            #   Prior swipe wrote: prefetch:{sid}:{prior_saved_current_round + 1}
            #   prior_saved_current_round + 1 == current saved_current_round (both = N)
            # So cache.get('prefetch:{sid}:{saved_current_round}') reads the prior write.
            #
            # cache.get before t.start() for readability; thread writes key N+1,
            # consumer reads N — no race on the cache key.
            #
            # Note: exposed_ids_snap passed to the thread DOES include T's next_card
            # (session.exposed_ids already had it added before line 703 snapshot).
            # It does NOT include T+1's not-yet-selected next_card. So on the
            # analyzing path, compute_mmr_next(round=N+2, exposed=exposed_at_T) may
            # return the same card T+1's main thread independently picks as next_bid
            # (via compute_mmr_next(round=N+1, exposed=exposed_at_T+1)). Cache hit
            # would then put the same card in both next_image and prefetch_image.
            # Fixed: dedupe guards below degrade such collisions to None (same as
            # cache miss) before the batch fetch. Frontend never sees a duplicate.
            cached = cache.get(f'prefetch:{session.session_id}:{saved_current_round}')
            pf_id = cached.get('prefetch_card_id') if cached else None
            pf2_id = cached.get('prefetch_card_2_id') if cached else None

            # Dedupe against next_bid + against each other. On the analyzing path,
            # compute_mmr_next can return the same card for T's lookahead (round=N+2,
            # exposed_at_T) as T+1's main pick (round=N+1, exposed_at_T+1) when the
            # inputs are similar (e.g., dislike streak keeps like_vectors stable).
            # Frontend does NOT dedupe (App.jsx:521+536 non-instant-swap path), so
            # duplicate-card-in-prefetch would surface as the user seeing the same
            # building twice. Degrade dupes to None — same as a cache miss.
            if pf_id == next_bid:
                pf_id = None
            if pf2_id and (pf2_id == next_bid or pf2_id == pf_id):
                pf2_id = None

            # Batch-fetch next + prefetch + prefetch_2 in a single DB RTT.
            _async_ids = [bid for bid in [next_bid, pf_id, pf2_id] if bid]
            _async_fetched = {
                c['canonical_bld_id']: c
                for c in engine.get_buildings_by_ids(_async_ids)
            }
            next_card = _async_fetched.get(next_bid)
            prefetch_card = _async_fetched.get(pf_id) if pf_id else None
            prefetch_card_2 = _async_fetched.get(pf2_id) if pf2_id else None

            t = threading.Thread(
                target=_async_prefetch_thread,
                args=(
                    str(session.session_id),
                    saved_current_round + 1,     # cache_round key (writes prefetch:{sid}:{N+1})
                    saved_phase,
                    saved_pool_ids,
                    saved_exposed_ids,
                    saved_pool_embeddings,
                    saved_like_vectors,
                    saved_initial_batch,
                    saved_current_round,
                    saved_question_bias_vector,
                ),
                daemon=True,
            )
            t.start()
            prefetch_strategy = 'async-thread'

        else:
            # ── Phase 1: prefetch ID selection (CPU-only, no DB) ─────────────
            pf_bid, pf2_bid = compute_sync_prefetch(
                saved_phase, saved_exposed_ids, saved_initial_batch, saved_current_round,
                saved_pool_ids, saved_pool_embeddings, saved_like_vectors,
                saved_question_bias_vector=saved_question_bias_vector,
            )

            # ── Phase 2: single batch DB call (1 RTT for next + pf + pf2) ────
            _fetch_ids = [bid for bid in [next_bid, pf_bid, pf2_bid] if bid]
            _fetched = {c['canonical_bld_id']: c for c in engine.get_buildings_by_ids(_fetch_ids)}
            next_card       = _fetched.get(next_bid)
            prefetch_card   = _fetched.get(pf_bid)   if pf_bid   else None
            prefetch_card_2 = _fetched.get(pf2_bid)  if pf2_bid  else None

        _mark('prefetch_done')
        _mark('total')

        # Build telemetry kwargs and fire off background thread.
        # Keeps ~4 Neon DB round-trips (~1200ms) off the response path.
        _swipe_telem, _confidence_telem, confidence, _timing_breakdown, _cache_misses = (
            build_swipe_telemetry(
                request, session, profile,
                action, canonical_bld_id, idempotency_key,
                _embedding_stats, _pool_escalation_fired, _timing_marks, prefetch_strategy,
                saved_recent_actions,
            )
        )

        # §6 logging
        logger.info(
            '[SWIPE TIMING] lock=%dms embed=%dms select=%dms prefetch=%dms total=%dms | phase=%s cache_hit=%s',
            _timing_breakdown['lock_ms'],
            _timing_breakdown['embed_ms'],
            _timing_breakdown['select_ms'],
            _timing_breakdown['prefetch_ms'],
            _timing_breakdown['total_ms'],
            saved_phase,
            _cache_misses == 0,
        )

        threading.Thread(
            target=_emit_telemetry_thread,
            args=(_swipe_telem, _confidence_telem),
            daemon=True,
        ).start()

        return Response({
            'accepted': True,
            'session_status': session.status,
            'progress': _progress(session),
            'next_image': next_card,
            'prefetch_image': prefetch_card,
            'prefetch_image_2': prefetch_card_2,
            'is_analysis_completed': next_card is None and session.phase in ('converged', 'completed'),
            'can_continue': (
                len([pid for pid in session.pool_ids if pid not in set(session.exposed_ids)]) >= 1
                and session.extended_rounds < 5
            ),
            'confidence': confidence,  # float [0,1] or null per spec C-1
            # 'sync' | 'async-thread' (matches telemetry payload). Exposes which
            # prefetch path served the response — useful for client perf debug +
            # required by test_first_swipe_hits_prefetch_cache (PR #145 F4).
            'prefetch_strategy': prefetch_strategy,
            # ALGO-QCARD-1: question card trigger (null or {type, axis, question, option_a, option_b})
            'question_trigger': question_trigger,
        })


# ── Question Response (ALGO-QCARD-1) ─────────────────────────────────────────

class QuestionResponseView(APIView):
    """
    POST /api/v1/analysis/sessions/<uuid:session_id>/question-responses/

    Record the user's answer to a question card (type: refine | refresh).
    Applies soft-vector bias to future recommendations (ALGO-QCARD Phase 1).
    Emits a tag_answer SessionEvent.

    Request body:
        question_type:   "refine" | "refresh"
        axis:            str | null   (axis name for refine; null for refresh)
        keyword:         str | null   (dominant tag echoed from question_trigger)
        selected_option: "A" | "B" | "skip"
            A = Yes (right swipe / agree)
            B = No  (left swipe / disagree)

    Response 200 (skip):
        { "accepted": true, "flush_prefetch": false }

    Response 200 (A or B):
        {
          "accepted": true,
          "flush_prefetch": true,
          "next_image": <ImageCard | null>,
          "prefetch_image": <ImageCard | null>,
          "prefetch_image_2": <ImageCard | null>,
          "progress": { ... }
        }
    """
    permission_classes = [IsAuthenticated]

    def post(self, request, session_id):
        profile = _get_profile(request)
        if not profile:
            from rest_framework import status
            return Response({'detail': 'Profile not found'}, status=status.HTTP_404_NOT_FOUND)
        return handle_question_response(request, profile, session_id)
