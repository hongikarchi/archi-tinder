"""
test_m1_clarification_cap.py -- M1 max-clarification-turns cap tests.

Investigation 22 §M1 refined (Sprint B mitigation):
- Python-level runaway-clarification cap: if user_turn_count >= 3 AND Gemini
  returns probe_needed=True, Python forces probe_needed=False (terminal mode).
- Prompt HARD CAP clause added as defense-in-depth (Gemini prompt instruction).
- m1_cap_forced_terminal telemetry field added to parse_query_timing event.

Critical guardrails verified:
- Cap fires at user_turn_count >= 3 ONLY (not at 2 — BareQuery 1-clarification
  flow must be preserved per Investigation 06 design intent).
- Bare-string / single-turn inputs never hit the cap (backward compat).
- 0-turn skip (Brutalist class) and 1-turn / 2-turn clarification flows unchanged.
- m1_cap_forced_terminal=False when cap did not fire; True only when Python overrode.
"""
import json
import pytest
from unittest.mock import patch, MagicMock
from django.core.cache import cache


# ---------------------------------------------------------------------------
# Test helpers (reuse pattern from test_m4_clarification_telemetry.py)
# ---------------------------------------------------------------------------

def _make_gemini_response(probe_needed: bool, with_filters=True):
    """Build a MagicMock Gemini response with the given probe_needed value."""
    if probe_needed:
        payload = {
            "probe_needed": True,
            "probe_question": "직교 vs 곡선?",
            "reply": "메모했어요.",
            "filters": {
                "location_country": None, "program": None, "material": None,
                "style": None, "year_min": None, "year_max": None,
                "min_area": None, "max_area": None,
            },
            "filter_priority": [],
            "raw_query": "좋은 레퍼런스 있으면 보여주세요.",
            "visual_description": None,
        }
    else:
        payload = {
            "probe_needed": False,
            "probe_question": None,
            "reply": "이해했어요.",
            "filters": {
                "location_country": None, "program": "Museum", "material": "concrete",
                "style": "Brutalist", "year_min": None, "year_max": None,
                "min_area": None, "max_area": None,
            } if with_filters else {
                "location_country": None, "program": None, "material": None,
                "style": None, "year_min": None, "year_max": None,
                "min_area": None, "max_area": None,
            },
            "filter_priority": ["program", "style", "material"] if with_filters else [],
            "raw_query": "concrete brutalist museum",
            "visual_description": "A raw concrete brutalist museum.",
        }

    resp = MagicMock()
    resp.text = json.dumps(payload)
    usage = MagicMock()
    usage.prompt_token_count = 100
    usage.candidates_token_count = 50
    usage.thoughts_token_count = 0
    usage.cached_content_token_count = None
    resp.usage_metadata = usage
    return resp


class _RecommendationOverride:
    """Minimal context manager to override RECOMMENDATION dict keys in tests."""
    def __init__(self, **overrides):
        self._overrides = overrides
        self._original = {}

    def __enter__(self):
        from django.conf import settings
        rc = settings.RECOMMENDATION
        for k, v in self._overrides.items():
            self._original[k] = rc.get(k)
            rc[k] = v
        return self

    def __exit__(self, *args):
        from django.conf import settings
        rc = settings.RECOMMENDATION
        for k, v in self._original.items():
            if v is None:
                rc.pop(k, None)
            else:
                rc[k] = v


def _run_parse_query(conversation_history, probe_needed_from_gemini):
    """Run parse_query with a mock Gemini response, collect emitted events."""
    from apps.recommendation.services import parse_query

    mock_resp = _make_gemini_response(probe_needed=probe_needed_from_gemini)
    emitted_events = []

    with patch('apps.recommendation.services._get_client') as mock_gc, \
         patch('apps.recommendation.services.event_log.emit_event',
               side_effect=lambda *a, **kw: emitted_events.append((a, kw))):
        mock_client = MagicMock()
        mock_client.models.generate_content.return_value = mock_resp
        mock_gc.return_value = mock_client

        with _RecommendationOverride(context_caching_enabled=False):
            result = parse_query(conversation_history)

    timing_events = [e for e in emitted_events if e[0][0] == 'parse_query_timing']
    return result, timing_events


# ---------------------------------------------------------------------------
# Conversation history fixtures
# ---------------------------------------------------------------------------

# 1-user-turn conversations
_HIST_1_TURN_BARE_STRING = "concrete brutalist museum"  # bare string (legacy path)
_HIST_1_TURN_LIST = [
    {'role': 'user', 'text': 'concrete brutalist museum'},
]

