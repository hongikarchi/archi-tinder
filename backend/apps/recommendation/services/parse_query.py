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
    _CALIBRATION_PROMPT_EXTENSION,
    _STYLE_TOKENS,
    _PROGRAM_TOKENS,
    _MATERIAL_TOKENS,
    _ADJECTIVE_TOKENS,
    _ALL_SPECIFICITY_TOKENS,
    _STAGE1_RESPONSE_SCHEMA,
    build_vocab_prompt_block,
)

logger = logging.getLogger('apps.recommendation')

# FULL-LANGUAGE-1: per-user language override directive injected into system_instruction.
# Scoped to `reply` and `probe_question` only.
# Does NOT override rule 3 (visual_description ALWAYS English) or rule 4 (raw_query verbatim).
# language=None (default) leaves current inference-from-message behaviour intact.
_LANG_DIRECTIVE = {
    'ko': (
        '\n\n## Language override (user preference)\n'
        'The user has set their language preference to Korean. '
        'Write `reply` and `probe_question` in Korean regardless of the language of their message. '
        '`visual_description` remains English (rule 3). `raw_query` is verbatim (rule 4).'
    ),
    'en': (
        '\n\n## Language override (user preference)\n'
        'The user has set their language preference to English. '
        'Write `reply` and `probe_question` in English regardless of the language of their message. '
        '`visual_description` remains English (rule 3). `raw_query` is verbatim (rule 4).'
    ),
}


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


# ---------------------------------------------------------------------------
# BACK-PARSER-VOCAB-1: snap the 5 grounded soft axes to live DB vocabulary.
# ---------------------------------------------------------------------------
_SNAP_AXES = ('style', 'atmosphere', 'color_tone', 'typology_primary', 'architectural_elements')


def _snap_to_vocab(filters: dict) -> dict:
    """Normalise style/atmosphere/color_tone/typology_primary/architectural_elements
    to the canonical DB casing, or None when unmappable.

    Resolution order per axis (first match wins):
      1. Exact match against the live vocab list -- returned unchanged.
      2. Case-insensitive (casefold) match -- returns the CANONICAL DB casing.
      3. style only: variant repair (value.replace('ism', 'ist')), then a
         casefold retry against the repaired string (e.g. 'Brutalism' ->
         'Brutalist', 'Modernism' -> 'Modernist').
      4. Title-case retry (e.g. 'contemporary house' style shouldn't hit this,
         but odd casing like 'BRUTALIST' does).
      5. None (unmappable -- the caller's downstream code treats this as if
         Gemini had returned null for the axis).

    Never raises. Leaves `program` untouched (PROGRAM_VALUES logic elsewhere
    already handles that axis). Values that are already None, non-string, or
    empty are left as None; missing axis keys are not added.
    """
    from apps.recommendation import services as _svc  # noqa: PLC0415

    try:
        vocab = _svc.get_axis_vocab() or {}
    except Exception:
        logger.warning('_snap_to_vocab: get_axis_vocab() failed; skipping snap', exc_info=True)
        return filters

    result = dict(filters)
    for axis in _SNAP_AXES:
        if axis not in result:
            continue
        value = result[axis]
        if value is None or not isinstance(value, str) or not value.strip():
            continue

        allowed = vocab.get(axis) or []
        if not allowed:
            # No live/snapshot vocab for this axis at all -- leave value as-is
            # rather than nulling out a possibly-valid value on a data outage.
            continue

        if value in allowed:
            continue  # exact match -- already canonical

        snapped = None
        value_cf = value.casefold()
        for candidate in allowed:
            if candidate.casefold() == value_cf:
                snapped = candidate
                break

        if snapped is None and axis == 'style':
            # Casefold BEFORE the ism->ist repair so all-caps variants
            # ('MODERNISM', 'BRUTALISM') resolve too.
            repaired_cf = value_cf.replace('ism', 'ist')
            for candidate in allowed:
                if candidate.casefold() == repaired_cf:
                    snapped = candidate
                    break

        if snapped is None:
            titled = value.title()
            for candidate in allowed:
                if candidate == titled or candidate.casefold() == titled.casefold():
                    snapped = candidate
                    break

        result[axis] = snapped  # None when nothing matched

    return result


