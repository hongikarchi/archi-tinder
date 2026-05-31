"""
parse_query.py -- Query parsing via Gemini chat phase.

Sprint 1 rewrite (Investigation 06): chat-phase + stage-decoupled (IMP-6).
M4 (Investigation 22): query complexity heuristic classifier + telemetry.

Cross-module symbol access uses the late-bound package reference (_svc) so that
mock.patch('apps.recommendation.services.X') continues to work in tests.
"""
import json
import logging
import re as _re
import time

from django.conf import settings
from django.core.cache import cache as django_cache
from google.genai import types

# ---------------------------------------------------------------------------
# Constants moved to _prompts.py (FULL-REFACTOR-1 warm-up).
# Re-imported here verbatim so every caller importing from parse_query
# continues to work unchanged (facade pattern).
# ---------------------------------------------------------------------------
from ._prompts import (  # noqa: F401
    PROGRAM_VALUES,
    REQUIRED_SLATE_FIELDS,
    REQUIRED_SLATE_PROBE_PRIORITY,
    _BROAD_SLATE_DEFAULT_FIELD,
    _BROAD_SLATE_DEFAULT_VALUE,
    _CHAT_PHASE_SYSTEM_PROMPT,
    _STYLE_TOKENS,
    _PROGRAM_TOKENS,
    _MATERIAL_TOKENS,
    _ADJECTIVE_TOKENS,
    _ALL_SPECIFICITY_TOKENS,
    _STAGE1_RESPONSE_SCHEMA,
)

logger = logging.getLogger('apps.recommendation')


def _classify_query_complexity(text: str) -> str:
    """
    M4 heuristic: classify a query string into one of four complexity classes.

    Returns:
        'brutalist'  -- >=3 specific architectural entities detected
        'narrow'     -- 1-2 specific entities (some signal but not fully determined)
        'barequery'  -- 0 specific entities (vague / generic)
        'unknown'    -- empty/None input or heuristic cannot decide

    Accuracy target: ~80% -- good enough for stratified analytics (Investigation 22
    Phase 1 Brutalist-vs-BareQuery cohort split). Not a hard classifier.

    Implementation: splits on whitespace + common delimiters; checks against
    pre-compiled vocabulary sets (style, program, material, adjective). Korean
    tokens included for bilingual corpus coverage.
    """
    if not text or not isinstance(text, str):
        return 'unknown'

    lowered = text.lower()

    # Tokenise: split on whitespace and common punctuation
    tokens = set(_re.split(r'[\s,·.!?;:\-/]+', lowered))
    tokens.discard('')

    # Count hits across all specificity token sets
    hits = sum(1 for tok in tokens if tok in _ALL_SPECIFICITY_TOKENS)

    # Also check for multi-word tokens (e.g., 'mixed use', 'rammed earth', 'critical regionalist')
    for multi_tok in ('mixed use', 'rammed earth', 'critical regionalist'):
        if multi_tok in lowered:
            hits += 1

    if hits >= 3:
        return 'brutalist'
    elif hits >= 1:
        return 'narrow'
    elif not tokens or len(tokens) <= 3:
        return 'barequery'
    else:
        return 'barequery'


def _has_required_slate(filters: dict) -> bool:
    """Return True when any downstream-useful slate field is present."""
    return any(filters.get(key) is not None for key in REQUIRED_SLATE_FIELDS)


def _normalise_filter_priority(filters: dict, raw_priority) -> list:
    """Keep valid non-null keys and promote required slate keys to the front.

    Gemini occasionally emits a useful required-slate filter but forgets to list
    it in `filter_priority`, or lists only `year_min`. Downstream pool creation
    treats `filter_priority` as a weight vector, so the slate field must be
    visible there too.
    """
    priority = []
    for key in REQUIRED_SLATE_PROBE_PRIORITY:
        if filters.get(key) is not None and key not in priority:
            priority.append(key)
    for key in raw_priority or []:
        if isinstance(key, str) and filters.get(key) is not None and key not in priority:
            priority.append(key)
    return priority


def _repair_required_slate(filters: dict, raw_priority) -> tuple[dict, list]:
    """Ensure successful LLM payloads do not leave the parser slate-empty."""
    if not _has_required_slate(filters):
        filters[_BROAD_SLATE_DEFAULT_FIELD] = _BROAD_SLATE_DEFAULT_VALUE
    return filters, _normalise_filter_priority(filters, raw_priority)


