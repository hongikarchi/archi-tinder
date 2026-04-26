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
