import json
import logging
import queue
import threading

from django.conf import settings
from django.db import connections as _db_connections
from django.http import StreamingHttpResponse
from rest_framework import status
from rest_framework.negotiation import DefaultContentNegotiation
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.utils.encoders import JSONEncoder
from rest_framework.views import APIView

from .. import engine, services
from ..services.parse_query import _build_axis_chips, _STRONG_AXES
from ..throttles import LLMSearchThrottle

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
    - connections.close_all() in finally: releases this thread's DB connections at exit
      (with the psycopg pool this RETURNS the checked-out connection to the
      pool; a short-lived thread that skips it leaks a pool slot for good)
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
#
# PERF-SEARCH-1: the request handling for POST /parse-query/ is split into small
# helpers so the streaming variant (ParseQueryStreamView) reuses EXACTLY the same
# validation, search and payload code as the blocking view. ParseQueryView's
# observable behaviour is unchanged.

def _read_prior_and_axis(request):
    """Parse prior_filters + priority_axis from the body.

    Returns (prior_filters, priority_axis, error_response_or_None)."""
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
        return prior_filters, priority_axis, Response(
            {'detail': f'priority_axis must be one of {sorted(_STRONG_AXES)}'},
            status=status.HTTP_400_BAD_REQUEST,
        )
    return prior_filters, priority_axis, None


def _rerank_body(data, prior_filters, priority_axis):
    """Branch A: DETERMINISTIC RE-RANK (chip click, priority_axis provided).

    Skip the LLM. Use prior_filters unchanged; boost chosen axis to rank 0.
    search_by_filters_scored scores the FULL publishable corpus (soft CASE WHEN
    on every axis + BM25) -> returns exactly 20 ranked results. No filter loss.
    conversation_history is NOT required on this path.
    """
    filters = dict(prior_filters)
    # image_focus may have been accumulated in prior filters; extract separately
    image_focus = filters.pop('image_focus', None)

    # Build filter_priority: chosen axis first, then remaining axes from prior.
    # Caller may send back the previous filter_priority list for ordering hints.
    prior_priority_raw = data.get('filter_priority') or []
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
    raw_query = data.get('raw_query', '') or ''

    # Score-ranked search: all prior axes present, chosen axis at rank 0.
    # search_by_filters_scored soft-scores the full corpus -> 20 results ranked
    # by all clues (chosen-axis-heavy -> partial -> others).
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

    return {
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
    }


def _validate_history(data):
    """Branch B input validation.

    conversation_history is required here — LLM call needs it.
    Accept BOTH legacy `query` string AND new `conversation_history` list.
    Returns (conversation_history, error_detail_or_None)."""
    conversation_history = data.get('conversation_history')
    query_str = data.get('query', '')
    if isinstance(query_str, str):
        query_str = query_str.strip()

    if conversation_history is not None:
        # New multi-turn path: validate it is a list
        if not isinstance(conversation_history, list) or len(conversation_history) == 0:
            return None, 'conversation_history must be a non-empty list'
        # Security: cap history depth to prevent Gemini cost amplification DoS
        _MAX_HISTORY_LEN = 10
        _MAX_TEXT_LEN = 2000
        _ALLOWED_ROLES = {'user', 'model'}
        if len(conversation_history) > _MAX_HISTORY_LEN:
            return None, f'conversation_history too long (max {_MAX_HISTORY_LEN})'
        for entry in conversation_history:
            if not isinstance(entry, dict):
                return None, 'conversation_history items must be {role, text} dicts'
            role = entry.get('role', 'user')
            if role not in _ALLOWED_ROLES:
                return None, f'invalid role; must be one of {sorted(_ALLOWED_ROLES)}'
            text = entry.get('text', '')
            if not isinstance(text, str) or len(text) > _MAX_TEXT_LEN:
                return None, f'conversation_history.text too long (max {_MAX_TEXT_LEN} chars)'
    elif query_str:
        # Legacy single-string path: wrap as single-turn history
        conversation_history = [{'role': 'user', 'text': query_str}]
    else:
        return None, 'query or conversation_history is required'
    return conversation_history, None


