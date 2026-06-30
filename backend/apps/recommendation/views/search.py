import logging
import threading

from django.conf import settings
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .. import engine, services
from ..services.parse_query import _build_axis_chips, _STRONG_AXES

logger = logging.getLogger('apps.recommendation')
RC = settings.RECOMMENDATION

_NULLISH_FILTER_STRINGS = {'', 'null', 'none', 'n/a', 'na', 'undefined'}

_FALLBACK_NOTE = (
    "Couldn't find an exact match — here are some buildings you might enjoy instead."
)


def _first_user_text(conversation_history):
    for entry in conversation_history:
        if entry.get('role') == 'user':
            return (entry.get('text') or '').strip()
    return ''


def _clean_filter_value(value):
    if isinstance(value, str):
        value = value.strip()
        if value.lower() in _NULLISH_FILTER_STRINGS:
            return None
        if not any(ch.isalnum() for ch in value):
            return None
    return value


def _clean_filters(filters):
    cleaned = {}
    for key, value in (filters or {}).items():
        cleaned_value = _clean_filter_value(value)
        if key in ('year_min', 'year_max') and cleaned_value is not None:
            try:
                cleaned_value = int(cleaned_value)
            except (TypeError, ValueError):
                cleaned_value = None
            if cleaned_value is not None and not (1800 <= cleaned_value <= 2100):
                cleaned_value = None
        if cleaned_value is not None:
            cleaned[key] = cleaned_value
    return cleaned


def _clean_filter_priority(priority, filters):
    filter_keys = set(filters.keys())
    return [
        key for key in (priority or [])
        if isinstance(key, str) and key in filter_keys
    ][:10]


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
    from django.db import connections as _connections

    def _run():
        try:
            services.generate_visual_description(filters, raw_query, user_id)
        except Exception as exc:
            logger.warning('IMP-6 Stage 2 thread uncaught exception: %s', exc)
        finally:
            # Release all DB connections at thread exit (Django thread-local conn pool)
            _connections.close_all()

    t = threading.Thread(target=_run, daemon=True)
    t.start()
    # Do NOT join -- fire-and-forget; caller returns Stage 1 immediately.


# ── LLM Query Parsing ─────────────────────────────────────────────────────────

