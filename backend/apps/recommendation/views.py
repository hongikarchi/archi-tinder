import hashlib
import logging
import math
import threading
import numpy as np
from collections import defaultdict
from django.conf import settings
from django.core.cache import cache
from django.core.exceptions import ValidationError
from django.db import transaction
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import AnonRateThrottle, UserRateThrottle
from rest_framework.views import APIView

from .models import Project, AnalysisSession, SwipeEvent, SessionEvent
from .serializers import ProjectSerializer, ProjectSelfUpdateSerializer
from . import engine, event_log, services

logger = logging.getLogger('apps.recommendation')
RC = settings.RECOMMENDATION

# Known filter keys for filter_priority validation
_VALID_FILTER_KEYS = frozenset([
    'program', 'location_country', 'style', 'material',
    'min_area', 'max_area', 'year_min', 'year_max',
])


def _liked_id_only(liked_ids):
    """Extract building_id strings from liked_ids regardless of legacy/new shape.

    Returns list[str]. Accepts both list[str] (legacy) and list[{id, intensity}] (new).
    Use this whenever passing liked_ids to a function that expects plain ID strings
    (e.g., SQL ``WHERE building_id IN (...)``, Gemini persona report).
    """
    return [
        entry if isinstance(entry, str) else entry['id']
        for entry in (liked_ids or [])
        if isinstance(entry, str) or (isinstance(entry, dict) and 'id' in entry)
    ]


def _get_profile(request):
    return getattr(request.user, 'profile', None)