def _parsed_filters_and_priority(parsed):
    """Cleaned (structured_filters, filter_priority) for a parse_query() result."""
    parsed_filters = _clean_filters(parsed.get('filters') or {})
    parsed_priority = _clean_filter_priority(
        parsed.get('filter_priority') or parsed.get('priority_ordered'),
        parsed_filters,
    )
    return parsed_filters, parsed_priority


def _parse_body(parsed, conversation_history, user_id):
    """Search + payload for a parse_query() result (Branch B tail).

    Runs the scored search, spawns Stage 2 on terminal turns and returns the exact
    response body dict of POST /parse-query/ (probe or terminal shape)."""
    parsed_filters, parsed_priority = _parsed_filters_and_priority(parsed)
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
        return {
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
        }

    # IMP-6 Commit 2: spawn Stage 2 thread on terminal turn (probe_needed=False)
    # Stage 2 generates visual_description -> V_initial -> caches for SessionCreate.
    # Only fires when stage_decouple_enabled=True (default OFF).
    # Probe turns are excluded above (unstable filter set — do not spawn Stage 2).
    if RC.get('stage_decouple_enabled', False):
        _spawn_stage2(
            filters=parsed_filters,
            raw_query=raw_query,
            user_id=user_id,
        )

    # Terminal path (probe_needed=False): results already computed above.
    return {
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
    }


class ParseQueryView(APIView):
    permission_classes = [IsAuthenticated]
    throttle_classes   = [LLMSearchThrottle]

    def post(self, request):
        # ── Branch A: DETERMINISTIC RE-RANK (chip click, priority_axis provided) ─
        # Evaluated BEFORE conversation_history validation — chip-click calls omit
        # conversation_history (frontend resets it after the terminal response) so
        # validating it here would 400 every chip click.  Branch A uses prior_filters
        # + raw_query from request.data; conversation_history is not read or required.
        prior_filters, priority_axis, error = _read_prior_and_axis(request)
        if error is not None:
            return error

        if priority_axis is not None:
            return Response(_rerank_body(request.data, prior_filters, priority_axis))

        # ── Branch B: NORMAL / FREE-TEXT TURN (no priority_axis) ─────────────────
        conversation_history, detail = _validate_history(request.data)
        if detail is not None:
            return Response({'detail': detail}, status=status.HTTP_400_BAD_REQUEST)

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
        return Response(_parse_body(parsed, conversation_history, request.user.id))


# ── PERF-SEARCH-1: streaming variant (Server-Sent Events) ─────────────────────

_SSE_KEEPALIVE_SECONDS = 10
_STREAM_ERROR_DETAIL = 'Search stream failed; retry without streaming.'
_STREAM_DONE = object()


def _sse(event, data):
    """One SSE frame (bytes). `data` is JSON (DRF encoder: Decimal/datetime safe)."""
    payload = json.dumps(data, cls=JSONEncoder, ensure_ascii=False)
    return f'event: {event}\ndata: {payload}\n\n'.encode('utf-8')


class _AnyAcceptNegotiation(DefaultContentNegotiation):
    """Accept: text/event-stream must not 406 -- this view returns its own response
    (never a DRF-rendered one), so the renderer choice is irrelevant."""

    def select_renderer(self, request, renderers, format_suffix=None):
        return renderers[0], renderers[0].media_type