def _compute_confidence_fallback(filters: dict, probe_needed: bool) -> float:
    """TASTE-CALIBRATION-1: compute confidence_score when LLM did not return one.

    Uses required-slate field coverage as a proxy:
    - probe_needed=True and 0 slate fields: 0.20
    - probe_needed=True and >=1 slate field: 0.45
    - probe_needed=False and 0 slate fields: 0.55  (broad fallback)
    - probe_needed=False and 1 slate field: 0.65
    - probe_needed=False and 2+ slate fields: 0.80

    These thresholds are calibrated so that probe_needed=True reliably maps
    below the 0.60 threshold and probe_needed=False maps above it.
    """
    slate_count = sum(
        1 for key in REQUIRED_SLATE_FIELDS if filters.get(key) is not None
    )
    if probe_needed:
        return 0.20 if slate_count == 0 else 0.45
    else:
        if slate_count == 0:
            return 0.55
        elif slate_count == 1:
            return 0.65
        else:
            return 0.80


def _extract_calibration_fields(data: dict, filters: dict, probe_needed: bool) -> dict:
    """TASTE-CALIBRATION-1: extract + validate all calibration output fields from LLM data.

    Returns a dict with keys: confidence_score, system_action, suggested_quick_replies,
    priority_ordered, llm_response_message.  Falls back gracefully when any field is absent.
    """
    # confidence_score: float 0-1, fall back to heuristic
    raw_confidence = data.get('confidence_score')
    if isinstance(raw_confidence, (int, float)) and 0.0 <= raw_confidence <= 1.0:
        confidence_score = float(raw_confidence)
    else:
        confidence_score = _compute_confidence_fallback(filters, probe_needed)

    # system_action: validate against allowed enum values
    _valid_actions = ('REQUEST_PRIORITY', 'CONFIRM_SELECTION', 'NONE')
    raw_action = data.get('system_action')
    if raw_action in _valid_actions:
        system_action = raw_action
    elif confidence_score < 0.60:
        system_action = 'REQUEST_PRIORITY'
    else:
        system_action = 'NONE'

    # suggested_quick_replies: list of structured chips {label, axis, value} or plain
    # strings.  Drop any chip whose axis is not a valid priority axis — this removes
    # the defunct skip chip ("상관없으니 카드 보여주세요" / "Just show me cards") and
    # prevents the "priority_axis must be one of [...]" 400 if an invalid-axis chip is
    # ever clicked.  Plain strings (no axis) are also dropped since they cannot be sent
    # back as a priority_axis.  The deterministic _build_axis_chips path (D1) always
    # produces valid-axis dicts and is unaffected — it overwrites this list downstream.
    raw_replies = data.get('suggested_quick_replies') or []
    if isinstance(raw_replies, list):
        suggested_quick_replies = [
            r for r in raw_replies
            if isinstance(r, dict) and r.get('axis') in _STRONG_AXES
        ][:3]
    else:
        suggested_quick_replies = []

    # priority_ordered: list[str]
    raw_priority_ordered = data.get('priority_ordered') or []
    if isinstance(raw_priority_ordered, list):
        priority_ordered = [k for k in raw_priority_ordered if isinstance(k, str)]
    else:
        priority_ordered = []

    # llm_response_message: string (fall back to reply or probe_question)
    raw_msg = data.get('llm_response_message')
    if isinstance(raw_msg, str) and raw_msg.strip():
        llm_response_message = raw_msg.strip()
    else:
        llm_response_message = data.get('probe_question') or data.get('reply') or ''

    return {
        'confidence_score': confidence_score,
        'system_action': system_action,
        'suggested_quick_replies': suggested_quick_replies,
        'priority_ordered': priority_ordered,
        'llm_response_message': llm_response_message,
    }


