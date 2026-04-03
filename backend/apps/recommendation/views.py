import logging
from collections import defaultdict
from django.conf import settings
from django.db import transaction
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Project, AnalysisSession, SwipeEvent
from .serializers import ProjectSerializer
from . import engine, services

logger = logging.getLogger('apps.recommendation')
RC = settings.RECOMMENDATION

# Known filter keys for filter_priority validation
_VALID_FILTER_KEYS = frozenset([
    'program', 'location_country', 'style', 'material',
    'min_area', 'max_area', 'year_min', 'year_max',
])


def _get_profile(request):
    return getattr(request.user, 'profile', None)


def _progress(session):
    like_count    = session.swipes.filter(action='like').count()
    dislike_count = session.swipes.filter(action='dislike').count()
    return {
        'current_round': session.current_round,
        'total_rounds':  session.total_rounds,
        'like_count':    like_count,
        'dislike_count': dislike_count,
        'phase':         session.phase,
        'pool_size':     len(session.pool_ids) if session.pool_ids else 0,
        'pool_remaining': len([pid for pid in (session.pool_ids or []) if pid not in (session.exposed_ids or [])]),
    }


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
    permission_classes = [IsAuthenticated]

    def _get_project(self, request, pk):
        profile = _get_profile(request)
        if not profile:
            return None
        return Project.objects.filter(project_id=pk, user=profile).first()

    def patch(self, request, pk):
        project = self._get_project(request, pk)
        if not project:
            return Response({'detail': 'Not found'}, status=status.HTTP_404_NOT_FOUND)
        serializer = ProjectSerializer(project, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(ProjectSerializer(project).data)

    def delete(self, request, pk):
        project = self._get_project(request, pk)
        if not project:
            return Response({'detail': 'Not found'}, status=status.HTTP_404_NOT_FOUND)
        project.delete()
        logger.info('Project deleted: %s', pk)
        return Response(status=status.HTTP_204_NO_CONTENT)


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

        # Create bounded pool with weighted scoring (with filter relaxation fallback)
        active_filters = filters or project.filters or {}
        pool_ids, pool_scores = engine.create_bounded_pool(
            active_filters, filter_priority, seed_ids
        )
        filter_relaxed = False

        if not pool_ids and active_filters:
            # Relax: drop geographic + numeric constraints, keep program/style/material
            relaxed = {k: v for k, v in active_filters.items()
                       if k not in ('location_country', 'year_min', 'year_max', 'min_area', 'max_area')}
            if relaxed and relaxed != active_filters:
                relaxed_priority = [k for k in filter_priority if k in relaxed]
                pool_ids, pool_scores = engine.create_bounded_pool(
                    relaxed, relaxed_priority, seed_ids
                )
                if pool_ids:
                    filter_relaxed = True
                    logger.info('Session pool relaxed (dropped geo/numeric): %d buildings', len(pool_ids))

        if not pool_ids:
            # Final fallback: diverse random pool
            pool_ids = engine._random_pool(RC['bounded_pool_target'])
            pool_scores = {}
            filter_relaxed = True
            logger.info('Session pool fallback to random: %d buildings', len(pool_ids))

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

        session = AnalysisSession.objects.create(
            user                 = profile,
            project              = project,
            phase                = 'exploring',
            pool_ids             = pool_ids,
            pool_scores          = pool_scores,
            total_rounds         = 999,
            current_round        = 0,
            preference_vector    = [],
            exposed_ids          = [initial_batch[0]],
            initial_batch        = initial_batch,
            like_vectors         = [],
            convergence_history  = [],
            previous_pref_vector = [],
        )

        logger.info('Session created: %s (pool=%d, tiers=%d, relaxed=%s)', session.session_id, len(pool_ids), len(tiers), filter_relaxed)
        return Response({
            'session_id':      str(session.session_id),
            'project_id':      str(project.project_id),
            'session_status':  session.status,
            'total_rounds':    session.total_rounds,
            'next_image':      first_card,
            'prefetch_image':  prefetch_card,
            'progress':        _progress(session),
            'filter_relaxed':  filter_relaxed,
        }, status=status.HTTP_201_CREATED)


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

        if action not in ('like', 'dislike'):
            return Response({'detail': 'action must be like or dislike'}, status=status.HTTP_400_BAD_REQUEST)

        # Idempotency check -- if already processed, return accepted so frontend treats it as success
        if SwipeEvent.objects.filter(idempotency_key=idempotency_key).exists():
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
                return Response({
                    'accepted': True,
                    'session_status': 'completed',
                    'progress': _progress(session),
                    'next_image': None,
                    'prefetch_image': None,
                    'is_analysis_completed': True,
                })
            else:
                # Reset and keep going
                with transaction.atomic():
                    session.convergence_history = []
                    session.previous_pref_vector = []
                    session.phase = 'analyzing'
                    session.save(update_fields=['phase', 'convergence_history', 'previous_pref_vector'])
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

                return Response({
                    'accepted': True,
                    'session_status': session.status,
                    'progress': _progress(session),
                    'next_image': next_card,
                    'prefetch_image': prefetch_card,
                    'is_analysis_completed': False,
                })

        # NORMAL SWIPE PROCESSING
        with transaction.atomic():
            # 1. Get embedding and update preference vector
            embedding = engine.get_building_embedding(building_id)
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
                if building_id not in project.liked_ids:
                    project.liked_ids = project.liked_ids + [building_id]
                # Append to session.like_vectors
                if embedding:
                    session.like_vectors = session.like_vectors + [{'embedding': embedding, 'round': session.current_round}]
            else:
                if building_id not in project.disliked_ids:
                    project.disliked_ids = project.disliked_ids + [building_id]
            project.save(update_fields=['liked_ids', 'disliked_ids'])

            # 4. Increment round
            session.current_round += 1

            # 5. Convergence — use K-Means global centroid during analyzing, pref_vector during exploring
            if session.phase == 'analyzing' and action == 'like' and session.like_vectors:
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
            # On dislike during analyzing: centroids unchanged, skip convergence check

            # 6. Phase transitions
            like_count = len(session.like_vectors)

            if session.phase == 'exploring' and like_count >= RC.get('min_likes_for_clustering', 3):
                session.phase = 'analyzing'
                logger.info('Session %s: exploring -> analyzing (likes=%d)', session.session_id, like_count)

            if session.phase == 'analyzing' and engine.check_convergence(
                session.convergence_history, RC.get('convergence_threshold', 0.08), RC.get('convergence_window', 3)
            ):
                session.phase = 'converged'
                logger.info('Session %s: analyzing -> converged', session.session_id)

            # 7. Check pool exhaustion
            remaining = [pid for pid in session.pool_ids if pid not in set(session.exposed_ids)]
            if not remaining and session.phase not in ('converged', 'completed'):
                session.phase = 'converged'
                logger.info('Session %s: pool exhausted -> converged', session.session_id)

            # 8. Card selection by phase
            pool_embeddings = engine.get_pool_embeddings(session.pool_ids)

            if session.phase == 'converged':
                next_card = engine.build_action_card()
            elif session.phase == 'exploring':
                # Use initial_batch for early rounds, then farthest-point
                if session.current_round < len(session.initial_batch):
                    next_bid = session.initial_batch[session.current_round]
                    next_card = engine.get_building_card(next_bid)
                else:
                    # Check for consecutive dislikes
                    recent_swipes = list(session.swipes.order_by('-created_at').values_list('action', flat=True)[:RC.get('max_consecutive_dislikes', 10)])
                    consecutive_dislikes = 0
                    for s in recent_swipes:
                        if s == 'dislike':
                            consecutive_dislikes += 1
                        else:
                            break

                    if consecutive_dislikes >= RC.get('max_consecutive_dislikes', 10):
                        # Get dislike vectors from project
                        dislike_embeds = []
                        for did in project.disliked_ids[-10:]:
                            emb = engine.get_building_embedding(did)
                            if emb:
                                dislike_embeds.append(emb)
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

            # 9. Prefetch (same phase logic, round+1)
            prefetch_card = None
            if next_card and next_card.get('building_id') != '__action_card__':
                try:
                    if session.phase == 'exploring':
                        if session.current_round + 1 < len(session.initial_batch):
                            pf_bid = session.initial_batch[session.current_round + 1]
                            prefetch_card = engine.get_building_card(pf_bid)
                        else:
                            pf_bid = engine.farthest_point_from_pool(session.pool_ids, session.exposed_ids, pool_embeddings)
                            prefetch_card = engine.get_building_card(pf_bid) if pf_bid else None
                    elif session.phase == 'analyzing':
                        pf_id = engine.compute_mmr_next(
                            session.pool_ids, session.exposed_ids, pool_embeddings,
                            session.like_vectors, session.current_round + 1
                        )
                        prefetch_card = engine.get_building_card(pf_id) if pf_id else None
                except Exception:
                    prefetch_card = None

            # 10. Save session
            session.save(update_fields=[
                'preference_vector', 'current_round', 'exposed_ids',
                'phase', 'like_vectors', 'convergence_history', 'previous_pref_vector'
            ])

        return Response({
            'accepted': True,
            'session_status': session.status,
            'progress': _progress(session),
            'next_image': next_card,
            'prefetch_image': prefetch_card,
            'is_analysis_completed': False,
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

        if not project.liked_ids:
            return Response({'detail': 'No liked buildings yet'}, status=status.HTTP_400_BAD_REQUEST)

        report = services.generate_persona_report(project.liked_ids)
        if not report:
            return Response({'detail': 'Report generation failed'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        project.final_report = report
        project.save(update_fields=['final_report'])
        logger.info('Persona report generated for project %s', pk)
        return Response({'final_report': report})


# ── LLM Query Parsing ─────────────────────────────────────────────────────────

class ParseQueryView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        query = request.data.get('query', '').strip()
        if not query:
            return Response({'detail': 'query is required'}, status=status.HTTP_400_BAD_REQUEST)

        parsed  = services.parse_query(query)
        filters = {k: v for k, v in parsed['filters'].items() if v is not None}
        results = engine.search_by_filters(filters, limit=20) if filters else []

        is_fallback   = False
        fallback_note = ''

        if not results:
            # Relax: drop geographic + numeric constraints, keep program/mood/material
            relaxed = {k: v for k, v in filters.items()
                       if k not in ('location_country', 'year_min', 'year_max', 'min_area', 'max_area')}
            if relaxed and relaxed != filters:
                results = engine.search_by_filters(relaxed, limit=20)
                if results:
                    is_fallback   = True
                    fallback_note = "No exact matches for those criteria \u2014 here are similar buildings you might like."

        if not results:
            # Final fallback: diverse random
            results       = engine.get_diverse_random(n=20)
            is_fallback   = True
            fallback_note = "Couldn\u2019t find an exact match \u2014 here are some buildings you might enjoy instead."

        return Response({
            'reply':              parsed['reply'],
            'structured_filters': parsed['filters'],
            'filter_priority':    parsed.get('filter_priority', []),
            'suggestions':        [],
            'results':            results,
            'is_fallback':        is_fallback,
            'fallback_note':      fallback_note,
        })