def _stream_worker(emit, conversation_history, language, prior_filters, user_id):
    """Run the whole parse -> search -> payload pipeline; push SSE events via emit().

    Runs in a background thread (the LLM stream is consumed here while the response
    generator drains the queue), so it owns its DB connections and closes them.
    Always ends with exactly one `final` or one `error` event.
    """
    def _on_filters_ready(partial):
        filters, priority = services.resolve_filters_from_partial(partial, prior_filters)
        cleaned = _clean_filters(filters)
        emit('filters', {
            'structured_filters': cleaned,
            'filter_priority': _clean_filter_priority(priority, cleaned),
        })

    def _on_reply_delta(text):
        emit('reply', {'text': text})

    sink = services.ParseStreamSink(
        on_filters_ready=_on_filters_ready, on_reply_delta=_on_reply_delta,
    )
    try:
        parsed = services.parse_query(
            conversation_history, language=language, prior_filters=prior_filters,
            _stream_sink=sink,
        )
        if sink.error is not None:
            # Genuine LLM failure (parse_query swallowed it into its fallback dict):
            # tell the client the LLM failed; it surfaces the error without re-running the LLM.
            emit('error', {'detail': _STREAM_ERROR_DETAIL})
            return
        if not sink.filters_emitted:
            # Gemini / non-stream fallback / non-conforming key order: derive the
            # filters event from the finished parse, just before `final`.
            parsed_filters, parsed_priority = _parsed_filters_and_priority(parsed)
            emit('filters', {
                'structured_filters': parsed_filters, 'filter_priority': parsed_priority,
            })
        emit('final', _parse_body(parsed, conversation_history, user_id))
    except Exception:  # noqa: BLE001 -- the stream must always terminate cleanly
        logger.exception('parse-query stream worker failed')
        emit('error', {'detail': _STREAM_ERROR_DETAIL})
    finally:
        _db_connections.close_all()


def _drain(q):
    """Generator over SSE bytes until the worker signals completion."""
    yield b': stream-open\n\n'
    while True:
        try:
            item = q.get(timeout=_SSE_KEEPALIVE_SECONDS)
        except queue.Empty:
            yield b': keepalive\n\n'
            continue
        if item is _STREAM_DONE:
            return
        yield _sse(*item)


def _sse_response(generator):
    response = StreamingHttpResponse(generator, content_type='text/event-stream; charset=utf-8')
    response['Cache-Control'] = 'no-cache'
    response['X-Accel-Buffering'] = 'no'
    return response


class ParseQueryStreamView(APIView):
    """POST /api/v1/parse-query/stream/ -- SSE variant of ParseQueryView (PERF-SEARCH-1).

    Same auth, throttle scope and request body as ParseQueryView. Validation errors
    are ordinary JSON 400s (before any stream starts). Events:
        filters {structured_filters, filter_priority}   as soon as the model closes them
        reply   {text}                                   incremental reply text
        final   <exact ParseQueryView response body>
        error   {detail}                                 instead of final on failure
    """
    permission_classes = [IsAuthenticated]
    throttle_classes = [LLMSearchThrottle]
    content_negotiation_class = _AnyAcceptNegotiation

    def post(self, request):
        prior_filters, priority_axis, error = _read_prior_and_axis(request)
        if error is not None:
            return error

        if priority_axis is not None:
            # Deterministic re-rank: no LLM, nothing to stream -- single `final`.
            body = _rerank_body(request.data, prior_filters, priority_axis)
            return _sse_response(iter([_sse('final', body)]))

        conversation_history, detail = _validate_history(request.data)
        if detail is not None:
            return Response({'detail': detail}, status=status.HTTP_400_BAD_REQUEST)

        # Resolve everything that touches `request` BEFORE the stream starts.
        _profile = getattr(request.user, 'profile', None)
        _lang = getattr(_profile, 'language', None)
        user_id = request.user.id

        q = queue.Queue()

        def _emit(event, data):
            q.put((event, data))

        def _run():
            try:
                _stream_worker(
                    _emit, conversation_history, _lang, prior_filters or None, user_id,
                )
            finally:
                q.put(_STREAM_DONE)

        threading.Thread(target=_run, daemon=True).start()
        return _sse_response(_drain(q))
