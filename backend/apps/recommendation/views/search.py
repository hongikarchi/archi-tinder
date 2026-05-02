import logging
import threading

from django.conf import settings
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .. import engine, services

logger = logging.getLogger('apps.recommendation')
RC = settings.RECOMMENDATION


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
                    fallback_note = "No exact matches for those criteria — here are similar buildings you might like."

        if not results:
            # Final fallback: diverse random
            results = engine.get_diverse_random(n=20)
            is_fallback = True
            fallback_note = "Couldn’t find an exact match — here are some buildings you might enjoy instead."

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