_STRONG_AXES = frozenset({
    'program', 'location_country', 'location_city',
    'style', 'material', 'atmosphere', 'typology_primary',
})

# D1: localised axis label map for priority-question chip generation
_AXIS_LABEL_KO = {
    'program': '프로그램',
    'location_country': '위치',
    'location_city': '위치',
    'style': '스타일',
    'material': '재료',
    'atmosphere': '분위기',
    'typology_primary': '유형',
}


def _build_axis_chips(filters):
    """Build structured chip objects for all present strong axes.

    Returns a list of dicts: {label, axis, value}.  One chip per present
    strong axis.  The ``axis`` field is the canonical filter key so the
    frontend can send it back as ``priority_axis`` without any string parsing.
    The ``label`` field is the Korean-localised display string with the value
    appended, e.g. ``재료(brick)``.
    """
    chips = []
    for ax in _STRONG_AXES:
        if filters.get(ax) is not None and str(filters[ax]).strip():
            label_text = _AXIS_LABEL_KO.get(ax, ax)
            val = filters[ax]
            chips.append({
                'label': f'{label_text}({val})',
                'axis': ax,
                'value': val,
            })
    return chips


def _maybe_multi_axis_probe(filters, filter_priority, user_turn_count, parsed_result):
    """D1: inject an optional priority prompt when >=2 strong axes are present (NON-BLOCKING).

    Results are always shown immediately (probe_needed stays False). When n_strong >= 2
    on a terminal response, this function augments the result with:
      - system_action = 'REQUEST_PRIORITY'
      - llm_response_message = short Korean criteria-priority question
      - suggested_quick_replies = list of chip objects {label, axis, value}, one per axis

    No skip chip is added — results are already shown so no "skip" action is needed.

    Fires on ANY terminal turn (turn-agnostic) when n_strong >= 2.
    When probe_needed=True (genuine slate probe) or n_strong < 2: returns unchanged.
    """
    # Only augment terminal responses — never touch genuine probes
    if parsed_result.get('probe_needed'):
        return parsed_result

    present_strong = [
        ax for ax in _STRONG_AXES
        if filters.get(ax) is not None and str(filters[ax]).strip()
    ]
    if len(present_strong) < 2:
        return parsed_result

    # Build the secondary question (shown below results, not as a blocking screen)
    priority_q = '추천에 더 중요하게 생각할 기준이 있나요?'

    # Build one structured chip object per present strong axis — no skip chip
    chips = _build_axis_chips(filters)

    result = dict(parsed_result)
    # probe_needed stays False — results are returned immediately
    result['llm_response_message'] = priority_q
    result['system_action'] = 'REQUEST_PRIORITY'
    result['suggested_quick_replies'] = chips
    # priority_ordered: existing value stays (filter_priority ordering from LLM)
    return result


