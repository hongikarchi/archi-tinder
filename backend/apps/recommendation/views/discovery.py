"""
views/discovery.py — Discovery tab v3.2 endpoints.

GET  /api/v1/discovery/                    — 10-card chunk (Tier-aware FPS + interleave)
POST /api/v1/discovery/feedback/           — record like/pass into a draft Project
POST /api/v1/discovery/promote-to-taste/  — promote draft likes into a pre-seeded Taste session

v3.2 changes vs v3.1:
  - Draft boards are per-session timestamped (name = 'discovery_YYMMDD_HHMM').
  - feedback/ accepts optional draft_id; returns draft_id in response.
  - promote-to-taste/ accepts optional draft_id; falls back to most-recent draft.
  - Draft boards are visible on the user's profile (normal boards).

BoardSurpriseView is preserved unchanged from v3.0 (endpoint stays, UX modal
removal is a separate frontend task).
"""
import logging
import re

from collections import defaultdict

from django.conf import settings
from django.core.cache import cache
from django.db import connections as _dj_connections
from django.db import transaction
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from ..models import Project, AnalysisSession
from .. import engine
from ..caches import (
    get_or_build_taste,
    get_or_build_discovery_centroids,
    evict_projects_list,
    evict_user_profile_detail,
    evict_project_detail,
)
from ..discovery_feed import (
    DISCOVERY_DRAFT_PREFIX,
    create_discovery_draft,
    get_discovery_draft,
    compute_discovery_tier,
    build_discovery_chunk,
    _liked_id_only as _draft_liked_id_only,
)
from ._shared import _get_profile, _liked_id_only, _progress

logger = logging.getLogger('apps.recommendation')

RC = settings.RECOMMENDATION

# Building-ID validation constants (mirrors LikedBuildingsView in profile.py)
_BLD_ID_MAX_LEN = 20
_BLD_ID_RE = re.compile(r'^bld_\d{6}$')

# Rolling cap for draft liked/disliked lists (prevents unbounded JSON growth).
# _DRAFT_DISLIKE_CAP must be >= discovery_dislike_history_window (30) so the
# rolling centroid window in build_discovery_chunk is unaffected.
_DRAFT_LIKE_CAP = 200
_DRAFT_DISLIKE_CAP = 200


# ── Tier → taste_state label ──────────────────────────────────────────────────

_TIER_TO_TASTE_STATE = {1: 'cold', 2: 'single', 3: 'multi'}


# ── DiscoveryFeedView (v3.2) ──────────────────────────────────────────────────