# 2-user-turn conversation (legitimate 1-clarification BareQuery flow)
_HIST_2_TURNS = [
    {'role': 'user', 'text': '좋은 레퍼런스 있으면 보여주세요.'},
    {'role': 'model', 'text': '작고 내밀한 공간이 끌리세요, 아니면 크고 개방감 있는 공간이 끌리세요?'},
    {'role': 'user', 'text': '개방감 있는 쪽.'},
]

# 3-user-turn conversation (runaway: answer to 2nd clarification)
_HIST_3_TURNS = [
    {'role': 'user', 'text': '좋은 레퍼런스 있으면 보여주세요.'},
    {'role': 'model', 'text': '작고 내밀한 공간이 끌리세요, 아니면 크고 개방감 있는 공간이 끌리세요?'},
    {'role': 'user', 'text': '개방감 있는 쪽.'},
    {'role': 'model', 'text': '직교적·격자형 공간이 끌리세요, 곡선적·흐르는 형태가 끌리세요?'},
    {'role': 'user', 'text': '직교적인 거.'},
]

# 4-user-turn conversation (deep runaway)
_HIST_4_TURNS = [
    {'role': 'user', 'text': '좋은 레퍼런스 있으면 보여주세요.'},
    {'role': 'model', 'text': 'Q1?'},
    {'role': 'user', 'text': 'A1'},
    {'role': 'model', 'text': 'Q2?'},
    {'role': 'user', 'text': 'A2'},
    {'role': 'model', 'text': 'Q3?'},
    {'role': 'user', 'text': 'A3'},
]


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestM1ClarificationCap:

    def setup_method(self):
        cache.clear()

    def test_cap_does_not_fire_on_first_user_turn(self):
        """1-turn conversation: cap never activates regardless of probe_needed."""
        result, timing_events = _run_parse_query(_HIST_1_TURN_LIST, probe_needed_from_gemini=True)

        # Gemini said probe_needed=True; with only 1 user turn, cap must NOT fire
        assert result['probe_needed'] is True, (
            "1-turn + Gemini probe_needed=True -> result must preserve probe_needed=True"
        )

        assert len(timing_events) == 1
        kw = timing_events[0][1]
        assert kw.get('m1_cap_forced_terminal') is False, (
            f"m1_cap_forced_terminal must be False on turn 1, got {kw.get('m1_cap_forced_terminal')!r}"
        )

    def test_cap_does_not_fire_on_first_user_turn_bare_string(self):
        """Bare-string input (legacy path) is treated as 1 user turn; cap never fires."""
        result, timing_events = _run_parse_query(_HIST_1_TURN_BARE_STRING, probe_needed_from_gemini=True)

        assert result['probe_needed'] is True, (
            "Bare-string turn 1 + Gemini probe_needed=True -> must preserve probe_needed=True"
        )

        assert len(timing_events) == 1
        kw = timing_events[0][1]
        assert kw.get('m1_cap_forced_terminal') is False, (
            "Bare-string input must never trigger M1 cap"
        )

    def test_cap_does_not_fire_on_second_user_turn(self):
        """2-user-turn conversation with Gemini probe_needed=True: cap must NOT fire.

        This is the legitimate BareQuery 1-clarification flow (Investigation 06 design intent).
        Cap fires only at turn 3+, not turn 2.
        """
        result, timing_events = _run_parse_query(_HIST_2_TURNS, probe_needed_from_gemini=True)

        # Turn 2 is a legal continuation of the 1-clarification BareQuery flow
        assert result['probe_needed'] is True, (
            "2-turn conversation + Gemini probe_needed=True -> probe_needed must remain True"
            " (cap fires at turn 3+, not turn 2)"
        )

        assert len(timing_events) == 1
        kw = timing_events[0][1]
        assert kw.get('m1_cap_forced_terminal') is False, (
            f"m1_cap_forced_terminal must be False on turn 2, got {kw.get('m1_cap_forced_terminal')!r}"
        )

    def test_cap_fires_on_third_user_turn_when_gemini_ignores(self):
        """3-user-turn conversation + Gemini probe_needed=True: Python forces terminal.

        This is the runaway clarification case. Gemini ignored the prompt cap;
        Python enforces it.
        """
        result, timing_events = _run_parse_query(_HIST_3_TURNS, probe_needed_from_gemini=True)

        # Python cap should override Gemini's probe_needed=True
        assert result['probe_needed'] is False, (
            "3-turn conversation + Gemini probe_needed=True -> Python cap must force probe_needed=False"
        )
        # probe_question must be None when probe_needed=False (line 770 in services.py)
        assert result['probe_question'] is None, (
            "probe_question must be None after cap forces terminal mode"
        )

        assert len(timing_events) == 1
        kw = timing_events[0][1]
        assert kw.get('m1_cap_forced_terminal') is True, (
            f"m1_cap_forced_terminal must be True when Python cap fires, got {kw.get('m1_cap_forced_terminal')!r}"
        )

    def test_cap_fires_on_fourth_user_turn_deep_runaway(self):
        """4-user-turn conversation: cap fires the same way as on turn 3."""
        result, timing_events = _run_parse_query(_HIST_4_TURNS, probe_needed_from_gemini=True)

        assert result['probe_needed'] is False, (
            "4-turn conversation + Gemini probe_needed=True -> Python cap must force probe_needed=False"
        )

        assert len(timing_events) == 1
        kw = timing_events[0][1]
        assert kw.get('m1_cap_forced_terminal') is True, (
            "m1_cap_forced_terminal must be True on deep-runaway (turn 4)"
        )

    def test_cap_inactive_on_third_turn_when_gemini_returns_terminal(self):
        """3-user-turn conversation + Gemini probe_needed=False: no Python override.

        Gemini correctly followed the prompt cap. Python must not interfere.
        """
        result, timing_events = _run_parse_query(_HIST_3_TURNS, probe_needed_from_gemini=False)

        # Gemini already returned terminal; Python cap should NOT fire
        assert result['probe_needed'] is False, (
            "3-turn + Gemini probe_needed=False -> result must be probe_needed=False (no Python override needed)"
        )

        assert len(timing_events) == 1
        kw = timing_events[0][1]
        assert kw.get('m1_cap_forced_terminal') is False, (
            "m1_cap_forced_terminal must be False when Gemini already returned terminal (cap not needed)"
        )

    def test_cap_preserves_brutalist_zero_turn_pattern(self):
        """Brutalist-class query (0-turn skip): no cap activation, normal flow."""
        result, timing_events = _run_parse_query(
            "concrete brutalist museum",
            probe_needed_from_gemini=False,
        )

        assert result['probe_needed'] is False, (
            "Brutalist 0-turn skip -> probe_needed must remain False"
        )

        assert len(timing_events) == 1
        kw = timing_events[0][1]
        assert kw.get('m1_cap_forced_terminal') is False, (
            "Brutalist zero-turn path must not trigger M1 cap"
        )
        # Verify complexity class is still correct
        assert kw.get('query_complexity_class') == 'brutalist', (
            "query_complexity_class must be 'brutalist' for 'concrete brutalist museum'"
        )

    def test_cap_preserves_barequery_two_turn_pattern(self):
        """BareQuery 2-user-turn conversation + Gemini probe_needed=True: cap must NOT fire.

        This is exactly Investigation 06's design intent: BareQuery class gets up to
        2 probe turns. Cap applies only at turn 3+.
        """
        result, timing_events = _run_parse_query(_HIST_2_TURNS, probe_needed_from_gemini=True)

        # Turn 2 is within the allowed 2-probe-turn budget
        assert result['probe_needed'] is True, (
            "BareQuery 2-turn continuation: probe_needed=True must be preserved (Investigation 06 design intent)"
        )

        kw = timing_events[0][1]
        assert kw.get('m1_cap_forced_terminal') is False, (
            "BareQuery turn-2 continuation must not trigger M1 cap (cap fires at turn 3+)"
        )

    def test_user_turn_count_works_with_alternating_assistant_messages(self):
        """user_turn_count counts only role='user', ignoring role='model' messages."""
        hist = [
            {'role': 'user', 'text': 'Query A'},          # user turn 1
            {'role': 'model', 'text': 'AI response 1'},   # model turn (NOT counted)
            {'role': 'user', 'text': 'Query B'},          # user turn 2
            {'role': 'model', 'text': 'AI response 2'},   # model turn (NOT counted)
            {'role': 'user', 'text': 'Query C'},          # user turn 3 --> cap threshold
        ]
        # With Gemini probe_needed=True on turn 3, cap must fire
        result, timing_events = _run_parse_query(hist, probe_needed_from_gemini=True)

        assert result['probe_needed'] is False, (
            "5-element hist with 3 user turns + Gemini probe_needed=True -> cap must fire"
        )

        kw = timing_events[0][1]
        assert kw.get('m1_cap_forced_terminal') is True, (
            "m1_cap_forced_terminal must be True: 3 user turns counted correctly despite model turns"
        )

    def test_cap_telemetry_field_present_in_payload_when_cap_fires(self):
        """m1_cap_forced_terminal=True lands in parse_query_timing event when cap fires."""
        result, timing_events = _run_parse_query(_HIST_3_TURNS, probe_needed_from_gemini=True)

        assert len(timing_events) == 1, "Exactly one parse_query_timing event expected"
        kw = timing_events[0][1]

        # Field must be present
        assert 'm1_cap_forced_terminal' in kw, (
            "m1_cap_forced_terminal field missing from parse_query_timing payload"
        )
        # Value must be True (cap fired)
        assert kw['m1_cap_forced_terminal'] is True

    def test_cap_telemetry_field_present_in_payload_when_cap_does_not_fire(self):
        """m1_cap_forced_terminal=False lands in parse_query_timing event on normal turns."""
        result, timing_events = _run_parse_query(_HIST_1_TURN_LIST, probe_needed_from_gemini=False)

        assert len(timing_events) == 1
        kw = timing_events[0][1]

        # Field must be present even when cap doesn't fire
        assert 'm1_cap_forced_terminal' in kw, (
            "m1_cap_forced_terminal field missing from parse_query_timing payload (normal path)"
        )
        assert kw['m1_cap_forced_terminal'] is False

    def test_existing_m4_fields_still_present_alongside_m1_field(self):
        """m1_cap_forced_terminal is additive; all existing M4 fields must still be present."""
        result, timing_events = _run_parse_query(_HIST_3_TURNS, probe_needed_from_gemini=True)

        assert len(timing_events) == 1
        kw = timing_events[0][1]

        # Existing M4 fields
        assert 'clarification_fired' in kw, "clarification_fired (M4) must still be present"
        assert 'query_complexity_class' in kw, "query_complexity_class (M4) must still be present"

        # New M1 field
        assert 'm1_cap_forced_terminal' in kw, "m1_cap_forced_terminal (M1) must be present"

        # Existing IMP-5 fields
        assert 'cache_hit' in kw, "cache_hit (IMP-5) must still be present"
        assert 'caching_mode' in kw, "caching_mode (IMP-5) must still be present"

        # Base timing fields
        assert 'gemini_total_ms' in kw, "gemini_total_ms must still be present"

    def test_cap_does_not_affect_filters_shape_when_gemini_returns_partial_filters(self):
        """After cap forces terminal, filters shape from Gemini response is preserved.

        The cap only overrides probe_needed; it does not rewrite filters. The existing
        'filters = data.get("filters") or dict(_empty_filters)' fallback handles
        empty/null filters gracefully.
        """
        # Build a 3-user-turn history with Gemini returning partial filters
        from apps.recommendation.services import parse_query

        partial_filter_payload = {
            "probe_needed": True,  # Gemini ignores cap
            "probe_question": "Yet another question?",
            "reply": "OK",
            "filters": {
                "location_country": None, "program": None, "material": None,
                "style": "Modernist", "year_min": None, "year_max": None,
                "min_area": None, "max_area": None,
            },
            "filter_priority": ["style"],
            "raw_query": "좋은 레퍼런스 있으면 보여주세요.",
            "visual_description": None,
        }

        resp = MagicMock()
        resp.text = json.dumps(partial_filter_payload)
        usage = MagicMock()
        usage.prompt_token_count = 100
        usage.candidates_token_count = 50
        usage.thoughts_token_count = 0
        usage.cached_content_token_count = None
        resp.usage_metadata = usage

        with patch('apps.recommendation.services._get_client') as mock_gc, \
             patch('apps.recommendation.services.event_log.emit_event'):
            mock_client = MagicMock()
            mock_client.models.generate_content.return_value = resp
            mock_gc.return_value = mock_client

            with _RecommendationOverride(context_caching_enabled=False):
                result = parse_query(_HIST_3_TURNS)

        # Cap must force terminal
        assert result['probe_needed'] is False
        # Filters from Gemini's partial response must be preserved
        assert result['filters']['style'] == 'Modernist', (
            "Cap must preserve whatever filters Gemini extracted"
        )
        # probe_question must be None when probe_needed=False
        assert result['probe_question'] is None