def parse_query(conversation_history):
    """
    Chat phase Gemini call (Sprint 1 rewrite per Investigation 06).

    IMP-6 Commit 2: when stage_decouple_enabled=True, routes to parse_query_stage1()
    which omits visual_description (Stage 2 generates it async). When flag is OFF,
    runs the original single-call full-output path.

    Input:
        conversation_history: list of {role: 'user'|'model', text: str} dicts,
            representing the full chat so far. Oldest turn first.
        Backward compat: if a bare string is passed (legacy caller), it is wrapped
            as [{'role': 'user', 'text': conversation_history}].

    Returns one of:

    Interim probe (probe_needed=True):
        {
            'probe_needed': True,
            'probe_question': str,      # verbal A-vs-B question in user's locale
            'reply': str,               # short ack in user's locale
            'filters': dict,            # partial filters inferred so far
            'filter_priority': list,
            'raw_query': str,           # first user turn verbatim
            'visual_description': None, # not yet finalised
        }

    Terminal response (probe_needed=False):
        {
            'probe_needed': False,
            'probe_question': None,
            'reply': str,               # rich paraphrase confirm in user's locale
            'filters': dict,            # all inferable SQL-WHERE predicates
            'filter_priority': list,    # ordered by essentialness
            'raw_query': str,           # first user turn verbatim
            'visual_description': str,  # English, 2-4 sentences, HyDE V_initial seed
                                        # (None when stage_decouple_enabled=True -- Stage 2)
        }

    Failure path (spec §5.4 graceful degradation):
        {
            'probe_needed': False,
            'probe_question': None,
            'reply': '이해를 잘 못 했어요. 일단 이 쪽으로 찾아볼게요.',
            'filters': {...all null},
            'filter_priority': [],
            'raw_query': <first user message verbatim>,
            'visual_description': None,
        }
        Also emits a 'failure' session event (spec §6).
    """
    # Late-bound package reference for cross-module symbol access.
    # mock.patch('apps.recommendation.services.X') modifies this module object;
    # _svc.X reads from it at call time -- patches are visible here.
    from apps.recommendation import services as _svc  # noqa: PLC0415

    # IMP-6: when stage_decouple_enabled=True, delegate to Stage 1 (visual_description
    # is generated asynchronously by Stage 2 thread spawned in ParseQueryView).
    # Use _svc.parse_query_stage1 so mock.patch/patch.object on services.parse_query_stage1
    # is visible here at call time (late-bound via the module object).
    if settings.RECOMMENDATION.get('stage_decouple_enabled', False):
        return _svc.parse_query_stage1(conversation_history)
    # else: fall through to the original single-call path (default, backward compat)
    # Backward compat: accept bare string (legacy callers pass query_text directly)
    if isinstance(conversation_history, str):
        conversation_history = [{'role': 'user', 'text': conversation_history}]

    # Extract first user message verbatim (BM25 raw_query channel)
    first_user_text = ''
    for turn in conversation_history:
        if turn.get('role') == 'user':
            first_user_text = turn.get('text', '')
            break

    _empty_filters = {
        'location_country': None, 'location_city': None,
        'program': None, 'material': None, 'style': None,
        'year_min': None, 'year_max': None,
    }
    _fallback = {
        'probe_needed': False,
        'probe_question': None,
        'reply': '이해를 잘 못 했어요. 일단 이 쪽으로 찾아볼게요.',
        'filters': dict(_empty_filters),
        'filter_priority': [],
        'image_focus': None,
        'raw_query': first_user_text,
        'visual_description': None,
    }

    try:
        client = _svc._get_client()
        rc = settings.RECOMMENDATION

        # Build Gemini contents list from conversation_history
        contents = []
        for turn in conversation_history:
            role = turn.get('role', 'user')
            text = turn.get('text', '')
            contents.append(
                types.Content(role=role, parts=[types.Part.from_text(text=text)])
            )

        # IMP-5: explicit context caching branch (flag-gated, default OFF)
        caching_enabled = rc.get('context_caching_enabled', False)
        cache_resource_name = None
        if caching_enabled:
            cache_resource_name = _svc._ensure_chat_cache(client)

        if cache_resource_name:
            # Cached path: supply cached_content= instead of system_instruction=
            def _call():
                return client.models.generate_content(
                    model='gemini-2.5-flash',
                    contents=contents,
                    config=types.GenerateContentConfig(
                        cached_content=cache_resource_name,
                        response_mime_type='application/json',
                        temperature=0.2,
                        thinking_config=types.ThinkingConfig(thinking_budget=0),
                    ),
                )
        else:
            # Uncached path: original behaviour, backward-compatible
            def _call():  # noqa: F811
                return client.models.generate_content(
                    model='gemini-2.5-flash',
                    contents=contents,
                    config=types.GenerateContentConfig(
                        system_instruction=_CHAT_PHASE_SYSTEM_PROMPT,
                        response_mime_type='application/json',
                        temperature=0.2,
                        thinking_config=types.ThinkingConfig(thinking_budget=0),
                    ),
                )

        t_call_start = time.perf_counter()
        try:
            response = _svc._retry_gemini_call(_call)
        except Exception as _cache_exc:
            # IMP-5: if call failed with 404/NOT_FOUND it means the Gemini cache
            # has expired but the Django cache entry is still live (TTL skew).
            # Evict Django entry, clear cache_resource_name, and retry uncached.
            exc_str = str(_cache_exc)
            if cache_resource_name and ('404' in exc_str or 'NOT_FOUND' in exc_str):
                logger.warning(
                    'IMP-5: Gemini cache 404 for %s -- evicting Django entry and retrying uncached',
                    cache_resource_name,
                )
                django_cache.delete(_svc._get_django_cache_key())
                cache_resource_name = None

                def _call_uncached():
                    return client.models.generate_content(
                        model='gemini-2.5-flash',
                        contents=contents,
                        config=types.GenerateContentConfig(
                            system_instruction=_CHAT_PHASE_SYSTEM_PROMPT,
                            response_mime_type='application/json',
                            temperature=0.2,
                            thinking_config=types.ThinkingConfig(thinking_budget=0),
                        ),
                    )
                response = _svc._retry_gemini_call(_call_uncached)
            else:
                raise
        t_call_end = time.perf_counter()

        # Emit parse_query.timing event (spec §6 + §11.1 IMP-4 mandatory companion).
        # Must be emitted before json.loads so parse failures still produce a timing record.
        # IMP-5: extend with 4 new fields (additive -- existing field names unchanged).
        # M4 (Investigation 22): pre-parse probe_needed to populate clarification_fired
        #     without changing the "timing always emits when Gemini responds" invariant.
        #     Pre-parse is best-effort: on decode failure it defaults to None.
        _usage = getattr(response, 'usage_metadata', None)
        _raw_cached = getattr(_usage, 'cached_content_token_count', None) if _usage else None
        # Guard: only accept int/float to avoid MagicMock or other non-serialisable types
        _cached_token_count = int(_raw_cached) if isinstance(_raw_cached, (int, float)) else None
        _cache_hit = (_cached_token_count > 0) if _cached_token_count is not None else None

        # M4: best-effort pre-parse for clarification_fired (does NOT replace the
        # main json.loads below -- that one raises and is caught by the outer except).
        _clarification_fired = None  # None = unknown (Gemini error or pre-parse failure)
        try:
            _pre_data = json.loads(response.text)
            _clarification_fired = bool(_pre_data.get('probe_needed', False))
        except Exception:
            pass  # main json.loads below will surface the error via the except handler

        # M4: classify the user's query text for stratified analytics
        _query_complexity_class = _classify_query_complexity(first_user_text)

        # M1 (Investigation 22 §M1 refined): compute user-turn count for cap telemetry.
        # Cap fires when user_turn_count >= 3 AND Gemini returned probe_needed=True.
        # Bare-string callers are wrapped to a 1-element list above, so count is always 1
        # there and the cap never fires -- backward compat is automatic.
        _user_turn_count = sum(1 for t in conversation_history if t.get('role') == 'user')
        _m1_cap_forced_terminal = bool(
            _user_turn_count >= 3 and _clarification_fired is True
        )

        _svc.event_log.emit_event(
            'parse_query_timing',
            session=None,
            user=None,
            gemini_total_ms=round((t_call_end - t_call_start) * 1000, 2),
            ttft_ms=None,   # not available without streaming
            gen_ms=round((t_call_end - t_call_start) * 1000, 2),
            input_tokens=getattr(_usage, 'prompt_token_count', None) if _usage else None,
            output_tokens=getattr(_usage, 'candidates_token_count', None) if _usage else None,
            thinking_tokens=getattr(_usage, 'thoughts_token_count', None) if _usage else None,
            # IMP-5 fields (additive)
            cache_hit=_cache_hit,
            cached_input_tokens=_cached_token_count,
            cache_name_hash=_svc._get_prompt_hash() if cache_resource_name else None,
            caching_mode='explicit' if cache_resource_name else 'none',
            # M4 fields (additive, Investigation 22 §M4 + IMP-10 sub-task A continuation)
            clarification_fired=_clarification_fired,
            query_complexity_class=_query_complexity_class,
            # M1 field (Investigation 22 §M1 refined): True iff Python-level cap overrode
            # Gemini's probe_needed=True on user turn 3+. Observable cap-fire-rate metric.
            m1_cap_forced_terminal=_m1_cap_forced_terminal,
        )

        data = json.loads(response.text)

        probe_needed = bool(data.get('probe_needed', False))

        # M1 (Investigation 22 §M1 refined): Python-level runaway-clarification cap.
        # If user_turn_count >= 3 AND Gemini still returned probe_needed=True, force
        # terminal mode. This is defense-in-depth: the prompt HARD CAP clause should
        # prevent Gemini from firing a 3rd probe, but Python enforces it regardless.
        # Cap fires ONLY at turn 3+ -- turns 1 and 2 are legitimate 0/1-turn flows per
        # Investigation 06's design intent. Always-on; no flag gate.
        if _user_turn_count >= 3 and probe_needed:
            logger.warning(
                'parse_query: Gemini returned probe_needed=True on user turn %d (>=3); '
                'forcing probe_needed=False per Investigation 22 M1 cap',
                _user_turn_count,
            )
            probe_needed = False

        # Sanitize program value (case-insensitive -> canonical form)
        filters = data.get('filters') or dict(_empty_filters)
        if filters.get('program'):
            program = filters['program']
            if program not in PROGRAM_VALUES:
                titled = program.title()
                filters['program'] = titled if titled in PROGRAM_VALUES else None

        # Sanitize/repair filter_priority: keep only non-null filter keys, but
        # never let a successful Gemini payload proceed without any required
        # slate field. Diffuse prompts get a broad Contemporary default.
        raw_priority = data.get('filter_priority') or []
        filters, filter_priority = _repair_required_slate(filters, raw_priority)

        # raw_query: spec §3 says always verbatim first user message
        raw_query = data.get('raw_query') or first_user_text

        image_focus = data.get('image_focus')
        if image_focus not in ('exterior', 'interior', 'drawing', 'aerial', 'detail'):
            image_focus = None

        result = {
            'probe_needed': probe_needed,
            'probe_question': data.get('probe_question') if probe_needed else None,
            'reply': data.get('reply', ''),
            'filters': filters,
            'filter_priority': filter_priority,
            'image_focus': image_focus,
            'raw_query': raw_query,
            'visual_description': data.get('visual_description'),
        }
        return result

    except json.JSONDecodeError as e:
        logger.error('parse_query JSON decode error: %s', e)
        _svc.event_log.emit_event(
            'failure',
            session=None,
            user=None,
            failure_type='gemini_parse',
            recovery_path='fallback_diverse_random',
            error_class='JSONDecodeError',
            error_message=str(e)[:200],
        )
        return _fallback
    except Exception as e:
        logger.error('parse_query failed after retries: %s: %s', type(e).__name__, e)
        _svc.event_log.emit_event(
            'failure',
            session=None,
            user=None,
            failure_type='gemini_parse',
            recovery_path='fallback_diverse_random',
            error_class=type(e).__name__,
            error_message=str(e)[:200],
        )
        return _fallback


