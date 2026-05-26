"""
Session event log helper (spec §6 implementation).

Events are emitted for measurement and post-hoc analysis. Failures in event
emission MUST NEVER crash the request -- log to standard logger and continue.
"""

import logging

logger = logging.getLogger('apps.recommendation')


def emit_event(event_type, session=None, user=None, **payload):
    """
    Emit a SessionEvent record.

    `event_type` must match one of SessionEvent.EVENT_TYPE_CHOICES.
    `session` and `user` are optional FK refs; payload is the event-specific
    structured data (will be stored as JSONField).

    Returns the created SessionEvent on success, None on failure.
    Never raises -- failure to log must not block the request.

    sequence_no is computed per-session as the count of existing events for
    that session at insert time. This isn't strictly monotonic under high
    concurrency (two simultaneous emits could both observe count=N and both
    write seq=N+1) but is robust enough for our use -- created_at microsecond
    resolution is the primary ordering signal; seq_no is the tie-breaker.
    """
    # Import inside function to avoid circular-import issues at module load time.
    from apps.recommendation.models import SessionEvent

    try:
        seq = 0
        if session is not None:
            seq = SessionEvent.objects.filter(session=session).count()
        return SessionEvent.objects.create(
            event_type=event_type,
            session=session,
            user=user,
            payload=payload,
            sequence_no=seq,
        )
    except Exception as e:
        logger.warning(
            'emit_event failed: %s (event_type=%s, session_id=%s)',
            e, event_type, getattr(session, 'session_id', None),
        )
        return None


def emit_event_batch(events):
    """
    Emit multiple SessionEvent records in a single bulk_create (one SQL round-trip).

    `events` is a list of dicts, each with keys:
        event_type  (str, required)
        session     (AnalysisSession | None)
        user        (UserProfile | None)
        **payload   (all other keys → stored as JSONField payload)

    sequence_no assignment: one COUNT(*) per unique session in the batch, then
    events sharing that session are numbered seq, seq+1, seq+2, ... in list order.
    Sessions that appear multiple times share one DB round-trip for count.

    Returns list of created SessionEvent instances on success, [] on failure.
    Never raises -- failure to log must not block the request.
    """
    if not events:
        return []

    from apps.recommendation.models import SessionEvent

    try:
        # Compute base sequence numbers per unique session (one query per unique session).
        _session_seqs = {}
        for ev in events:
            s = ev.get('session')
            key = getattr(s, 'pk', None)
            if key not in _session_seqs:
                base = SessionEvent.objects.filter(session=s).count() if s is not None else 0
                _session_seqs[key] = base

        # Build model instances, incrementing seq per session as we go.
        _session_offsets = {}
        instances = []
        for ev in events:
            s = ev.get('session')
            u = ev.get('user')
            et = ev['event_type']
            payload = {k: v for k, v in ev.items() if k not in ('event_type', 'session', 'user')}
            key = getattr(s, 'pk', None)
            offset = _session_offsets.get(key, 0)
            seq = _session_seqs[key] + offset
            _session_offsets[key] = offset + 1
            instances.append(SessionEvent(
                event_type=et,
                session=s,
                user=u,
                payload=payload,
                sequence_no=seq,
            ))

        SessionEvent.objects.bulk_create(instances)
        return instances
    except Exception as e:
        session_id = getattr(events[0].get('session'), 'session_id', None) if events else None
        logger.warning(
            'emit_event_batch failed: %s (count=%d, first_event_type=%s, session_id=%s)',
            e, len(events), events[0].get('event_type') if events else None, session_id,
        )
        return []


def aggregate_session_clustering_stats(session_id):
    """
    Topic 06 / IMP-10 sub-task A: aggregate cluster_count_used + silhouette_score
    across a session's confidence_update events for session_end payload.

    Returns dict:
        {
          'cluster_count_distribution': dict[str, int],  # str keys for JSONField stability (e.g., {'1': 3, '2': 2})
          'silhouette_score_p50': float | None,           # median; None if no scores
        }

    Returns safely-empty dict (distribution={}, p50=None) on:
      - session_id is None
      - no confidence_update events exist yet
      - all events have silhouette_score=None (adaptive flag was off)
      - any exception (function never raises)

    Called from SwipeView (session_end path) after action_card like.
    """
    from apps.recommendation.models import SessionEvent

    empty = {'cluster_count_distribution': {}, 'silhouette_score_p50': None}
    if session_id is None:
        return empty
    try:
        events = SessionEvent.objects.filter(
            session_id=session_id,
            event_type='confidence_update',
        ).values_list('payload', flat=True)

        distribution = {}
        sil_scores = []
        for payload in events:
            if not isinstance(payload, dict):
                continue
            k = payload.get('cluster_count_used')
            if k is not None:
                sk = str(k)
                distribution[sk] = distribution.get(sk, 0) + 1
            sil = payload.get('silhouette_score')
            if sil is not None:
                sil_scores.append(float(sil))

        p50 = None
        if sil_scores:
            sorted_sils = sorted(sil_scores)
            n = len(sorted_sils)
            mid = n // 2
            if n % 2 == 1:
                p50 = sorted_sils[mid]
            else:
                p50 = (sorted_sils[mid - 1] + sorted_sils[mid]) / 2.0

        return {
            'cluster_count_distribution': distribution,
            'silhouette_score_p50': p50,
        }
    except Exception as exc:
        logger.warning(
            'aggregate_session_clustering_stats failed for session %s: %s',
            session_id, exc,
        )
        return empty


def emit_swipe_event(session, user, direction, card_id, intensity, rank_in_pool,
                     timing_breakdown, idempotency_key=None,
                     cache_hit=None, cache_source=None, cache_partial_miss_count=None,
                     prefetch_strategy=None, db_call_count=None,
                     pool_escalation_fired=None, pool_signature_hash=None):
    """Convenience wrapper for the most-emitted event type.

    IMP-7 §6 fields (spec v1.6):
        cache_hit: bool -- True if all pool embeddings were served from cache this swipe.
        cache_source: str -- 'precompute' (full hit) or 'fresh' (any miss).
        cache_partial_miss_count: int -- number of building_ids not in cache at call time.
        prefetch_strategy: str -- 'sync' baseline; 'async-thread' when IMP-8 ships.
        db_call_count: int | None -- null until IMP-9 connection-level instrumentation.
        pool_escalation_fired: bool -- True if refresh_pool_if_low escalated tier this swipe.
        pool_signature_hash: str | None -- first 16 hex chars of SHA-256 of sorted pool_ids.
    """
    return emit_event(
        'swipe',
        session=session,
        user=user,
        direction=direction,
        card_id=card_id,
        intensity=intensity,
        rank_in_pool=rank_in_pool,
        timing_breakdown=timing_breakdown,
        idempotency_key=idempotency_key,
        cache_hit=cache_hit,
        cache_source=cache_source,
        cache_partial_miss_count=cache_partial_miss_count,
        prefetch_strategy=prefetch_strategy,
        db_call_count=db_call_count,
        pool_escalation_fired=pool_escalation_fired,
        pool_signature_hash=pool_signature_hash,
    )