def parse_query(conversation_history, language=None, prior_filters=None):
    """
    Chat phase Gemini call (Sprint 1 rewrite per Investigation 06).

    IMP-6 Commit 2: when stage_decouple_enabled=True, routes to parse_query_stage1()
    which omits visual_description (Stage 2 generates it async). When flag is OFF,
    runs the original single-call full-output path.

    Input:
        conversation_history: list of {role: 'user'|'model', text: str} dicts,
            representing the full chat so far. Oldest turn first.
        language: optional 'ko' or 'en' (UserProfile.language). When set, forces
            `reply` and `probe_question` to that language regardless of message language.
            None (default) keeps the infer-from-message behaviour.
        prior_filters: optional dict of accumulated filters from previous turns.
            When provided, injected into the Gemini request as context so the LLM
            can return a filter_delta (set/remove) instead of a full filters dict.
            The final filters are computed deterministically:
            final = prior_filters + delta.set - delta.remove.
            None (default) = first turn, no prior context.
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
        return _svc.parse_query_stage1(
            conversation_history, language=language, prior_filters=prior_filters,
        )
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
        'atmosphere': None, 'color_tone': None, 'typology_primary': None,
        'architectural_elements': None,
    }
    _fallback = {
        'probe_needed': False,
        'probe_question': None,
        'reply': '이해를 잘 못 했어요. 일단 이 쪽으로 찾아볼게요.',
        'filters': dict(_empty_filters),
        'filter_delta': {'set': {}, 'remove': []},
        'filter_priority': [],
        'image_focus': None,
        'raw_query': first_user_text,
        'visual_description': None,
        # TASTE-CALIBRATION-1 fallback defaults
        'confidence_score': 0.55,
        'system_action': 'NONE',
        'suggested_quick_replies': [],
        'priority_ordered': [],
        'llm_response_message': '이해를 잘 못 했어요. 일단 이 쪽으로 찾아볼게요.',
    }

    # FULL-LANGUAGE-1: compute augmented system instruction once for all sites below.
    # language=None -> no directive (infer from message, existing behaviour).
    # TASTE-CALIBRATION-1: always append calibration extension to inject confidence fields.
    # BACK-PARSER-VOCAB-1: also append the live-DB "Allowed <axis> values" grounding
    # block for style/atmosphere/color_tone/typology_primary/architectural_elements.
    # get_axis_vocab() never raises (falls back to _VOCAB_SNAPSHOT), so this is safe
    # to call unconditionally. IMP-5 note: this string (including the vocab block)
    # is what would be hashed/cached if _get_prompt_hash read _system_instruction --
    # today it hashes the static _CHAT_PHASE_SYSTEM_PROMPT only, and the cached-content
    # path below (context_caching_enabled, default OFF) intentionally keeps caching the
    # static prompt (caching logic in _caches.py is algorithm-owned, untouched here);
    # the vocab block flows into system_instruction= on the (default) uncached path,
    # exactly like the language directive does today.
    _vocab_block = build_vocab_prompt_block(_svc.get_axis_vocab())
    _system_instruction = (
        _CHAT_PHASE_SYSTEM_PROMPT + _CALIBRATION_PROMPT_EXTENSION + _vocab_block
        + _LANG_DIRECTIVE[language]
        if language in _LANG_DIRECTIVE
        else _CHAT_PHASE_SYSTEM_PROMPT + _CALIBRATION_PROMPT_EXTENSION + _vocab_block
    )

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

        # FILTER-DELTA: inject prior_filters as a system-side context line so the
        # LLM knows the accumulated filter state and can return only the delta.
        # Appended as a trailing 'user' turn so it rides after the conversation
        # history but before the model responds. The model's instructions tell it
        # to output filter_delta (set/remove) when this context line is present.
        if prior_filters:
            import json as _json
            _prior_ctx = (
                f'현재까지 확정된 필터(JSON): {_json.dumps(prior_filters, ensure_ascii=False)}'
                f' — 사용자의 새 메시지는 이걸 다듬는 변경(델타)이다.'
            )
            contents.append(
                types.Content(role='user', parts=[types.Part.from_text(text=_prior_ctx)])
            )

        # IMP-5: explicit context caching branch (flag-gated, default OFF)
        # BACK-LLM-PROVIDER-1: Gemini explicit context caching (_ensure_chat_cache)
        # is a genai-only API surface (client.caches.create) -- gate it off on the
        # openai path so an openai.OpenAI client is never handed to it. The flag is
        # OFF by default regardless, so this guard only matters if a deployment
        # ever flips context_caching_enabled=True while LLM_PROVIDER=openai.
        caching_enabled = rc.get('context_caching_enabled', False) and settings.LLM_PROVIDER == 'gemini'
        cache_resource_name = None
        if caching_enabled:
            cache_resource_name = _svc._ensure_chat_cache(client)

        if cache_resource_name:
            # Cached path: supply cached_content= instead of system_instruction=
            # Note: cached_content and system_instruction are mutually exclusive.
            # The language directive is per-user (dynamic), so it cannot be baked
            # into the static cache. When caching is enabled and a language directive
            # is set, the directive is lost on the cached path -- this is an accepted
            # limitation since context_caching_enabled defaults to OFF.
            _cached_config = types.GenerateContentConfig(
                cached_content=cache_resource_name,
                response_mime_type='application/json',
                temperature=0.2,
                thinking_config=types.ThinkingConfig(thinking_budget=settings.GEMINI_THINKING_BUDGET),
            )
        else:
            # Uncached path: inject language directive via augmented system_instruction.
            _cached_config = types.GenerateContentConfig(
                system_instruction=_system_instruction,
                response_mime_type='application/json',
                temperature=0.2,
                thinking_config=types.ThinkingConfig(thinking_budget=settings.GEMINI_THINKING_BUDGET),
            )

        t_call_start = time.perf_counter()
        try:
            response = _svc.generate_content_with_fallback(
                client,
                contents=contents,
                config=_cached_config,
            )
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
                response = _svc.generate_content_with_fallback(
                    client,
                    contents=contents,
                    config=types.GenerateContentConfig(
                        system_instruction=_system_instruction,
                        response_mime_type='application/json',
                        temperature=0.2,
                        thinking_config=types.ThinkingConfig(thinking_budget=settings.GEMINI_THINKING_BUDGET),
                    ),
                )
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

        # FILTER-DELTA: deterministic apply of prior_filters + delta.
        # Priority:
        #   1. If filter_delta present: final = prior + delta.set - delta.remove
        #   2. Else if filters present: final = {**(prior or {}), **llm_filters}
        #      (backward-compat for first turns or models that skip filter_delta)
        # After merging, run existing _repair_required_slate so result has a slate.
        _filter_delta = data.get('filter_delta') or {}
        _delta_set = _filter_delta.get('set') or {}
        _delta_remove = _filter_delta.get('remove') or []
        # Allowlist: only the 11 known axes survive into delta
        _VALID_AXES = frozenset({
            'location_country', 'location_city', 'program', 'material', 'style',
            'year_min', 'year_max', 'atmosphere', 'color_tone', 'typology_primary',
            'architectural_elements',
        })
        _delta_set = {k: v for k, v in _delta_set.items() if k in _VALID_AXES and v is not None}
        _delta_remove = [a for a in _delta_remove if isinstance(a, str) and a in _VALID_AXES]

        # An EMPTY delta ({'set': {}, 'remove': []}) is only meaningful on a
        # follow-up turn (prior filters exist). On a first turn it must NOT
        # shadow the full `filters` dict -- some models (gpt-5.6-luna, and
        # Gemini on schema-faithful outputs) always emit the delta skeleton,
        # which silently wiped every parsed filter (found in A/B 2026-08-04).
        if (_delta_set or _delta_remove) or (prior_filters and _filter_delta):
            # Follow-up turn: apply delta to prior
            filters = dict(prior_filters or {})
            filters.update(_delta_set)
            for _axis in _delta_remove:
                filters.pop(_axis, None)
        else:
            # First turn or LLM skipped filter_delta: merge prior + full LLM filters
            _llm_filters = data.get('filters') or dict(_empty_filters)
            filters = dict(prior_filters or {})
            filters.update({k: v for k, v in _llm_filters.items() if v is not None})

        # Sanitize program value (case-insensitive -> canonical form)
        if filters.get('program'):
            program = filters['program']
            if program not in PROGRAM_VALUES:
                titled = program.title()
                filters['program'] = titled if titled in PROGRAM_VALUES else None

        # BACK-PARSER-VOCAB-1: snap the 5 grounded soft axes to live DB vocabulary
        # (exact -> casefold -> style ism->ist -> title -> None). program is
        # untouched (handled above via PROGRAM_VALUES).
        filters = _snap_to_vocab(filters)

        # Sanitize/repair filter_priority: keep only non-null filter keys, but
        # never let a successful Gemini payload proceed without any required
        # slate field. Diffuse prompts get a broad Contemporary default.
        raw_priority = data.get('filter_priority') or []
        filters, filter_priority = _repair_required_slate(filters, raw_priority)
        # Expose validated delta for transparency (callers may log/inspect it)
        filter_delta = {'set': _delta_set, 'remove': _delta_remove}

        # raw_query: spec §3 says always verbatim first user message
        raw_query = data.get('raw_query') or first_user_text

        image_focus = data.get('image_focus')
        if image_focus not in ('exterior', 'interior', 'drawing', 'aerial', 'detail'):
            image_focus = None

        # TASTE-CALIBRATION-1: extract calibration fields
        calibration = _extract_calibration_fields(data, filters, probe_needed)

        result = {
            'probe_needed': probe_needed,
            'probe_question': data.get('probe_question') if probe_needed else None,
            'reply': data.get('reply', ''),
            'filters': filters,
            'filter_delta': filter_delta,
            'filter_priority': filter_priority,
            'image_focus': image_focus,
            'raw_query': raw_query,
            'visual_description': data.get('visual_description'),
            # TASTE-CALIBRATION-1 fields
            'confidence_score': calibration['confidence_score'],
            'system_action': calibration['system_action'],
            'suggested_quick_replies': calibration['suggested_quick_replies'],
            'priority_ordered': calibration['priority_ordered'],
            'llm_response_message': calibration['llm_response_message'],
        }
        # D1: multi-axis optional prompt — fires on any terminal turn with >=2 strong axes
        result = _maybe_multi_axis_probe(filters, filter_priority, _user_turn_count, result)
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


def parse_query_stage1(conversation_history, language=None, prior_filters=None):
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
        language: optional 'ko' or 'en' (UserProfile.language). When set, forces
            `reply` and `probe_question` to that language regardless of message language.
            None (default) keeps the infer-from-message behaviour.
        prior_filters: optional dict of accumulated filters from previous turns.
            When provided, injected into the Gemini request as context so the LLM
            can return a filter_delta (set/remove) instead of a full filters dict.
            The final filters are computed deterministically:
            final = prior_filters + delta.set - delta.remove.
            None (default) = first turn, no prior context.

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
        'atmosphere': None, 'color_tone': None, 'typology_primary': None,
        'architectural_elements': None,
    }
    _fallback = {
        'probe_needed': False,
        'probe_question': None,
        'reply': '이해를 잘 못 했어요. 일단 이 쪽으로 찾아볼게요.',
        'filters': dict(_empty_filters),
        'filter_delta': {'set': {}, 'remove': []},
        'filter_priority': [],
        'image_focus': None,
        'raw_query': first_user_text,
        'visual_description': None,
        # TASTE-CALIBRATION-1 fallback defaults
        'confidence_score': 0.55,
        'system_action': 'NONE',
        'suggested_quick_replies': [],
        'priority_ordered': [],
        'llm_response_message': '이해를 잘 못 했어요. 일단 이 쪽으로 찾아볼게요.',
    }

    # FULL-LANGUAGE-1: compute augmented system instruction once for all sites below.
    # language=None -> no directive (infer from message, existing behaviour).
    # TASTE-CALIBRATION-1: always append calibration extension to inject confidence fields.
    # BACK-PARSER-VOCAB-1: also append the live-DB "Allowed <axis> values" grounding
    # block for style/atmosphere/color_tone/typology_primary/architectural_elements.
    # get_axis_vocab() never raises (falls back to _VOCAB_SNAPSHOT), so this is safe
    # to call unconditionally. IMP-5 note: this string (including the vocab block)
    # is what would be hashed/cached if _get_prompt_hash read _system_instruction --
    # today it hashes the static _CHAT_PHASE_SYSTEM_PROMPT only, and the cached-content
    # path below (context_caching_enabled, default OFF) intentionally keeps caching the
    # static prompt (caching logic in _caches.py is algorithm-owned, untouched here);
    # the vocab block flows into system_instruction= on the (default) uncached path,
    # exactly like the language directive does today.
    _vocab_block = build_vocab_prompt_block(_svc.get_axis_vocab())
    _system_instruction = (
        _CHAT_PHASE_SYSTEM_PROMPT + _CALIBRATION_PROMPT_EXTENSION + _vocab_block
        + _LANG_DIRECTIVE[language]
        if language in _LANG_DIRECTIVE
        else _CHAT_PHASE_SYSTEM_PROMPT + _CALIBRATION_PROMPT_EXTENSION + _vocab_block
    )

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

        # FILTER-DELTA: inject prior_filters as a system-side context line so the
        # LLM knows the accumulated filter state and can return only the delta.
        # Appended as a trailing 'user' turn so it rides after the conversation
        # history but before the model responds. The model's instructions tell it
        # to output filter_delta (set/remove) when this context line is present.
        if prior_filters:
            import json as _json
            _prior_ctx = (
                f'현재까지 확정된 필터(JSON): {_json.dumps(prior_filters, ensure_ascii=False)}'
                f' — 사용자의 새 메시지는 이걸 다듬는 변경(델타)이다.'
            )
            contents.append(
                types.Content(role='user', parts=[types.Part.from_text(text=_prior_ctx)])
            )

        # IMP-5: explicit context caching branch (flag-gated, default OFF)
        # BACK-LLM-PROVIDER-1: Gemini explicit context caching (_ensure_chat_cache)
        # is a genai-only API surface (client.caches.create) -- gate it off on the
        # openai path so an openai.OpenAI client is never handed to it. The flag is
        # OFF by default regardless, so this guard only matters if a deployment
        # ever flips context_caching_enabled=True while LLM_PROVIDER=openai.
        caching_enabled = rc.get('context_caching_enabled', False) and settings.LLM_PROVIDER == 'gemini'
        cache_resource_name = None
        if caching_enabled:
            cache_resource_name = _svc._ensure_chat_cache(client)

        if cache_resource_name:
            # Cached path: supply cached_content= instead of system_instruction=
            # response_schema excludes visual_description -> reduced output tokens
            # Note: language directive is per-user (dynamic) so it cannot live in the
            # static cache; it is silently absent on the cached path (caching OFF by default).
            _s1_config = types.GenerateContentConfig(
                cached_content=cache_resource_name,
                response_mime_type='application/json',
                response_schema=_STAGE1_RESPONSE_SCHEMA,
                temperature=0.2,
                thinking_config=types.ThinkingConfig(thinking_budget=settings.GEMINI_THINKING_BUDGET),
            )
        else:
            # Uncached path: inject language directive via augmented system_instruction.
            _s1_config = types.GenerateContentConfig(
                system_instruction=_system_instruction,
                response_mime_type='application/json',
                response_schema=_STAGE1_RESPONSE_SCHEMA,
                temperature=0.2,
                thinking_config=types.ThinkingConfig(thinking_budget=settings.GEMINI_THINKING_BUDGET),
            )

        t_call_start = time.perf_counter()
        try:
            response = _svc.generate_content_with_fallback(
                client,
                contents=contents,
                config=_s1_config,
            )
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
                response = _svc.generate_content_with_fallback(
                    client,
                    contents=contents,
                    config=types.GenerateContentConfig(
                        system_instruction=_system_instruction,
                        response_mime_type='application/json',
                        response_schema=_STAGE1_RESPONSE_SCHEMA,
                        temperature=0.2,
                        thinking_config=types.ThinkingConfig(thinking_budget=settings.GEMINI_THINKING_BUDGET),
                    ),
                )
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

        # FILTER-DELTA: deterministic apply of prior_filters + delta.
        # Priority:
        #   1. If filter_delta present: final = prior + delta.set - delta.remove
        #   2. Else if filters present: final = {**(prior or {}), **llm_filters}
        #      (backward-compat for first turns or models that skip filter_delta)
        # After merging, run existing _repair_required_slate so result has a slate.
        _filter_delta = data.get('filter_delta') or {}
        _delta_set = _filter_delta.get('set') or {}
        _delta_remove = _filter_delta.get('remove') or []
        # Allowlist: only the 11 known axes survive into delta
        _VALID_AXES = frozenset({
            'location_country', 'location_city', 'program', 'material', 'style',
            'year_min', 'year_max', 'atmosphere', 'color_tone', 'typology_primary',
            'architectural_elements',
        })
        _delta_set = {k: v for k, v in _delta_set.items() if k in _VALID_AXES and v is not None}
        _delta_remove = [a for a in _delta_remove if isinstance(a, str) and a in _VALID_AXES]

        # An EMPTY delta ({'set': {}, 'remove': []}) is only meaningful on a
        # follow-up turn (prior filters exist). On a first turn it must NOT
        # shadow the full `filters` dict -- some models (gpt-5.6-luna, and
        # Gemini on schema-faithful outputs) always emit the delta skeleton,
        # which silently wiped every parsed filter (found in A/B 2026-08-04).
        if (_delta_set or _delta_remove) or (prior_filters and _filter_delta):
            # Follow-up turn: apply delta to prior
            filters = dict(prior_filters or {})
            filters.update(_delta_set)
            for _axis in _delta_remove:
                filters.pop(_axis, None)
        else:
            # First turn or LLM skipped filter_delta: merge prior + full LLM filters
            _llm_filters = data.get('filters') or dict(_empty_filters)
            filters = dict(prior_filters or {})
            filters.update({k: v for k, v in _llm_filters.items() if v is not None})

        # Sanitize program value
        if filters.get('program'):
            program = filters['program']
            if program not in PROGRAM_VALUES:
                titled = program.title()
                filters['program'] = titled if titled in PROGRAM_VALUES else None

        # BACK-PARSER-VOCAB-1: snap the 5 grounded soft axes to live DB vocabulary
        # (exact -> casefold -> style ism->ist -> title -> None). program is
        # untouched (handled above via PROGRAM_VALUES).
        filters = _snap_to_vocab(filters)

        # Sanitize/repair filter_priority: keep only non-null filter keys, but
        # never let a successful Gemini payload proceed without any required
        # slate field. Diffuse prompts get a broad Contemporary default.
        raw_priority = data.get('filter_priority') or []
        filters, filter_priority = _repair_required_slate(filters, raw_priority)
        # Expose validated delta for transparency (callers may log/inspect it)
        filter_delta = {'set': _delta_set, 'remove': _delta_remove}

        # raw_query: spec §3 says always verbatim first user message
        raw_query = data.get('raw_query') or first_user_text

        image_focus = data.get('image_focus')
        if image_focus not in ('exterior', 'interior', 'drawing', 'aerial', 'detail'):
            image_focus = None

        # TASTE-CALIBRATION-1: extract calibration fields
        calibration = _extract_calibration_fields(data, filters, probe_needed)

        result = {
            'probe_needed': probe_needed,
            'probe_question': data.get('probe_question') if probe_needed else None,
            'reply': data.get('reply', ''),
            'filters': filters,
            'filter_delta': filter_delta,
            'filter_priority': filter_priority,
            'image_focus': image_focus,
            'raw_query': raw_query,
            'visual_description': None,  # Stage 2 generates this asynchronously
            # TASTE-CALIBRATION-1 fields
            'confidence_score': calibration['confidence_score'],
            'system_action': calibration['system_action'],
            'suggested_quick_replies': calibration['suggested_quick_replies'],
            'priority_ordered': calibration['priority_ordered'],
            'llm_response_message': calibration['llm_response_message'],
        }
        # D1: multi-axis optional prompt — fires on any terminal turn with >=2 strong axes
        result = _maybe_multi_axis_probe(filters, filter_priority, _user_turn_count, result)
        return result

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
