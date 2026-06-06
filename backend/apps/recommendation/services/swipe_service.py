"""swipe_service.py — orchestration extracted from views/swipe.py.

Pure move: question-card state logic, buffer helpers, and view-body
orchestration relocated verbatim from SwipeView, ProjectBookmarkView,
and QuestionResponseView.  Zero behaviour changes.

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
import math

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
    evict_taste,
    evict_projects_list,
    evict_discovery_feed,
    evict_user_profile_detail,
    evict_project_detail,
    get_corpus_tag_df,
)
from ..views._shared import _progress, _liked_id_only

logger = logging.getLogger('apps.recommendation')
RC = settings.RECOMMENDATION

# ── Question card constants (ALGO-QCARD-1) ────────────────────────────────────

_AXIS_FIELDS = ('style', 'atmosphere', 'material_visual')

# Allowlist for axis column names interpolated into raw SQL in _compute_kw_vec_refine.
# Must be a fixed literal — never derived from request data.  (FIX: ALGO-QCARD axis injection)
_VALID_AXES = frozenset({'style', 'atmosphere', 'material_visual'})

_AXIS_QUESTIONS = {
    'atmosphere': {'q': '어떤 분위기에 더 끌리세요?', 'a': '따뜻하고 아늑한', 'b': '차갑고 절제된'},
    'material_visual': {'q': '재료감은 어느 쪽이 더 끌리세요?', 'a': '나무·돌 같은 자연재료', 'b': '콘크리트·유리 같은 인공재료'},
    'style': {'q': '디자인 방향은 어느 쪽이 더 끌리세요?', 'a': '간결하고 미니멀한', 'b': '풍부하고 디테일한'},
}

_REFRESH_QUESTION = {
    'type': 'refresh', 'axis': None,
    'q': '마음에 드는 건물이 잘 없었네요.',
    'a': '더 다양한 유형 보여줘',
    'b': '지금 타입으로 계속',
}


def _update_question_state(session, action, canonical_bld_id):
    """Update tag counts and consecutive-dislike counter for question card triggering."""
    session.question_cooldown = max(0, (session.question_cooldown or 0) - 1)

    if action == 'like':
        from django.db import connections
        try:
            with connections['buildings'].cursor() as cur:
                cur.execute(
                    "SELECT style, atmosphere, material_visual"
                    " FROM canonical_v2_buildings"
                    " WHERE canonical_bld_id = %s AND is_publishable = true",
                    [canonical_bld_id],
                )
                row = cur.fetchone()
        except Exception as exc:
            logger.warning('_update_question_state buildings fetch failed: %s', exc)
            row = None

        if row:
            # style/atmosphere are TEXT (single string), material_visual is TEXT[]
            style_tags = [row[0]] if row[0] else []
            atm_tags = [row[1]] if row[1] else []
            mat_tags = list(row[2]) if row[2] else []
            axis_tags = {
                'style': style_tags,
                'atmosphere': atm_tags,
                'material_visual': mat_tags,
            }
            counts = dict(session.tag_axis_counts or {})
            for axis, tags in axis_tags.items():
                axis_counts = dict(counts.get(axis, {}))
                for tag in tags:
                    axis_counts[tag] = axis_counts.get(tag, 0) + 1
                counts[axis] = axis_counts
            session.tag_axis_counts = counts

            all_tags = style_tags + atm_tags + mat_tags
            recent = list(session.recent_like_tag_sets or [])
            recent.append(all_tags)
            if len(recent) > 3:
                recent = recent[-3:]
            session.recent_like_tag_sets = recent

        session.q_card_consecutive_dislikes = 0

    elif action == 'dislike':
        session.q_card_consecutive_dislikes = (session.q_card_consecutive_dislikes or 0) + 1


def _dominant_axis(counts, intersection_tags):
    """Return the axis with the highest absolute count among intersection tags."""
    best_axis, best_count = None, 0
    for axis, axis_counts in counts.items():
        if axis not in _AXIS_QUESTIONS:
            continue
        axis_total = sum(axis_counts.get(t, 0) for t in intersection_tags)
        if axis_total > best_count:
            best_count, best_axis = axis_total, axis
    return best_axis


def _build_refine_trigger(axis, keyword=None):
    q = _AXIS_QUESTIONS.get(axis)
    if not q:
        return None
    if keyword:
        question_text = f'지금까지 고르신 카드들에서 [{keyword}] 특징이 강하게 보입니다. 이게 핵심 테마인가요?'
    else:
        question_text = q['q']
    return {
        'type': 'refine',
        'axis': axis,
        'keyword': keyword,
        'question': question_text,
        'option_a': q['a'],
        'option_b': q['b'],
    }


def _pick_discriminative_tag(session, axis):
    """Return the most TF-IDF-discriminative tag for the given axis.

    ALGO-QCARD Phase 2: replaces the raw-frequency pick used in Phase 1.

    For each tag in session.tag_axis_counts[axis]:
      - Skip tags in question_keyword_blacklist (case-insensitive).
      - Skip tags where df/N > question_common_tag_ratio (too common, non-discriminative).
      - score = tf * log(N / (df + 1)).
    Returns the highest-scoring tag.

    Falls back to frequency-based dominant tag if:
      - No tags survive the filters.
      - Corpus DF data is unavailable (get_corpus_tag_df()['_total'] == 0).
    """
    counts = session.tag_axis_counts or {}
    axis_counts = counts.get(axis, {})
    if not axis_counts:
        return None

    RC = settings.RECOMMENDATION
    blacklist = {t.lower() for t in RC.get('question_keyword_blacklist', [])}
    common_ratio = float(RC.get('question_common_tag_ratio', 0.4))

    df_map = get_corpus_tag_df()
    total_n = df_map.get('_total', 0) or 1  # guard div-by-zero
    axis_df = df_map.get(axis, {})

    # Corpus unavailable — fall back to frequency
    if df_map.get('_total', 0) == 0:
        return max(axis_counts, key=lambda t: axis_counts[t])

    best_tag = None
    best_score = -1.0
    for tag, tf in axis_counts.items():
        if tag.lower() in blacklist:
            continue
        df = axis_df.get(tag, 0)
        if df / total_n > common_ratio:
            continue
        score = tf * math.log(total_n / (df + 1))
        if score > best_score:
            best_score, best_tag = score, tag

    if best_tag is None:
        # All tags were filtered — fall back to frequency-dominant tag
        best_tag = max(axis_counts, key=lambda t: axis_counts[t])

    return best_tag


def _pick_pool_category(session):
    """Return the dominant program category in the session's current pool.

    ALGO-QCARD Phase 2 (Trigger B): queries the buildings DB for the most
    common program value among the session's pool_ids.

    Returns a program string (e.g. '주거') or None on failure / empty pool.
    """
    pool_ids = list(session.pool_ids or [])
    if not pool_ids:
        return None
    try:
        with connections['buildings'].cursor() as cur:
            cur.execute(
                'SELECT program, COUNT(*) cnt'
                ' FROM canonical_v2_buildings'
                ' WHERE is_publishable = true'
                ' AND canonical_bld_id = ANY(%s)'
                ' AND program IS NOT NULL'
                ' GROUP BY program'
                ' ORDER BY cnt DESC'
                ' LIMIT 1',
                [pool_ids],
            )
            row = cur.fetchone()
        return row[0] if row else None
    except Exception as exc:
        logger.warning('_pick_pool_category buildings query failed: %s', exc)
        return None


def _check_question_trigger(session, action):
    """Return question_trigger dict if a trigger condition is met, else None.

    ALGO-QCARD Phase 1 additions:
    - Caps at question_max_per_session (default 2): once session.question_count
      reaches the cap, no further question cards are shown.
    - Uses question_cooldown_swipes (default 15) for the cooldown window instead
      of the hardcoded 5 swipes.
    - Trigger payload now includes 'keyword' for refine triggers so the response
      handler knows which embedding direction to boost/penalize.
    """
    cooldown_n = RC.get('question_cooldown_swipes', 15)
    max_q = RC.get('question_max_per_session', 2)

    if (session.question_cooldown or 0) > 0:
        return None
    if (session.question_count or 0) >= max_q:
        return None

    # Refresh: consecutive dislikes >= 4 (Trigger B)
    if action == 'dislike' and (session.q_card_consecutive_dislikes or 0) >= 4:
        session.question_cooldown = cooldown_n
        session.question_count = (session.question_count or 0) + 1
        # ALGO-QCARD Phase 2: extract dominant pool category for a targeted question
        category = _pick_pool_category(session)
        if category:
            question_text = (
                f'원하는 느낌이 잘 안 나오나요? '
                f'혹시 [{category}] 공간을 찾고 계신가요?'
            )
        else:
            question_text = _REFRESH_QUESTION['q']
        return {
            'type': _REFRESH_QUESTION['type'],
            'axis': 'program' if category else _REFRESH_QUESTION['axis'],
            'keyword': category,
            'question': question_text,
            'option_a': _REFRESH_QUESTION['a'],
            'option_b': _REFRESH_QUESTION['b'],
        }

    if action != 'like':
        return None

    counts = session.tag_axis_counts or {}
    total_count = sum(sum(v.values()) for v in counts.values())

    # Refine condition A: intersection of last 3 liked card tags
    recent = session.recent_like_tag_sets or []
    if len(recent) == 3:
        intersection = set(recent[0]) & set(recent[1]) & set(recent[2])
        if intersection:
            winning_axis = _dominant_axis(counts, intersection)
            if winning_axis:
                # ALGO-QCARD Phase 2: use TF-IDF to pick the most discriminative
                # tag within the intersection (falls back to frequency if needed)
                best_tag = _pick_discriminative_tag(session, winning_axis)
                # Constrain to intersection tags: if TF-IDF winner is not in the
                # intersection, fall back to frequency pick within intersection
                axis_counts_local = counts.get(winning_axis, {})
                if best_tag not in intersection:
                    best_tag = max(
                        intersection,
                        key=lambda t: axis_counts_local.get(t, 0),
                        default=None,
                    )
                session.question_cooldown = cooldown_n
                session.question_count = (session.question_count or 0) + 1
                return _build_refine_trigger(winning_axis, keyword=best_tag)

    # Refine condition B: single tag >= 70% of total likes
    if total_count >= 3:
        for axis, axis_counts in counts.items():
            for tag, cnt in axis_counts.items():
                if cnt / total_count >= 0.70:
                    # ALGO-QCARD Phase 2: use TF-IDF-discriminative tag for the axis
                    # (the 70% tag is used as the trigger condition; the question
                    # keyword is the most discriminative tag on that axis, which
                    # may differ from the 70% tag if a more specific term exists)
                    best_tag = _pick_discriminative_tag(session, axis)
                    session.question_cooldown = cooldown_n
                    session.question_count = (session.question_count or 0) + 1
                    return _build_refine_trigger(axis, keyword=best_tag)

    # Refine condition C (ALGO-QCARD Phase 3): hyper-positive / fast-swipe detection.
    # Fires when the user has rapidly liked almost everything in the recent window,
    # suggesting mindless swiping that needs active taste disambiguation.
    hp_window = RC.get('question_hyperpositive_window', 10)
    hp_min_likes = RC.get('question_hyperpositive_min_likes', 8)
    lats = list(session.recent_latencies or [])
    avg_lat = (sum(lats) / len(lats)) if lats else None
    fast_ms = RC.get('question_fast_swipe_ms', 1500)
    lat_cap = RC.get('recent_latencies_cap', 10)
    lat_min_samples = max(1, min(hp_window, lat_cap) // 2)
    hp_recent = _recent_actions(session, hp_window)
    hp_like_count = sum(1 for a in hp_recent if a == 'like')
    if (
        len(hp_recent) >= hp_window
        and hp_like_count >= hp_min_likes
        and avg_lat is not None
        and len(lats) >= lat_min_samples
        and avg_lat < fast_ms
    ):
        # Pick axis by highest total count (mirrors _dominant_axis without needing
        # an intersection set — use all known tags as the candidate universe).
        if counts:
            hp_axis = max(
                (ax for ax in counts if ax in _AXIS_QUESTIONS),
                key=lambda ax: sum(counts[ax].values()) if counts.get(ax) else 0,
                default=None,
            )
            if hp_axis and counts.get(hp_axis):
                hp_keyword = _pick_discriminative_tag(session, hp_axis)
                if hp_keyword:
                    session.question_cooldown = cooldown_n
                    session.question_count = (session.question_count or 0) + 1
                    return _build_refine_trigger(hp_axis, keyword=hp_keyword)

    return None


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


def _recent_actions(session, window):
    return list(
        reversed(
            list(
                session.swipes.order_by('-created_at')
                .values_list('action', flat=True)[:window]
            )
        )
    )


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
        if session.phase not in ('converged', 'completed') or session.extended_rounds >= 5:
            residual_noop = len([
                pid for pid in session.pool_ids
                if pid not in set(session.exposed_ids)
            ]) if session.pool_ids else 0
            can_continue_noop = (residual_noop >= 1) and (session.extended_rounds < 5)
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

        session.extended_rounds += 1
        session.phase = 'analyzing'
        session.convergence_history = []
        # Seed previous_pref_vector from the current centroid so delta_v tracking
        # resumes on the first post-extend swipe. Clearing to [] (old behaviour)
        # made compute_confidence always return None in the extended session.
        if session.like_vectors:
            _, global_centroid = engine.compute_taste_centroids(
                session.like_vectors, session.current_round,
                multimodal_floor=session.multimodal_floor,
            )
            session.previous_pref_vector = global_centroid.tolist()
        else:
            session.previous_pref_vector = []

        if client_buffer_ids:
            session.exposed_ids = _merge_buffer_into_exposed(session.exposed_ids, client_buffer_ids)

        engine.refresh_pool_if_low(session, threshold=5)

        pool_embeddings = engine.get_pool_embeddings(session.pool_ids)
        next_card_id = engine.compute_mmr_next(
            session.pool_ids, session.exposed_ids, pool_embeddings,
            session.like_vectors, session.current_round,
            multimodal_floor=session.multimodal_floor,
            question_bias_vector=session.question_bias_vector,
        )
        next_card = engine.get_building_card(next_card_id) if next_card_id else None
        if next_card:
            session.exposed_ids = session.exposed_ids + [next_card['canonical_bld_id']]

        session.save(update_fields=[
            'extended_rounds', 'phase', 'convergence_history', 'previous_pref_vector',
            'exposed_ids', 'pool_ids', 'pool_scores', 'current_pool_tier',
        ])

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
        'can_continue': (residual_after >= 1) and (session.extended_rounds < 5),
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
    if canonical_bld_id:
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
        # Keep Project JSON lists synchronized per existing API contract.
        # Lock order: Session -> Project (bookmark POST takes only Project).
        project = Project.objects.select_for_update().get(pk=session.project_id)

        # 1. Get embedding and update preference vector
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
                session.like_vectors = session.like_vectors + [{'embedding': embedding, 'round': session.current_round}]
        else:
            if canonical_bld_id not in project.disliked_ids:
                project.disliked_ids = project.disliked_ids + [canonical_bld_id]
        project.save(update_fields=['liked_ids', 'disliked_ids'])
        evict_taste(profile.id)
        evict_discovery_feed(profile.id)
        # Fix 1: evict /projects/ cache — liked_ids/disliked_ids counts changed.
        evict_projects_list(profile.id)
        evict_project_detail(str(project.project_id))

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
                session.like_vectors, session.current_round,
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

        _convergence_window = RC.get('convergence_window', 3)
        _recent_action_window = max(
            _convergence_window,
            RC.get('max_consecutive_dislikes', 5),
        )
        _recent_actions_window = _recent_actions(session, _recent_action_window)
        _recent_convergence_actions = _recent_actions_window[-_convergence_window:]
        if session.phase == 'analyzing' and engine.check_convergence(
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

        # ID selection only — DB fetch deferred to post-transaction batch call.
        if session.phase == 'converged':
            next_bid = None  # S3: no end-of-session card in stream; frontend handles end-screen
        elif session.phase == 'exploring':
            exposed_set = set(session.exposed_ids)
            next_bid = None
            if session.current_round < len(session.initial_batch):
                _candidate = session.initial_batch[session.current_round]
                if _candidate and _candidate not in exposed_set:
                    next_bid = _candidate
                else:
                    # initial_batch slot already exposed — fall through to farthest-point
                    next_bid = engine.farthest_point_from_pool(
                        session.pool_ids, session.exposed_ids, pool_embeddings
                    )
            else:
                recent_swipes = list(
                    reversed(
                        _recent_actions_window[-RC.get('max_consecutive_dislikes', 5):]
                    )
                )
                consecutive_dislikes = 0
                for s in recent_swipes:
                    if s == 'dislike':
                        consecutive_dislikes += 1
                    else:
                        break

                if consecutive_dislikes >= RC.get('max_consecutive_dislikes', 5):
                    # Batch-fetch dislike embeddings (single query instead of N individual calls)
                    dislike_ids = list(
                        session.swipes
                        .filter(action='dislike')
                        .order_by('-created_at')
                        .values_list('canonical_bld_id', flat=True)[:10]
                    )
                    dislike_embeds = []
                    if dislike_ids:
                        dislike_emb_map = engine.get_pool_embeddings(dislike_ids)
                        dislike_embeds = [dislike_emb_map[did] for did in dislike_ids if did in dislike_emb_map]
                    next_bid = engine.get_dislike_fallback(
                        session.pool_ids, session.exposed_ids, pool_embeddings, dislike_embeds
                    )
                else:
                    next_bid = engine.farthest_point_from_pool(
                        session.pool_ids, session.exposed_ids, pool_embeddings
                    )
        elif session.phase == 'analyzing':
            next_bid = engine.compute_mmr_next(
                session.pool_ids, session.exposed_ids, pool_embeddings,
                session.like_vectors, session.current_round,
                question_bias_vector=session.question_bias_vector,
                multimodal_floor=session.multimodal_floor,
            )
            if not next_bid:
                # Pool exhausted during analyzing
                session.phase = 'converged'
        else:
            next_bid = None

        if next_bid and next_bid not in session.exposed_ids:
            session.exposed_ids = session.exposed_ids + [next_bid]

        _mark('select_done')

        # Question card trigger state update (ALGO-QCARD-1).
        # Called inside the transaction so question state is consistent with swipe row.
        _update_question_state(session, action, canonical_bld_id)

        # ALGO-QCARD Phase 3: capture inter-swipe latency BEFORE trigger evaluation
        # so the new sample is included in avg_lat inside _check_question_trigger.
        _lat_raw = request.data.get('latency_ms')
        try:
            _lat = float(_lat_raw) if _lat_raw is not None else None
        except (TypeError, ValueError):
            _lat = None
        if _lat is not None and 0 < _lat <= 120000:
            _lat_cap = RC.get('recent_latencies_cap', 10)
            session.recent_latencies = (list(session.recent_latencies or []) + [_lat])[-_lat_cap:]

        question_trigger = _check_question_trigger(session, action)

        # Save session BEFORE prefetch so concurrent requests see updated exposed_ids.
        # pool_ids/pool_scores/current_pool_tier included unconditionally to persist
        # any in-place mutations from refresh_pool_if_low (A4 pool exhaustion guard).
        session.save(update_fields=[
            'preference_vector', 'current_round', 'exposed_ids',
            'phase', 'like_vectors', 'convergence_history', 'previous_pref_vector',
            'pool_ids', 'pool_scores', 'current_pool_tier',
            'tag_axis_counts', 'recent_like_tag_sets',
            'question_cooldown', 'q_card_consecutive_dislikes',
            'question_count', 'question_bias_vector',
            'recent_latencies',
        ])

        # Save copies for prefetch calculation outside transaction
        saved_pool_ids = list(session.pool_ids)
        saved_exposed_ids = list(session.exposed_ids)
        saved_like_vectors = list(session.like_vectors) if session.like_vectors else []
        saved_initial_batch = list(session.initial_batch) if session.initial_batch else []
        saved_current_round = session.current_round
        saved_phase = session.phase
        saved_multimodal_floor = session.multimodal_floor
        # Cache pool_embeddings -- same pool_ids, no need to re-fetch outside transaction
        saved_pool_embeddings = pool_embeddings
        saved_recent_actions = list(_recent_actions_window)
        # ALGO-QCARD Phase 1: snapshot bias vector for async prefetch thread
        saved_question_bias_vector = session.question_bias_vector

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
        'saved_question_bias_vector': saved_question_bias_vector,
        'pool_embeddings': pool_embeddings,
        '_embedding_stats': _embedding_stats,
        '_pool_escalation_fired': _pool_escalation_fired,
        '_timing_marks': _timing_marks,
        'question_trigger': question_trigger,
        '_t_start': _t_start,
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
    saved_phase, saved_exposed_ids, saved_initial_batch, saved_current_round,
    saved_pool_ids, saved_pool_embeddings, saved_like_vectors,
    saved_question_bias_vector=None,
    saved_multimodal_floor=None,
):
    """Compute prefetch IDs on the sync path (CPU-only, no DB).

    Returns (pf_bid, pf2_bid).  Verbatim from the sync else-branch in SwipeView.post.

    saved_question_bias_vector: optional accumulated soft-bias vector
    (ALGO-QCARD Phase 1) passed through to compute_mmr_next on the analyzing path.
    """
    pf_bid = None
    pf2_bid = None
    try:
        if saved_phase == 'exploring':
            exposed_set = set(saved_exposed_ids)
            if saved_current_round + 1 < len(saved_initial_batch):
                _candidate = saved_initial_batch[saved_current_round + 1]
                if _candidate and _candidate not in exposed_set:
                    pf_bid = _candidate
                else:
                    pf_bid = engine.farthest_point_from_pool(
                        saved_pool_ids, saved_exposed_ids, saved_pool_embeddings
                    )
            else:
                pf_bid = engine.farthest_point_from_pool(
                    saved_pool_ids, saved_exposed_ids, saved_pool_embeddings
                )
        elif saved_phase == 'analyzing':
            pf_bid = engine.compute_mmr_next(
                saved_pool_ids, saved_exposed_ids, saved_pool_embeddings,
                saved_like_vectors, saved_current_round + 1,
                question_bias_vector=saved_question_bias_vector,
                multimodal_floor=saved_multimodal_floor,
            )
    except Exception:
        pf_bid = None

    if pf_bid:
        try:
            # Use pf_bid string directly — card data not needed for ID selection.
            temp_exposed = saved_exposed_ids + [pf_bid]
            if saved_phase == 'exploring':
                exposed_set = set(temp_exposed)
                if saved_current_round + 2 < len(saved_initial_batch):
                    _candidate = saved_initial_batch[saved_current_round + 2]
                    if _candidate and _candidate not in exposed_set:
                        pf2_bid = _candidate
                    else:
                        pf2_bid = engine.farthest_point_from_pool(
                            saved_pool_ids, temp_exposed, saved_pool_embeddings
                        )
                else:
                    pf2_bid = engine.farthest_point_from_pool(
                        saved_pool_ids, temp_exposed, saved_pool_embeddings
                    )
            elif saved_phase == 'analyzing':
                pf2_bid = engine.compute_mmr_next(
                    saved_pool_ids, temp_exposed, saved_pool_embeddings,
                    saved_like_vectors, saved_current_round + 2,
                    question_bias_vector=saved_question_bias_vector,
                    multimodal_floor=saved_multimodal_floor,
                )
        except Exception:
            pf2_bid = None

    return pf_bid, pf2_bid


def _compute_kw_vec_refine(keyword, axis, session):
    """Compute L2-normalized keyword embedding vector for a refine question response.

    Queries the buildings DB for pool cards whose tag on `axis` matches `keyword`,
    averages their embeddings, and returns the L2-normalized result.

    Returns np.ndarray (384,) normalized, or None if no matching cards/embeddings.
    """
    if not keyword or not axis or not session.pool_ids:
        return None
    if axis not in _VALID_AXES:
        return None

    pool_ids = list(session.pool_ids)
    try:
        placeholders = ','.join(['%s'] * len(pool_ids))
        if axis == 'material_visual':
            query = (
                f"SELECT canonical_bld_id FROM canonical_v2_buildings"
                f" WHERE canonical_bld_id IN ({placeholders})"
                f" AND is_publishable = true"
                f" AND EXISTS (SELECT 1 FROM unnest(material_visual) m WHERE m ILIKE %s)"
            )
            params = pool_ids + [keyword]
        else:
            # style and atmosphere are plain TEXT columns
            query = (
                f"SELECT canonical_bld_id FROM canonical_v2_buildings"
                f" WHERE canonical_bld_id IN ({placeholders})"
                f" AND is_publishable = true"
                f" AND {axis} ILIKE %s"
            )
            params = pool_ids + [keyword]

        with connections['buildings'].cursor() as cur:
            cur.execute(query, params)
            matching_ids = [row[0] for row in cur.fetchall()]
    except Exception as exc:
        logger.warning('_compute_kw_vec_refine buildings query failed: %s', exc)
        return None

    if not matching_ids:
        return None

    pool_embeddings = engine.get_pool_embeddings(matching_ids)
    if not pool_embeddings:
        return None

    vecs = [pool_embeddings[bid] for bid in matching_ids if bid in pool_embeddings]
    if not vecs:
        return None

    mean_vec = np.mean(np.stack(vecs), axis=0)
    norm = np.linalg.norm(mean_vec)
    if norm < 1e-12:
        return None
    return mean_vec / norm


def _compute_kw_vec_refresh(session):
    """Compute L2-normalized embedding direction from recent dislikes for a refresh question.

    Returns np.ndarray (384,) normalized, or None if insufficient data.
    """
    dislike_ids = list(
        session.swipes
        .filter(action='dislike')
        .order_by('-created_at')
        .values_list('canonical_bld_id', flat=True)[:10]
    )
    if not dislike_ids:
        return None

    pool_embeddings = engine.get_pool_embeddings(dislike_ids)
    vecs = [pool_embeddings[bid] for bid in dislike_ids if bid in pool_embeddings]
    if not vecs:
        return None

    mean_vec = np.mean(np.stack(vecs), axis=0)
    norm = np.linalg.norm(mean_vec)
    if norm < 1e-12:
        return None
    return mean_vec / norm


def _compute_kw_vec_category(program, session):
    """Compute L2-normalized centroid embedding for a program category.

    ALGO-QCARD Phase 2 (Part C3): used for refresh questions that carry a
    specific program category keyword.  Queries the buildings DB for pool
    cards belonging to the program, averages their pre-computed embeddings,
    and returns the L2-normalized result.

    Returns np.ndarray (384,) normalized, or None if no matching data.
    """
    if not program or not session.pool_ids:
        return None

    pool_ids = list(session.pool_ids)
    try:
        with connections['buildings'].cursor() as cur:
            cur.execute(
                'SELECT canonical_bld_id FROM canonical_v2_buildings'
                ' WHERE is_publishable = true'
                ' AND canonical_bld_id = ANY(%s)'
                ' AND program = %s',
                [pool_ids, program],
            )
            matching_ids = [row[0] for row in cur.fetchall()]
    except Exception as exc:
        logger.warning('_compute_kw_vec_category buildings query failed: %s', exc)
        return None

    if not matching_ids:
        return None

    pool_embeddings = engine.get_pool_embeddings(matching_ids)
    if not pool_embeddings:
        return None

    vecs = [pool_embeddings[bid] for bid in matching_ids if bid in pool_embeddings]
    if not vecs:
        return None

    mean_vec = np.mean(np.stack(vecs), axis=0)
    norm = np.linalg.norm(mean_vec)
    if norm < 1e-12:
        return None
    return mean_vec / norm


def handle_question_response(request, profile, session_id):
    """Orchestrate QuestionResponseView.post body.

    ALGO-QCARD Phase 1: the answer now mutates session.question_bias_vector
    via soft-vector math and triggers a qbias-aware prefetch flush.

    Request body: {question_type, axis, keyword, selected_option}
    Response: {accepted, flush_prefetch, [next_image, prefetch_image, prefetch_image_2, progress]}
    """
    session = AnalysisSession.objects.filter(session_id=session_id, user=profile).first()
    if not session:
        return Response({'detail': 'Session not found'}, status=status.HTTP_404_NOT_FOUND)

    question_type = request.data.get('question_type', '')
    axis = request.data.get('axis')
    keyword = request.data.get('keyword')
    selected_option = request.data.get('selected_option', '')

    if question_type not in ('refine', 'refresh'):
        return Response(
            {'detail': 'question_type must be refine or refresh'},
            status=status.HTTP_400_BAD_REQUEST,
        )
    if selected_option not in ('A', 'B', 'skip'):
        return Response(
            {'detail': 'selected_option must be A, B, or skip'},
            status=status.HTTP_400_BAD_REQUEST,
        )

    cooldown_n = RC.get('question_cooldown_swipes', 15)
    boost_w = float(RC.get('question_boost_weight', 2.0))
    penalty_w = float(RC.get('question_penalty_weight', 1.0))

    # ── skip: reset state only, no algo change ────────────────────────────
    if selected_option == 'skip':
        event_log.emit_event(
            'tag_answer',
            session=session,
            user=profile,
            question_type=question_type,
            axis=axis,
            selected_option=selected_option,
        )
        with transaction.atomic():
            s = AnalysisSession.objects.select_for_update().get(
                session_id=session_id, user=profile
            )
            s.question_cooldown = cooldown_n
            s.q_card_consecutive_dislikes = 0
            s.save(update_fields=['question_cooldown', 'q_card_consecutive_dislikes'])
        return Response(
            {'accepted': True, 'flush_prefetch': False},
            status=status.HTTP_200_OK,
        )

    # ── compute keyword vector ────────────────────────────────────────────
    kw_vec = None
    if question_type == 'refine':
        # Resolve keyword: prefer the one echoed from trigger; fall back to
        # dominant tag from session counts on `axis`.
        _kw = keyword
        if not _kw and axis:
            counts = session.tag_axis_counts or {}
            axis_counts = counts.get(axis, {})
            if axis_counts:
                _kw = max(axis_counts, key=lambda t: axis_counts[t])
        if _kw and axis:
            kw_vec = _compute_kw_vec_refine(_kw, axis, session)
    else:  # refresh
        # ALGO-QCARD Phase 2: if a program category keyword was provided, use
        # the program centroid vector instead of the dislike direction.
        if keyword and axis == 'program':
            kw_vec = _compute_kw_vec_category(keyword, session)
        # Fall back to dislike-direction when no category available
        if kw_vec is None:
            kw_vec = _compute_kw_vec_refresh(session)

    # ── apply soft bias delta ─────────────────────────────────────────────
    delta = None
    if kw_vec is not None:
        if question_type == 'refine':
            if selected_option == 'A':   # Yes
                delta = boost_w * kw_vec
            else:                        # No (B)
                delta = -penalty_w * kw_vec
        else:  # refresh
            # ALGO-QCARD Phase 2: refresh with category keyword reverses sign semantics
            # vs. the Phase 1 dislike-direction refresh:
            #   A (Yes, "that category") → boost toward the category centroid
            #   B (No) → penalize the category centroid (push away)
            # When no category keyword is present the Phase 1 semantics apply:
            #   A (Yes, "show me different") → push AWAY from dislike direction
            if keyword and axis == 'program':
                if selected_option == 'A':   # Yes, that category
                    delta = boost_w * kw_vec
                else:                        # No (B) — not that category
                    delta = -penalty_w * kw_vec
            else:
                # Phase 1 dislike-direction refresh (no category)
                if selected_option == 'A':   # Yes, "show me different" → push away
                    delta = -penalty_w * kw_vec
                # B (keep going) → delta = 0, no bias change

    # ── atomic state save ─────────────────────────────────────────────────
    with transaction.atomic():
        s = AnalysisSession.objects.select_for_update().get(
            session_id=session_id, user=profile
        )

        if delta is not None:
            existing = s.question_bias_vector
            if existing and len(existing) == 384:
                new_qbias = [existing[i] + float(delta[i]) for i in range(384)]
            else:
                new_qbias = [float(v) for v in delta]
            s.question_bias_vector = new_qbias
        # Reset streak + cooldown regardless of whether bias was updated
        s.question_cooldown = cooldown_n
        s.q_card_consecutive_dislikes = 0
        s.save(update_fields=[
            'question_bias_vector', 'question_cooldown', 'q_card_consecutive_dislikes',
        ])
        # Keep fresh reference for the prefetch recompute below
        session = s

    # Emit tag_answer event (after save so bias is persisted if event fails)
    event_log.emit_event(
        'tag_answer',
        session=session,
        user=profile,
        question_type=question_type,
        axis=axis,
        selected_option=selected_option,
        keyword=keyword,
    )

    # ── recompute next + 2 prefetch with qbias-aware ranking ─────────────
    next_card = None
    prefetch_card = None
    prefetch_card_2 = None

    try:
        pool_embeddings = engine.get_pool_embeddings(session.pool_ids)
        like_vectors = session.like_vectors or []
        exposed_ids = list(session.exposed_ids or [])

        card_ids = []
        temp_exposed = list(exposed_ids)

        for _ in range(3):
            if like_vectors:
                bid = engine.compute_mmr_next(
                    session.pool_ids, temp_exposed, pool_embeddings,
                    like_vectors, session.current_round,
                    multimodal_floor=session.multimodal_floor,
                    question_bias_vector=session.question_bias_vector,
                )
            else:
                # Exploring phase — no like_vectors; use farthest-point
                bid = engine.farthest_point_from_pool(
                    session.pool_ids, temp_exposed, pool_embeddings
                )
            if bid:
                card_ids.append(bid)
                temp_exposed = temp_exposed + [bid]

        if card_ids:
            fetched = {
                c['canonical_bld_id']: c
                for c in engine.get_buildings_by_ids(card_ids)
            }
            if len(card_ids) > 0:
                next_card = fetched.get(card_ids[0])
            if len(card_ids) > 1:
                prefetch_card = fetched.get(card_ids[1])
            if len(card_ids) > 2:
                prefetch_card_2 = fetched.get(card_ids[2])

        # Mark first new card as exposed so subsequent swipes don't re-select it
        if card_ids:
            first_new = card_ids[0]
            if first_new not in set(session.exposed_ids):
                with transaction.atomic():
                    s2 = AnalysisSession.objects.select_for_update().get(
                        session_id=session_id, user=profile
                    )
                    if first_new not in set(s2.exposed_ids):
                        s2.exposed_ids = s2.exposed_ids + [first_new]
                        s2.save(update_fields=['exposed_ids'])
    except Exception as exc:
        logger.warning('handle_question_response flush recompute failed: %s', exc)

    return Response(
        {
            'accepted': True,
            'flush_prefetch': True,
            'next_image': next_card,
            'prefetch_image': prefetch_card,
            'prefetch_image_2': prefetch_card_2,
            'progress': _progress(session),
        },
        status=status.HTTP_200_OK,
    )