class DiscoveryFeedView(APIView):
    """
    GET /api/v1/discovery/?buffer=id1,id2,...

    Returns a fresh 10-card chunk built with:
      - 3-Tier ratio (cold 0/10 · single 2/8 · multi 4/6)
      - Greedy FPS diversity within each pool
      - Dislike-zone exclusion (rolling recent-N pass centroid, all projects)
      - Micro-interleave [G,L,G,G,L,G,L,G,G,L] pattern

    Query param `buffer`: comma-separated canonical_bld_ids the client already
    holds in its deck — added to the exclude set so we never re-issue them.

    Response:
      {cards: [...10], tier: 1|2|3, taste_state: 'cold'|'single'|'multi'}

    No cursor/offset pagination — the client calls again with its updated buffer
    to fetch the next chunk.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        profile = _get_profile(request)
        if profile is None:
            return Response(
                {'detail': 'unauthenticated'},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        # Parse optional buffer param — validate each id and cap total length.
        buffer_param = request.query_params.get('buffer', '')
        chunk_size = RC.get('discovery_chunk_size', 10)
        _buffer_cap = chunk_size * 3  # =30; ignore anything beyond this

        if buffer_param:
            raw_ids = [bid.strip() for bid in buffer_param.split(',') if bid.strip()]
            # Silently drop any item that doesn't match the canonical bld_id format
            # (mirrors _BLD_ID_RE + _BLD_ID_MAX_LEN used in DiscoveryFeedbackView).
            client_buffer_ids = [
                bid for bid in raw_ids
                if len(bid) <= _BLD_ID_MAX_LEN and _BLD_ID_RE.match(bid)
            ][:_buffer_cap]
        else:
            client_buffer_ids = []

        # App-open centroid (lazy cache; in-session fixed — not evicted on likes)
        centroids = get_or_build_discovery_centroids(profile)

        # Tier
        tier_info = compute_discovery_tier(profile)
        tier = tier_info['tier']
        taste_state = _TIER_TO_TASTE_STATE.get(tier, 'cold')

        # Build chunk
        cards = build_discovery_chunk(
            profile, centroids,
            client_buffer_ids=client_buffer_ids,
            chunk_size=chunk_size,
        )

        return Response({
            'cards': cards,
            'tier': tier,
            'taste_state': taste_state,
        })


# ── DiscoveryFeedbackView (v3.2) ──────────────────────────────────────────────

class DiscoveryFeedbackView(APIView):
    """
    POST /api/v1/discovery/feedback/

    Record a Discovery swipe action into a draft Project.

    Body:
      {
        "canonical_bld_id": "bld_000123",
        "action": "like" | "pass",
        "draft_id": "<uuid>"   (optional)
      }

    Draft resolution:
      - draft_id given + resolves to a valid discovery draft → use it.
      - draft_id given but invalid / wrong owner / not a draft → create new draft.
      - draft_id omitted → create new draft.

    "like" → append {id, intensity:1.0} to draft.liked_ids (deduped by id).
    "pass" → append id to draft.disliked_ids (deduped; preserves order; rolling
             dislike_history for centroid computation).

    Response:
      { "draft_id": "<uuid>", "draft_like_count": N, "draft_pass_count": N }
    """
    permission_classes = [IsAuthenticated]

    def post(self, request):
        profile = _get_profile(request)
        if profile is None:
            return Response(
                {'detail': 'unauthenticated'},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        bld_id = request.data.get('canonical_bld_id', '')
        action = request.data.get('action', '')
        draft_id = request.data.get('draft_id', None)

        # Validate canonical_bld_id
        if not bld_id or not isinstance(bld_id, str):
            return Response(
                {'detail': 'canonical_bld_id required'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        bld_id = bld_id.strip()
        if not bld_id:
            return Response(
                {'detail': 'canonical_bld_id required'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if len(bld_id) > _BLD_ID_MAX_LEN:
            return Response(
                {'detail': 'canonical_bld_id too long'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if not _BLD_ID_RE.match(bld_id):
            return Response(
                {'detail': 'invalid canonical_bld_id format'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Validate action
        if action not in ('like', 'pass'):
            return Response(
                {'detail': 'action must be "like" or "pass"'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Verify building exists and is publishable (raw SQL on buildings DB)
        with _dj_connections['buildings'].cursor() as cur:
            cur.execute(
                'SELECT 1 FROM canonical_v2_buildings'
                ' WHERE canonical_bld_id = %s AND is_publishable = true',
                [bld_id],
            )
            if not cur.fetchone():
                return Response(
                    {'detail': 'building not found'},
                    status=status.HTTP_404_NOT_FOUND,
                )

        # Resolve draft: use given draft_id if valid, otherwise create new board.
        draft = None
        if draft_id:
            draft = get_discovery_draft(profile, draft_id)
        if draft is None:
            # missing OR invalid/malformed draft_id -> graceful new draft (author intent),
            # but enforce the guest board-limit so guests can't bypass the 3-board cap.
            if profile.is_guest and Project.objects.filter(user=profile).count() >= 3:
                return Response(
                    {'detail': 'verify_required', 'reason': 'board_limit_reached', 'limit': 3},
                    status=status.HTTP_403_FORBIDDEN,
                )
            draft = create_discovery_draft(profile)

        HARD_CAP = RC.get('discovery_like_hard_cap', 50)
        if action == 'like':
            liked = list(draft.liked_ids or [])
            existing_ids = {
                (e if isinstance(e, str) else e.get('id', ''))
                for e in liked
            }
            # Hard cap: do not record a NEW like once the draft is at the cap.
            # (Re-liking an already-liked id is a no-op and stays allowed.)
            if bld_id not in existing_ids and len(liked) < HARD_CAP:
                liked.append({'id': bld_id, 'intensity': 1.0})
            draft.liked_ids = liked[-_DRAFT_LIKE_CAP:]
            draft.save(update_fields=['liked_ids', 'updated_at'])
        else:  # pass  (UNCHANGED)
            disliked = list(draft.disliked_ids or [])
            if bld_id not in disliked:
                disliked.append(bld_id)
            draft.disliked_ids = disliked[-_DRAFT_DISLIKE_CAP:]
            draft.save(update_fields=['disliked_ids', 'updated_at'])

        # Evict caches so the profile reflects the new/updated board in real-time.
        evict_projects_list(profile.id)
        evict_user_profile_detail(profile.user.id)
        evict_project_detail(str(draft.project_id))

        like_cap_reached = len(draft.liked_ids or []) >= HARD_CAP
        return Response({
            'draft_id': str(draft.project_id),
            'draft_like_count': len(draft.liked_ids or []),
            'draft_pass_count': len(draft.disliked_ids or []),
            'like_cap_reached': like_cap_reached,
        })


# ── DiscoveryPromoteView (v3.2) ───────────────────────────────────────────────

class DiscoveryPromoteView(APIView):
    """
    POST /api/v1/discovery/promote-to-taste/

    Promote a Discovery draft board's likes into a pre-seeded Taste
    AnalysisSession so the K-Means/MMR engine starts already warm.

    Body:
      { "draft_id": "<uuid>"  (optional) }

    Draft resolution:
      - draft_id given + resolves to a valid discovery draft → use it.
      - draft_id omitted or invalid → use the most-recent draft board
        (name startswith 'discovery_', ordered by updated_at desc).
      - No draft exists, or fewer than discovery_promote_threshold (10)
        likes → 400 not_enough_likes.

    Takes ALL liked building ids from the resolved draft (10 is now the
    minimum required, not a cap), fetches their embeddings, and creates a new
    Project + AnalysisSession with:
      - like_vectors pre-seeded from ALL draft likes, each injected at round=0
        (equal recency weight — no decay gradient across the Discovery batch)
      - preference_vector folded from each seed embedding
      - phase = 'analyzing' when seed count >= min_likes_for_clustering, else 'exploring'
      - multimodal_floor = RC['k_clusters'] so K-Means multi-centroid runs immediately
      - pool built via create_pool_with_relaxation(seed_ids=liked_ids)
      - exposed_ids = seed liked ids (already seen in Discovery)
      - first cards selected via centroid MMR (not farthest-point) when analyzing

    Response shape matches POST /api/v1/analysis/sessions/ so the frontend's
    existing applySessionResponse works unchanged:
      { session_id, project_id, session_status,
        next_image, prefetch_image, prefetch_image_2,
        progress, filter_relaxed }

    Errors:
      400 { detail: 'not_enough_likes' } — fewer than 10 draft likes
      403 { detail: 'verify_required', reason: 'board_limit_reached' }
          — guest at the 3-board cap
    """
    permission_classes = [IsAuthenticated]

    def post(self, request):
        profile = _get_profile(request)
        if profile is None:
            return Response(
                {'detail': 'unauthenticated'},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        draft_id = request.data.get('draft_id', None)

        # ── 1. Resolve the draft board ─────────────────────────────────────
        draft = None
        if draft_id:
            draft = get_discovery_draft(profile, draft_id)

        if draft is None:
            # Fall back to the most-recently updated draft board for this user.
            draft = (
                Project.objects
                .filter(user=profile, name__startswith=DISCOVERY_DRAFT_PREFIX)
                .order_by('-updated_at')
                .first()
            )

        promote_threshold = RC.get('discovery_promote_threshold', 10)
        min_likes = RC.get('min_likes_for_clustering', 4)
        multimodal_floor = RC.get('k_clusters', 2)   # need >= k points to form k centroids

        # Take ALL draft likes (promote_threshold is now a minimum gate, not a cap).
        # Dedupe preserving order so identical building ids are not double-counted.
        all_liked = list(draft.liked_ids or []) if draft else []
        _seed_ids_raw = _draft_liked_id_only(all_liked)
        seen_seed = set()
        seed_ids = []
        for _sid in _seed_ids_raw:
            if _sid not in seen_seed:
                seen_seed.add(_sid)
                seed_ids.append(_sid)

        if len(seed_ids) < promote_threshold:
            return Response(
                {'detail': 'not_enough_likes'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Guest board-limit gate: promote creates a NEW non-draft Project while
        # the draft board persists → net +1 board.  Mirror the raw count used by
        # POST /api/v1/projects/ and DiscoveryFeedbackView (drafts included in
        # total — consistent with the resource cap policy, not the tier logic
        # which excludes discovery_ prefix boards for algorithm purposes).
        if profile.is_guest and Project.objects.filter(user=profile).count() >= 3:
            return Response(
                {'detail': 'verify_required', 'reason': 'board_limit_reached', 'limit': 3},
                status=status.HTTP_403_FORBIDDEN,
            )

        # ── 2. Fetch seed embeddings ───────────────────────────────────────
        pool_embeddings_seed = engine.get_pool_embeddings(seed_ids)

        # Build like_vectors and preference_vector from seed embeddings.
        # All seeds use round=0 so they share identical recency weight — no decay
        # gradient is introduced across the contemporaneous Discovery batch.
        like_vectors = []
        pref_vector = []
        for bid in seed_ids:
            emb = pool_embeddings_seed.get(bid)
            if emb is None:
                continue
            emb_list = emb.tolist() if hasattr(emb, 'tolist') else list(emb)
            like_vectors.append({'embedding': emb_list, 'round': 0})
            pref_vector = engine.update_preference_vector(pref_vector, emb_list, 'like')

        # Determine phase based on how many seeds were successfully embedded.
        # session_floor activates multi-centroid K-Means immediately for analyzing sessions.
        seeded_count = len(like_vectors)
        phase = 'analyzing' if seeded_count >= min_likes else 'exploring'
        session_floor = multimodal_floor if phase == 'analyzing' else None

        # ── 3. Build the pool (seed_ids steer the pool toward the user's taste) ──
        pool_ids, pool_scores, current_pool_tier = engine.create_pool_with_relaxation(
            {}, [], seed_ids,
            v_initial=pref_vector if pref_vector else None,
        )

        if not pool_ids:
            return Response(
                {'detail': 'No buildings match your criteria'},
                status=status.HTTP_404_NOT_FOUND,
            )

        # ── 4. Get pool embeddings for initial-batch selection ─────────────
        pool_embeddings = engine.get_pool_embeddings(pool_ids)

        # Seed likes count as already-exposed; exclude them from pool serving
        exposed_ids = [bid for bid in seed_ids if bid in set(pool_ids)]

        # Build served (first 3 cards): centroid MMR for analyzing, farthest-point fallback
        current_round = seeded_count   # for MMR round_num / recency
        served = []
        if phase == 'analyzing' and like_vectors:
            temp_exposed = list(exposed_ids)
            for _ in range(3):   # next_image + 2 prefetch
                bid = engine.compute_mmr_next(
                    pool_ids, temp_exposed, pool_embeddings,
                    like_vectors, current_round,
                    multimodal_floor=session_floor,
                )
                if not bid:
                    break
                served.append(bid)
                temp_exposed.append(bid)
        if not served:
            # exploring-edge fallback (rare: <min_likes embeddings resolved) — farthest-point
            tiers_map = defaultdict(list)
            for bid in pool_ids:
                tiers_map[pool_scores.get(bid, 0)].append(bid)
            exposed_temp = list(exposed_ids)
            for score in sorted(tiers_map.keys(), reverse=True):
                tier_ids = list(tiers_map[score])
                while len(served) < 3 and tier_ids:
                    nb = engine.farthest_point_from_pool(tier_ids, exposed_temp, pool_embeddings)
                    if nb:
                        served.append(nb)
                        exposed_temp.append(nb)
                        tier_ids.remove(nb)
                    else:
                        break
                if len(served) >= 3:
                    break
        if not served:
            non_exposed = [bid for bid in pool_ids if bid not in set(exposed_ids)]
            served = non_exposed[:1] if non_exposed else pool_ids[:1]

        initial_batch = served   # analyzing won't consume it, but keep state consistent

        # ── 5. Fetch first 3 cards for next_image + prefetch ──────────────
        _initial_cards = engine.get_buildings_by_ids(initial_batch[:3])
        first_card = _initial_cards[0] if len(_initial_cards) > 0 else None
        prefetch_card = _initial_cards[1] if len(_initial_cards) > 1 else None
        prefetch_card_2 = _initial_cards[2] if len(_initial_cards) > 2 else None

        # ── 6. Persist Project + AnalysisSession ──────────────────────────
        with transaction.atomic():
            project = Project.objects.create(
                user=profile,
                name='Discovery 취향 탐색',
                filters={},
                raw_query=None,
            )
            session = AnalysisSession.objects.create(
                user=profile,
                project=project,
                phase=phase,
                pool_ids=pool_ids,
                pool_scores=pool_scores,
                current_round=seeded_count,
                preference_vector=pref_vector if pref_vector else [],
                exposed_ids=exposed_ids + ([initial_batch[0]] if initial_batch else []),
                initial_batch=initial_batch,
                like_vectors=like_vectors,
                convergence_history=[],
                previous_pref_vector=[],
                original_filters={},
                original_filter_priority=[],
                original_seed_ids=list(seed_ids),
                current_pool_tier=current_pool_tier,
                v_initial=pref_vector if pref_vector else None,
                original_q_text=None,
                multimodal_floor=session_floor,
            )

        # ── 7. Evict caches (mirrors session_service.create_session) ──────
        evict_projects_list(profile.id)           # keyed by UserProfile.pk
        evict_user_profile_detail(profile.user.id)  # keyed by User.pk (Django auth user)
        evict_project_detail(str(project.project_id))

        # Seed prefetch cache for first swipe (mirrors session_service F4).
        # Promoted sessions start at current_round=seeded_count, so the first
        # swipe's consumer reads prefetch:{sid}:{seeded_count + 1} (saved_current_round
        # = current_round AFTER the first-swipe increment). Seed that exact key —
        # not :1 — or the first Taste swipe always misses the seeded cache.
        _pf_seed = {
            'prefetch_card_id': initial_batch[1] if len(initial_batch) > 1 else None,
            'prefetch_card_2_id': initial_batch[2] if len(initial_batch) > 2 else None,
        }
        cache.set(
            f'prefetch:{session.session_id}:{seeded_count + 1}',
            _pf_seed,
            timeout=RC.get('async_prefetch_cache_timeout_seconds', 60),
        )

        logger.info(
            'Discovery promote-to-taste: session=%s profile=%s seeds=%d phase=%s pool=%d',
            session.session_id, profile.id, seeded_count, phase, len(pool_ids),
        )

        return Response({
            'session_id': str(session.session_id),
            'project_id': str(project.project_id),
            'session_status': session.status,
            'next_image': first_card,
            'prefetch_image': prefetch_card,
            'prefetch_image_2': prefetch_card_2,
            'progress': _progress(session),
            'filter_relaxed': current_pool_tier > 1,
        }, status=status.HTTP_201_CREATED)


# ── BoardSurpriseView (preserved from v3.0) ───────────────────────────────────

class BoardSurpriseView(APIView):
    """
    GET /api/v1/recommendations/board-surprise/

    Returns up to 10 curated or cold-start-random buildings for the Surprise
    Board modal. Read-only: no persistence side-effects.

    Cold start (v_taste is None):
        cards = diverse random 10 minus excluded IDs
        title = "Discover something new"
        rationale = "A diverse starter pack"

    Warm (v_taste exists):
        cards = taste_ranked_page at offset 0, limit 10
        title = "Curated for you"
        rationale = "Based on your taste so far"
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        profile = _get_profile(request)
        if profile is None:
            return Response({'detail': 'unauthenticated'}, status=status.HTTP_401_UNAUTHORIZED)

        # Build exclusion set (all user projects incl. draft)
        projects = Project.objects.filter(user=profile).values('liked_ids', 'disliked_ids', 'saved_ids')
        liked_ids = []
        disliked_ids = []
        saved_ids = []
        for project in projects:
            liked_ids.extend(_liked_id_only(project.get('liked_ids')))
            disliked_ids.extend(project.get('disliked_ids') or [])
            saved_ids.extend(
                e.get('id')
                for e in (project.get('saved_ids') or [])
                if isinstance(e, dict) and e.get('id')
            )

        # BACK-RECOMMEND-4: include buildings liked via UserProfile.liked_building_ids
        profile_liked_bld_ids = [
            bid for bid in list(profile.liked_building_ids or [])
            if isinstance(bid, str)
        ]
        exclude_ids = []
        seen = set()
        for bid in liked_ids + disliked_ids + saved_ids + profile_liked_bld_ids:
            if isinstance(bid, str) and bid not in seen:
                exclude_ids.append(bid)
                seen.add(bid)
        exclude_set = set(exclude_ids)

        v_taste = get_or_build_taste(profile)
        if v_taste is None:
            cards = engine.get_diverse_random(n=10, filters=None)
            cards = [card for card in cards if card.get('canonical_bld_id') not in exclude_set]
            return Response({
                'cards': cards,
                'title': 'Discover something new',
                'rationale': 'A diverse starter pack',
            })

        cards = engine.taste_ranked_page(v_taste, exclude_ids, limit=10, offset=0)
        return Response({
            'cards': cards,
            'title': 'Curated for you',
            'rationale': 'Based on your taste so far',
        })