def _progress(session):
    like_count    = session.swipes.filter(action='like').count()
    dislike_count = session.swipes.filter(action='dislike').count()
    return {
        'current_round': session.current_round,
        'like_count':    like_count,
        'dislike_count': dislike_count,
        'phase':         session.phase,
        'pool_size':     len(session.pool_ids) if session.pool_ids else 0,
        'pool_remaining': len([pid for pid in (session.pool_ids or []) if pid not in (session.exposed_ids or [])]),
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


# ── Projects ──────────────────────────────────────────────────────────────────

class ProjectListCreateView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        profile = _get_profile(request)
        if not profile:
            return Response({'results': [], 'total': 0, 'has_more': False})
        try:
            page      = max(1, int(request.query_params.get('page', 1)))
            page_size = min(max(1, int(request.query_params.get('page_size', 50))), 50)
        except (ValueError, TypeError):
            page, page_size = 1, 50
        qs     = Project.objects.filter(user=profile).order_by('-created_at')
        total  = qs.count()
        start  = (page - 1) * page_size
        chunk  = qs[start:start + page_size]
        return Response({
            'results':  ProjectSerializer(chunk, many=True).data,
            'total':    total,
            'page':     page,
            'has_more': (page * page_size) < total,
        })

    def post(self, request):
        profile = _get_profile(request)
        if not profile:
            return Response({'detail': 'Profile not found'}, status=status.HTTP_404_NOT_FOUND)
        serializer = ProjectSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        project = serializer.save(user=profile)
        logger.info('Project created: %s by user %s', project.project_id, profile.pk)
        return Response(ProjectSerializer(project).data, status=status.HTTP_201_CREATED)


class ProjectDetailView(APIView):
    """GET/PATCH/DELETE /api/v1/projects/{project_id}/ — BOARD1 Phase 13.

    GET:   AllowAny — returns 200 for own or public; 403 for private non-owner.
    PATCH: owner-only — name + visibility only (ProjectSelfUpdateSerializer).
    DELETE: owner-only — cascade rules TBD (Phase 15); plain delete for now.
    """
    permission_classes = [AllowAny]

    def get(self, request, pk):
        project = get_object_or_404(Project.objects.select_related('user__user'), project_id=pk)
        profile = _get_profile(request)
        is_owner = profile and project.user_id == profile.pk
        if not is_owner and project.visibility != 'public':
            return Response({'detail': 'Forbidden'}, status=status.HTTP_403_FORBIDDEN)
        data = ProjectSerializer(project).data
        if request.user.is_authenticated and profile:
            from apps.social.models import Reaction
            data['is_reacted'] = Reaction.objects.filter(user=profile, project=project).exists()
        else:
            data['is_reacted'] = False
        return Response(data)

    def patch(self, request, pk):
        profile = _get_profile(request)
        if not profile:
            return Response({'detail': 'Authentication required'}, status=status.HTTP_401_UNAUTHORIZED)
        project = get_object_or_404(Project, project_id=pk)
        if project.user_id != profile.pk:
            return Response({'detail': 'Forbidden'}, status=status.HTTP_403_FORBIDDEN)
        serializer = ProjectSelfUpdateSerializer(project, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        project.refresh_from_db()  # updated_at is auto_now=True (DB-set); refresh to avoid stale in-memory value
        return Response(ProjectSerializer(project).data)

    def delete(self, request, pk):
        profile = _get_profile(request)
        if not profile:
            return Response({'detail': 'Authentication required'}, status=status.HTTP_401_UNAUTHORIZED)
        project = get_object_or_404(Project, project_id=pk)
        if project.user_id != profile.pk:
            return Response({'detail': 'Forbidden'}, status=status.HTTP_403_FORBIDDEN)
        project.delete()
        logger.info('Project deleted: %s', pk)
        return Response(status=status.HTTP_204_NO_CONTENT)


class UserProjectsListView(APIView):
    """GET /api/v1/users/{user_id}/projects/ — BOARD1 Phase 13.

    Non-owner: public projects only.
    Owner: public + private.
    """
    permission_classes = [AllowAny]

    def get(self, request, user_id):
        from apps.accounts.models import UserProfile
        target_profile = get_object_or_404(UserProfile, user__id=user_id)
        requester_profile = _get_profile(request)
        is_owner = requester_profile and requester_profile.pk == target_profile.pk
        try:
            page      = max(1, int(request.query_params.get('page', 1)))
            page_size = min(max(1, int(request.query_params.get('page_size', 50))), 50)
        except (ValueError, TypeError):
            page, page_size = 1, 50
        qs = Project.objects.filter(user=target_profile).select_related('user__user').order_by('-created_at')
        if not is_owner:
            qs = qs.filter(visibility='public')
        total = qs.count()
        start = (page - 1) * page_size
        chunk = list(qs[start:start + page_size])
        return Response({
            'results':  ProjectSerializer(chunk, many=True).data,
            'total':    total,
            'page':     page,
            'has_more': (page * page_size) < total,
        })


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


# ── Reports ───────────────────────────────────────────────────────────────────

class ProjectReportGenerateView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        profile = _get_profile(request)
        project = Project.objects.filter(project_id=pk, user=profile).first() if profile else None
        if not project:
            return Response({'detail': 'Not found'}, status=status.HTTP_404_NOT_FOUND)

        liked_id_strings = _liked_id_only(project.liked_ids)
        if not liked_id_strings:
            return Response({'detail': 'No liked buildings yet'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            report = services.generate_persona_report(liked_id_strings)
        except (ValueError, RuntimeError) as e:
            return Response(
                {'detail': str(e), 'error_type': type(e).__name__},
                status=status.HTTP_502_BAD_GATEWAY,
            )

        if not report:
            return Response(
                {'detail': 'No building data found for report generation'},
                status=status.HTTP_404_NOT_FOUND,
            )

        project.final_report = report
        project.save(update_fields=['final_report'])
        logger.info('Persona report generated for project %s', pk)
        return Response({'final_report': report})


class ProjectReportImageView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        profile = _get_profile(request)
        project = Project.objects.filter(project_id=pk, user=profile).first() if profile else None
        if not project:
            return Response({'detail': 'Not found'}, status=status.HTTP_404_NOT_FOUND)

        if not project.final_report:
            return Response({'detail': 'Generate persona report first'}, status=status.HTTP_400_BAD_REQUEST)

        result = services.generate_persona_image(project.final_report)
        if not result:
            return Response({'detail': 'Image generation failed. The Imagen API may not be enabled for your API key.'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        project.report_image = result['image_data']
        project.save(update_fields=['report_image'])
        logger.info('Persona image generated for project %s', pk)
        return Response({
            'image_data': result['image_data'],
            'mime_type': result['mime_type'],
            'prompt': result['prompt'],
        })


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


# ── IMP-6 Commit 2: Stage 2 background thread spawn helper ───────────────────

def _spawn_stage2(filters, raw_query, user_id):
    """IMP-6 Commit 2: Spawn background thread for Stage 2 visual_description generation.

    Per Investigation 17 §3a + Inv 23 §3: runs OFF the user-blocking critical path.
    User reads Stage 1 rich-paraphrase confirmation while this generates
    visual_description -> V_initial -> caches it for SessionCreate's late-bind read.

    Threading design:
    - daemon=True: prevents process-exit deadlock if thread outlives server process
    - fire-and-forget (no join): caller returns Stage 1 response immediately
    - connection.close() in finally: releases Django DB connection at thread exit
      (each thread gets its own connection; must be explicitly released to avoid leak)
    - All exceptions caught: Stage 2 failure is silent; SessionCreate falls through
      to filter-only pool (graceful degrade per spec v1.5 Topic 01)
    """
    from django.db import connection as _db_conn

    def _run():
        try:
            services.generate_visual_description(filters, raw_query, user_id)
        except Exception as exc:
            logger.warning('IMP-6 Stage 2 thread uncaught exception: %s', exc)
        finally:
            # Release DB connection at thread exit (Django thread-local conn pool)
            _db_conn.close()

    t = threading.Thread(target=_run, daemon=True)
    t.start()
    # Do NOT join -- fire-and-forget; caller returns Stage 1 immediately.


# ── LLM Query Parsing ─────────────────────────────────────────────────────────

class ParseQueryView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        # Accept BOTH legacy `query` string AND new `conversation_history` list.
        # If conversation_history provided: pass directly to parse_query.
        # If only query: wrap as single-turn history for parse_query.
        conversation_history = request.data.get('conversation_history')
        query_str = request.data.get('query', '')
        if isinstance(query_str, str):
            query_str = query_str.strip()

        if conversation_history is not None:
            # New multi-turn path: validate it is a list
            if not isinstance(conversation_history, list) or len(conversation_history) == 0:
                return Response(
                    {'detail': 'conversation_history must be a non-empty list'},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            # Security: cap history depth to prevent Gemini cost amplification DoS
            _MAX_HISTORY_LEN = 10
            _MAX_TEXT_LEN = 2000
            _ALLOWED_ROLES = {'user', 'model'}
            if len(conversation_history) > _MAX_HISTORY_LEN:
                return Response(
                    {'detail': f'conversation_history too long (max {_MAX_HISTORY_LEN})'},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            for entry in conversation_history:
                if not isinstance(entry, dict):
                    return Response(
                        {'detail': 'conversation_history items must be {role, text} dicts'},
                        status=status.HTTP_400_BAD_REQUEST,
                    )
                role = entry.get('role', 'user')
                if role not in _ALLOWED_ROLES:
                    return Response(
                        {'detail': f'invalid role; must be one of {sorted(_ALLOWED_ROLES)}'},
                        status=status.HTTP_400_BAD_REQUEST,
                    )
                text = entry.get('text', '')
                if not isinstance(text, str) or len(text) > _MAX_TEXT_LEN:
                    return Response(
                        {'detail': f'conversation_history.text too long (max {_MAX_TEXT_LEN} chars)'},
                        status=status.HTTP_400_BAD_REQUEST,
                    )
        elif query_str:
            # Legacy single-string path: wrap as single-turn history
            conversation_history = [{'role': 'user', 'text': query_str}]
        else:
            return Response(
                {'detail': 'query or conversation_history is required'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        parsed = services.parse_query(conversation_history)

        # When probe_needed=True: return probe payload immediately without
        # touching the search engine. Frontend renders the probe question.
        if parsed.get('probe_needed'):
            return Response({
                'probe_needed': True,
                'probe_question': parsed.get('probe_question'),
                'reply': parsed.get('reply', ''),
                'raw_query': parsed.get('raw_query', ''),
                'structured_filters': parsed.get('filters', {}),
                'filter_priority': parsed.get('filter_priority', []),
                'visual_description': parsed.get('visual_description'),
                'suggestions': [],
                'results': [],
                'is_fallback': False,
                'fallback_note': '',
            })

        # IMP-6 Commit 2: spawn Stage 2 thread on terminal turn (probe_needed=False)
        # Stage 2 generates visual_description -> V_initial -> caches for SessionCreate.
        # Only fires when stage_decouple_enabled=True (default OFF).
        # Clarification turns (probe_needed=True) are excluded above so we never reach
        # this point with an unstable filter set.
        if RC.get('stage_decouple_enabled', False):
            _spawn_stage2(
                filters=parsed.get('filters') or {},
                raw_query=parsed.get('raw_query', ''),
                user_id=request.user.id,
            )

        # Terminal path (probe_needed=False): run search engine.
        filters = {k: v for k, v in (parsed.get('filters') or {}).items() if v is not None}
        results = engine.search_by_filters(filters, limit=20) if filters else []

        is_fallback = False
        fallback_note = ''

        if not results:
            # Relax: drop geographic + numeric constraints, keep program/mood/material
            relaxed = {k: v for k, v in filters.items()
                       if k not in ('location_country', 'year_min', 'year_max', 'min_area', 'max_area')}
            if relaxed and relaxed != filters:
                results = engine.search_by_filters(relaxed, limit=20)
                if results:
                    is_fallback = True
                    fallback_note = "No exact matches for those criteria \u2014 here are similar buildings you might like."

        if not results:
            # Final fallback: diverse random
            results = engine.get_diverse_random(n=20)
            is_fallback = True
            fallback_note = "Couldn\u2019t find an exact match \u2014 here are some buildings you might enjoy instead."

        return Response({
            'probe_needed': False,
            'probe_question': None,
            'reply': parsed.get('reply', ''),
            'raw_query': parsed.get('raw_query', ''),
            'visual_description': parsed.get('visual_description'),
            'structured_filters': parsed.get('filters', {}),
            'filter_priority': parsed.get('filter_priority', []),
            'suggestions': [],
            'results': results,
            'is_fallback': is_fallback,
            'fallback_note': fallback_note,
        })


# ── Telemetry ─────────────────────────────────────────────────────────────────

class ImageLoadTelemetryThrottle(AnonRateThrottle):
    """Scoped anon throttle for the image-load telemetry endpoint.

    Uses the 'image_load_telemetry' scope defined in REST_FRAMEWORK DEFAULT_THROTTLE_RATES
    (120/min). Applied alongside UserRateThrottle so authenticated users are capped too.
    """
    scope = 'image_load_telemetry'


class ImageLoadTelemetryView(APIView):
    """POST /api/v1/telemetry/image-load/ — frontend image load success/failure beacon.

    Accepts anonymous requests (broken images can happen to unauthenticated users too).
    Records a SessionEvent with event_type='image_load' for observability.
    """
    permission_classes = [AllowAny]
    throttle_classes = [ImageLoadTelemetryThrottle, UserRateThrottle]

    def post(self, request):
        from urllib.parse import urlparse
        data = request.data

        url = data.get('url', '')
        outcome = data.get('outcome', '')
        if outcome not in ('success', 'failure', 'timeout'):
            return Response({'detail': 'invalid outcome'}, status=status.HTTP_400_BAD_REQUEST)
        if not url or len(url) > 2048:
            return Response({'detail': 'invalid url'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            domain = urlparse(url).netloc or 'unknown'
        except Exception:
            domain = 'unknown'

        profile = _get_profile(request) if request.user.is_authenticated else None

        # Fix 3: filter session by user to prevent cross-user session injection.
        # Anonymous users (profile=None) never get session linkage.
        session_id = data.get('session_id')
        session = None
        if session_id and profile:
            try:
                session = AnalysisSession.objects.filter(
                    session_id=session_id, user=profile,
                ).first()
            except (ValueError, ValidationError):
                session = None

        # Fix 4: guard against NaN, Infinity, negative, and implausibly large values.
        # bool is a subclass of int in Python; reject it explicitly to avoid True->1.
        raw_ms = data.get('load_ms')
        if (
            isinstance(raw_ms, (int, float))
            and not isinstance(raw_ms, bool)
            and math.isfinite(raw_ms)
            and 0 <= raw_ms <= 60_000
        ):
            load_ms = int(raw_ms)
        else:
            load_ms = None

        SessionEvent.objects.create(
            user=profile,
            session=session,
            event_type='image_load',
            payload={
                'url': url[:2048],
                'outcome': outcome,
                'domain': domain[:128],
                'building_id': str(data.get('building_id', ''))[:32] or None,
                'context': str(data.get('context', ''))[:32] or None,
                'load_ms': load_ms,
            },
        )
        return Response({'ok': True}, status=status.HTTP_201_CREATED)