class ParseQueryView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        # ── Branch A: DETERMINISTIC RE-RANK (chip click, priority_axis provided) ─
        # Evaluated BEFORE conversation_history validation — chip-click calls omit
        # conversation_history (frontend resets it after the terminal response) so
        # validating it here would 400 every chip click.  Branch A uses prior_filters
        # + raw_query from request.data; conversation_history is not read or required.
        prior_filters_raw = request.data.get('prior_filters') or {}
        priority_axis = request.data.get('priority_axis')

        # Validate prior_filters: must be a dict (or absent)
        prior_filters = (
            _clean_filters(prior_filters_raw)
            if isinstance(prior_filters_raw, dict)
            else {}
        )

        # Validate priority_axis against known axis allowlist (400 on bad value)
        if priority_axis is not None and priority_axis not in _STRONG_AXES:
            return Response(
                {'detail': f'priority_axis must be one of {sorted(_STRONG_AXES)}'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if priority_axis is not None:
            # Branch A: deterministic re-rank.
            # Skip Gemini. Use prior_filters unchanged; boost chosen axis to rank 0.
            # search_by_filters_scored scores the FULL publishable corpus (soft CASE WHEN
            # on every axis + BM25) → returns exactly 20 ranked results.  No filter loss.
            # conversation_history is NOT required on this path.
            filters = dict(prior_filters)
            # image_focus may have been accumulated in prior filters; extract separately
            image_focus = filters.pop('image_focus', None)

            # Build filter_priority: chosen axis first, then remaining axes from prior.
            # Caller may send back the previous filter_priority list for ordering hints.
            prior_priority_raw = request.data.get('filter_priority') or []
            prior_other = [
                k for k in (
                    prior_priority_raw
                    if isinstance(prior_priority_raw, list)
                    else []
                )
                if k != priority_axis and k in filters
            ]
            # Include any filter keys not already in the explicit priority list
            remaining = [
                k for k in filters
                if k != priority_axis and k not in prior_other
            ]
            filter_priority = [priority_axis] + prior_other + remaining

            # raw_query from request.data (BM25 channel); fall back to empty string.
            raw_query = request.data.get('raw_query', '') or ''

            # Score-ranked search: all prior axes present, chosen axis at rank 0.
            # search_by_filters_scored soft-scores the full corpus → 20 results ranked
            # by all clues (chosen-axis-heavy → partial → others).
            is_fallback = False
            fallback_note = ''
            has_signal = bool(filters) or bool(raw_query and raw_query.strip())
            if has_signal:
                search_filters = dict(filters)
                if image_focus:
                    search_filters['image_focus'] = image_focus
                results = engine.search_by_filters_scored(
                    search_filters,
                    raw_query=raw_query,
                    filter_priority=filter_priority,
                    limit=20,
                    image_focus=image_focus,
                )
            else:
                results = []

            # Last-resort fallback: fires only when the scored search itself is empty
            # (SQL error or genuine zero-signal). Minimise random — only when necessary.
            if not results:
                results = engine.get_diverse_random(n=20, image_focus=image_focus)
                is_fallback = True
                fallback_note = _FALLBACK_NOTE

            # Re-emit the multi-axis chips so user can pick another axis.
            # Chosen axis sorts first for frontend affordance.
            all_chips = _build_axis_chips(filters)
            chips = sorted(
                all_chips,
                key=lambda c: (0 if c['axis'] == priority_axis else 1),
            )

            return Response({
                'probe_needed': False,
                'probe_question': None,
                'reply': '',
                'raw_query': raw_query,
                'visual_description': None,
                'structured_filters': filters,
                'filter_priority': filter_priority,
                'image_focus': image_focus,
                'suggestions': [],
                'results': results,
                'is_fallback': is_fallback,
                'fallback_note': fallback_note,
                # Calibration fields — deterministic values for chip-click path
                'confidence_score': 0.90,
                'system_action': 'REQUEST_PRIORITY',
                'suggested_quick_replies': chips,
                'priority_ordered': filter_priority,
                'llm_response_message': '추천에 더 중요하게 생각할 기준이 있나요?',
                'chosen_axis': priority_axis,
            })

        # ── Branch B: NORMAL / FREE-TEXT TURN (no priority_axis) ─────────────────
        # conversation_history is required here — LLM call needs it.
        # Accept BOTH legacy `query` string AND new `conversation_history` list.
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
                        {'detail': (
                            f'conversation_history.text too long (max {_MAX_TEXT_LEN} chars)'
                        )},
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

        # FULL-LANGUAGE-1: pass user's language preference to parse_query so it can
        # force reply/probe_question into the chosen language.
        # FILTER-DELTA: pass prior_filters so parse_query can inject them as context
        # for the LLM and apply the returned filter_delta deterministically.
        # parse_query now returns filters = the fully merged+repaired accumulated set.
        # The blind merge block that previously lived here has been DELETED.
        _profile = getattr(request.user, 'profile', None)
        _lang = getattr(_profile, 'language', None)
        parsed = services.parse_query(
            conversation_history, language=_lang, prior_filters=prior_filters or None,
        )
        parsed_filters = _clean_filters(parsed.get('filters') or {})

        parsed_priority = _clean_filter_priority(
            parsed.get('filter_priority') or parsed.get('priority_ordered'),
            parsed_filters,
        )
        raw_query = _first_user_text(conversation_history) or parsed.get('raw_query', '')

        # Compute results for EVERY turn (probe and terminal alike).
        # Product rule: every parse-query response shows ~20 references; the
        # probe question/chips are a supplementary overlay, never a replacement.
        # LLM-SEARCH-RANK-1: pure-soft IDF+BM25 scoring. is_publishable=true is
        # the only hard gate; all filter axes are soft (weighted CASE WHEN).
        filters = dict(parsed_filters)
        # image_focus lives outside the WHERE-clause filter dict but rides along
        # so cards get the user-requested cover variant.
        image_focus = parsed.get('image_focus')
        if image_focus:
            filters['image_focus'] = image_focus

        is_fallback = False
        fallback_note = ''

        # Score-ranked path: fires when any filter axis is set OR raw_query is non-empty.
        # Both conditions allow search_by_filters_scored to produce a ranked result set.
        # On probe turns, partial filters are tolerated — soft scoring works fine with
        # whatever partial signal the LLM extracted; get_diverse_random covers zero-signal.
        has_signal = bool(parsed_filters) or bool(raw_query and raw_query.strip())
        if has_signal:
            results = engine.search_by_filters_scored(
                filters,
                raw_query=raw_query,
                filter_priority=parsed_priority,
                limit=20,
                image_focus=image_focus,
            )
        else:
            results = []

        # Last-resort fallback: fires only when both filter-signal AND raw_query are
        # absent (true zero-signal) or the search returned empty (SQL error).
        # Preserves the get_diverse_random path for zero-signal queries; minimises
        # random — search_by_filters_scored already returns 20 for any non-empty signal.
        if not results:
            results = engine.get_diverse_random(n=20, image_focus=image_focus)
            is_fallback = True
            fallback_note = _FALLBACK_NOTE

        # Probe turn: return probe payload with real results already computed above.
        # Stage 2 is NOT spawned on probe turns — the filter set is still unstable.
        if parsed.get('probe_needed'):
            return Response({
                'probe_needed': True,
                'probe_question': parsed.get('probe_question'),
                'reply': parsed.get('reply', ''),
                'raw_query': raw_query,
                'structured_filters': parsed_filters,
                'filter_priority': parsed_priority,
                'visual_description': parsed.get('visual_description'),
                'suggestions': [],
                'results': results,
                'is_fallback': is_fallback,
                'fallback_note': fallback_note,
                'confidence_score': parsed.get('confidence_score'),
                'system_action': parsed.get('system_action'),
                'suggested_quick_replies': parsed.get('suggested_quick_replies', []),
                'priority_ordered': parsed.get('priority_ordered', []),
                'llm_response_message': parsed.get('llm_response_message', ''),
            })

        # IMP-6 Commit 2: spawn Stage 2 thread on terminal turn (probe_needed=False)
        # Stage 2 generates visual_description -> V_initial -> caches for SessionCreate.
        # Only fires when stage_decouple_enabled=True (default OFF).
        # Probe turns are excluded above (unstable filter set — do not spawn Stage 2).
        if RC.get('stage_decouple_enabled', False):
            _spawn_stage2(
                filters=parsed_filters,
                raw_query=raw_query,
                user_id=request.user.id,
            )

        # Terminal path (probe_needed=False): results already computed above.
        return Response({
            'probe_needed': False,
            'probe_question': None,
            'reply': parsed.get('reply', ''),
            'raw_query': raw_query,
            'visual_description': parsed.get('visual_description'),
            'structured_filters': parsed_filters,
            'filter_priority': parsed_priority,
            'image_focus': image_focus,
            'suggestions': [],
            'results': results,
            'is_fallback': is_fallback,
            'fallback_note': fallback_note,
            'confidence_score': parsed.get('confidence_score'),
            'system_action': parsed.get('system_action'),
            'suggested_quick_replies': parsed.get('suggested_quick_replies', []),
            'priority_ordered': parsed.get('priority_ordered', []),
            'llm_response_message': parsed.get('llm_response_message', ''),
        })
