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