def parse_query_stage1(conversation_history):
    """IMP-6 Commit 2: Stage 1 Gemini call -- USER-BLOCKING portion of the split.

    Same as parse_query() but uses response_schema to exclude visual_description,
    reducing output tokens from ~290-400 to ~150-220. Returns same dict shape as
    parse_query() but with visual_description=None always.

    When stage_decouple_enabled=False, this function is not called directly;
    parse_query() (the legacy wrapper) handles routing.

    Emits parse_query_timing with stage='1' field added (additive -- all existing
    fields preserved per spec v1.7).

    Args:
        conversation_history: list of {role, text} dicts or bare string (backward compat).

    Returns:
        Same dict shape as parse_query(), with visual_description always None.
        On failure: graceful degradation fallback dict (same as parse_query).
    """
    # Late-bound package reference (same rationale as parse_query above)
    from apps.recommendation import services as _svc  # noqa: PLC0415

    # Backward compat: accept bare string (legacy callers pass query_text directly)
    if isinstance(conversation_history, str):
        conversation_history = [{'role': 'user', 'text': conversation_history}]

    # Extract first user message verbatim (BM25 raw_query channel)
    first_user_text = ''
    for turn in conversation_history:
        if turn.get('role') == 'user':
            first_user_text = turn.get('text', '')
            break

    _empty_filters = {
        'location_country': None, 'location_city': None,
        'program': None, 'material': None, 'style': None,
        'year_min': None, 'year_max': None,
    }
    _fallback = {
        'probe_needed': False,
        'probe_question': None,
        'reply': '이해를 잘 못 했어요. 일단 이 쪽으로 찾아볼게요.',
        'filters': dict(_empty_filters),
        'filter_priority': [],
        'image_focus': None,
        'raw_query': first_user_text,
        'visual_description': None,
    }

    try:
        client = _svc._get_client()
        rc = settings.RECOMMENDATION

        # Build Gemini contents list from conversation_history
        contents = []
        for turn in conversation_history:
            role = turn.get('role', 'user')
            text = turn.get('text', '')
            contents.append(
                types.Content(role=role, parts=[types.Part.from_text(text=text)])
            )

        # IMP-5: explicit context caching branch (flag-gated, default OFF)
        caching_enabled = rc.get('context_caching_enabled', False)
        cache_resource_name = None
        if caching_enabled:
            cache_resource_name = _svc._ensure_chat_cache(client)

        if cache_resource_name:
            # Cached path: supply cached_content= instead of system_instruction=
            # response_schema excludes visual_description -> reduced output tokens
            def _call():
                return client.models.generate_content(
                    model='gemini-2.5-flash',
                    contents=contents,
                    config=types.GenerateContentConfig(
                        cached_content=cache_resource_name,
                        response_mime_type='application/json',
                        response_schema=_STAGE1_RESPONSE_SCHEMA,
                        temperature=0.2,
                        thinking_config=types.ThinkingConfig(thinking_budget=0),
                    ),
                )
        else:
            # Uncached path: original system_instruction + Stage 1 schema
            def _call():  # noqa: F811
                return client.models.generate_content(
                    model='gemini-2.5-flash',
                    contents=contents,
                    config=types.GenerateContentConfig(
                        system_instruction=_CHAT_PHASE_SYSTEM_PROMPT,
                        response_mime_type='application/json',
                        response_schema=_STAGE1_RESPONSE_SCHEMA,
                        temperature=0.2,
                        thinking_config=types.ThinkingConfig(thinking_budget=0),
                    ),
                )

        t_call_start = time.perf_counter()
        try:
            response = _svc._retry_gemini_call(_call)
        except Exception as _cache_exc:
            # IMP-5: if call failed with 404/NOT_FOUND (Gemini cache expired but Django
            # cache still live), evict Django entry and retry uncached.
            exc_str = str(_cache_exc)
            if cache_resource_name and ('404' in exc_str or 'NOT_FOUND' in exc_str):
                logger.warning(
                    'IMP-5: Gemini cache 404 for %s -- evicting Django entry and retrying uncached',
                    cache_resource_name,
                )
                django_cache.delete(_svc._get_django_cache_key())
                cache_resource_name = None

                def _call_uncached():
                    return client.models.generate_content(
                        model='gemini-2.5-flash',
                        contents=contents,
                        config=types.GenerateContentConfig(
                            system_instruction=_CHAT_PHASE_SYSTEM_PROMPT,
                            response_mime_type='application/json',
                            response_schema=_STAGE1_RESPONSE_SCHEMA,
                            temperature=0.2,
                            thinking_config=types.ThinkingConfig(thinking_budget=0),
                        ),
                    )
                response = _svc._retry_gemini_call(_call_uncached)
            else:
                raise
        t_call_end = time.perf_counter()

        # --- Telemetry (same as parse_query, additive stage='1' field per spec v1.7) ---
        _usage = getattr(response, 'usage_metadata', None)
        _raw_cached = getattr(_usage, 'cached_content_token_count', None) if _usage else None
        _cached_token_count = int(_raw_cached) if isinstance(_raw_cached, (int, float)) else None
        _cache_hit = (_cached_token_count > 0) if _cached_token_count is not None else None

        _clarification_fired = None
        try:
            _pre_data = json.loads(response.text)
            _clarification_fired = bool(_pre_data.get('probe_needed', False))
        except Exception:
            pass

        _query_complexity_class = _classify_query_complexity(first_user_text)
        _user_turn_count = sum(1 for t in conversation_history if t.get('role') == 'user')
        _m1_cap_forced_terminal = bool(_user_turn_count >= 3 and _clarification_fired is True)

        _svc.event_log.emit_event(
            'parse_query_timing',
            session=None,
            user=None,
            gemini_total_ms=round((t_call_end - t_call_start) * 1000, 2),
            ttft_ms=None,
            gen_ms=round((t_call_end - t_call_start) * 1000, 2),
            input_tokens=getattr(_usage, 'prompt_token_count', None) if _usage else None,
            output_tokens=getattr(_usage, 'candidates_token_count', None) if _usage else None,
            thinking_tokens=getattr(_usage, 'thoughts_token_count', None) if _usage else None,
            # IMP-5 fields
            cache_hit=_cache_hit,
            cached_input_tokens=_cached_token_count,
            cache_name_hash=_svc._get_prompt_hash() if cache_resource_name else None,
            caching_mode='explicit' if cache_resource_name else 'none',
            # M4 fields
            clarification_fired=_clarification_fired,
            query_complexity_class=_query_complexity_class,
            # M1 field
            m1_cap_forced_terminal=_m1_cap_forced_terminal,
            # IMP-6 Commit 2 additive field: stage identifier
            stage='1',
        )

        data = json.loads(response.text)
        probe_needed = bool(data.get('probe_needed', False))

        # M1 cap: Python-level runaway-clarification guard (same as parse_query)
        if _user_turn_count >= 3 and probe_needed:
            logger.warning(
                'parse_query_stage1: Gemini returned probe_needed=True on user turn %d (>=3); '
                'forcing probe_needed=False per Investigation 22 M1 cap',
                _user_turn_count,
            )
            probe_needed = False

        # Sanitize program value
        filters = data.get('filters') or dict(_empty_filters)
        if filters.get('program'):
            program = filters['program']
            if program not in PROGRAM_VALUES:
                titled = program.title()
                filters['program'] = titled if titled in PROGRAM_VALUES else None

        # Sanitize/repair filter_priority: keep only non-null filter keys, but
        # never let a successful Gemini payload proceed without any required
        # slate field. Diffuse prompts get a broad Contemporary default.
        raw_priority = data.get('filter_priority') or []
        filters, filter_priority = _repair_required_slate(filters, raw_priority)

        # raw_query: spec §3 says always verbatim first user message
        raw_query = data.get('raw_query') or first_user_text

        image_focus = data.get('image_focus')
        if image_focus not in ('exterior', 'interior', 'drawing', 'aerial', 'detail'):
            image_focus = None

        return {
            'probe_needed': probe_needed,
            'probe_question': data.get('probe_question') if probe_needed else None,
            'reply': data.get('reply', ''),
            'filters': filters,
            'filter_priority': filter_priority,
            'image_focus': image_focus,
            'raw_query': raw_query,
            'visual_description': None,  # Stage 2 generates this asynchronously
        }

    except json.JSONDecodeError as e:
        logger.error('parse_query_stage1 JSON decode error: %s', e)
        _svc.event_log.emit_event(
            'failure',
            session=None,
            user=None,
            failure_type='gemini_parse',
            recovery_path='fallback_diverse_random',
            error_class='JSONDecodeError',
            error_message=str(e)[:200],
        )
        return _fallback
    except Exception as e:
        logger.error('parse_query_stage1 failed after retries: %s: %s', type(e).__name__, e)
        _svc.event_log.emit_event(
            'failure',
            session=None,
            user=None,
            failure_type='gemini_parse',
            recovery_path='fallback_diverse_random',
            error_class=type(e).__name__,
            error_message=str(e)[:200],
        )
        return _fallback
