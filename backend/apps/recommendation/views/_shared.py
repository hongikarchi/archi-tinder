"""Shared helpers used by 2+ view modules.

Rules:
- Helpers used in only 1 module live in that module instead.
- Module-level singletons (logger, RC) are defined per-module for explicit namespacing.
"""
import logging

from django.conf import settings

logger = logging.getLogger('apps.recommendation')
RC = settings.RECOMMENDATION  # noqa: used by callers importing from here, kept for convenience


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
    like_count = len(session.like_vectors) if session.like_vectors else 0
    target_swipes = max(1, int(RC.get('target_swipes', 10)))
    swipe_count = max(0, int(session.current_round or 0))
    return {
        'current_round': swipe_count,
        'swipe_count':   swipe_count,
        'target_swipes': target_swipes,
        'swipe_target_remaining': max(0, target_swipes - swipe_count),
        'like_count':    like_count,
        'dislike_count': swipe_count - like_count,
        'phase':         session.phase,
        'pool_size': len(session.pool_ids) if session.pool_ids else 0,
        'pool_remaining': len(set(session.pool_ids or []) - set(session.exposed_ids or [])),
        'action_card_shown': bool(getattr(session, 'action_card_shown', False)),
    }
