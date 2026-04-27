"""
test_m4_clarification_telemetry.py -- M4 clarification telemetry fields.

Investigation 22 §M4 + IMP-10 sub-task A continuation (spec v1.7+v1.8+v1.9):
Extends `parse_query_timing` SessionEvent payload with two additive fields:
  - `clarification_fired` (bool | None)
  - `query_complexity_class` (str)

Tests cover:
1. test_clarification_fired_true_when_clarification_response
2. test_clarification_fired_false_when_terminal_response
3. test_query_complexity_brutalist
4. test_query_complexity_narrow
5. test_query_complexity_barequery
6. test_query_complexity_unknown_fallback
7. test_backward_compat_existing_fields_preserved
8. test_failure_path_emits_safe_defaults

Vocabulary note: query_complexity_class uses the task-spec vocabulary
('brutalist' / 'narrow' / 'barequery' / 'unknown'). Investigation 20 row 22
diagnostic SQL uses 'narrow' to query the brutalist-class cohort — callers
running that query should adapt the WHERE clause to filter by 'brutalist'.
This is a known vocabulary discrepancy between Investigation 22 §M4 task spec
and Investigation 20 §2 row 22 as written; the back-maker shipped per task spec.
"""
import json
import pytest
from unittest.mock import patch, MagicMock
from django.core.cache import cache


# ---------------------------------------------------------------------------
# Reuse helper patterns from test_imp5_context_caching.py
# ---------------------------------------------------------------------------

def _make_gemini_response_with_probe(probe_needed: bool, cached_tokens=None):
    """Build a MagicMock Gemini response with the given probe_needed value."""
    if probe_needed:
        payload = {
            "probe_needed": True,
            "probe_question": "따뜻한 재료 vs 차가운 기하성?",
            "reply": "주택 찾는 거 확인했어요.",
            "filters": {
                "location_country": None, "program": "Housing", "material": None,
                "style": None, "year_min": None, "year_max": None,
                "min_area": None, "max_area": None,
            },
            "filter_priority": ["program"],
            "raw_query": "새로 올릴 주택 프로젝트 참고용 찾아요.",
            "visual_description": None,
        }
    else:
        payload = {
            "probe_needed": False,
            "probe_question": None,
            "reply": "이해했어요: 브루탈리스트 콘크리트 미술관.",
            "filters": {
                "location_country": None, "program": "Museum", "material": "concrete",
                "style": "Brutalist", "year_min": None, "year_max": None,
                "min_area": None, "max_area": None,
            },
            "filter_priority": ["program", "style", "material"],
            "raw_query": "concrete brutalist museum",
            "visual_description": "A monumental concrete brutalist museum with raw exposed surfaces.",
        }

    resp = MagicMock()
    resp.text = json.dumps(payload)
    usage = MagicMock()
    usage.prompt_token_count = 120
    usage.candidates_token_count = 60
    usage.thoughts_token_count = 0
    usage.cached_content_token_count = cached_tokens
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


# ---------------------------------------------------------------------------
# Tests: _classify_query_complexity (unit; no DB needed)
# ---------------------------------------------------------------------------

class TestQueryComplexityClassifier:
    """Unit tests for the M4 query complexity heuristic classifier."""

    def test_query_complexity_brutalist(self):
        """Query with 3+ specific architectural entities -> 'brutalist'."""
        from apps.recommendation.services import _classify_query_complexity
        result = _classify_query_complexity("concrete brutalist museum")
        assert result == 'brutalist', f"Expected 'brutalist', got {result!r}"

    def test_query_complexity_brutalist_korean(self):
        """Korean-flavoured Brutalist query also classifies correctly."""
        from apps.recommendation.services import _classify_query_complexity
        # 콘크리트 (material) + 브루탈리스트 (style) + 미술관 (program)
        result = _classify_query_complexity("콘크리트 브루탈리스트 미술관")
        assert result == 'brutalist', f"Expected 'brutalist', got {result!r}"

    def test_query_complexity_narrow_modern_building(self):
        """Query with 1-2 specific terms -> 'narrow'."""
        from apps.recommendation.services import _classify_query_complexity
        result = _classify_query_complexity("modern building")
        assert result == 'narrow', f"Expected 'narrow', got {result!r}"

    def test_query_complexity_narrow_art_museum(self):
        """'art museum' has one program entity -> 'narrow'."""
        from apps.recommendation.services import _classify_query_complexity
        result = _classify_query_complexity("art museum")
        assert result == 'narrow', f"Expected 'narrow', got {result!r}"

    def test_query_complexity_barequery_generic(self):
        """Generic/vague queries without specific entities -> 'barequery'."""
        from apps.recommendation.services import _classify_query_complexity
        result = _classify_query_complexity("show me something")
        assert result == 'barequery', f"Expected 'barequery', got {result!r}"

    def test_query_complexity_barequery_interesting(self):
        """'interesting building' has no vocabulary hits -> 'barequery'."""
        from apps.recommendation.services import _classify_query_complexity
        result = _classify_query_complexity("interesting building")
        assert result == 'barequery', f"Expected 'barequery', got {result!r}"

    def test_query_complexity_unknown_none_input(self):
        """None input -> 'unknown' (safe default)."""
        from apps.recommendation.services import _classify_query_complexity
        result = _classify_query_complexity(None)
        assert result == 'unknown', f"Expected 'unknown', got {result!r}"

    def test_query_complexity_unknown_empty_string(self):
        """Empty string -> 'unknown'."""
        from apps.recommendation.services import _classify_query_complexity
        result = _classify_query_complexity("")
        assert result == 'unknown', f"Expected 'unknown', got {result!r}"


# ---------------------------------------------------------------------------
# Tests: parse_query_timing event fields (require DB via @pytest.mark.django_db)
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestM4ClarificationFields:
    """Integration tests: M4 fields land correctly in parse_query_timing emit."""

    def setup_method(self):
        cache.clear()

    def test_clarification_fired_true_when_clarification_response(self):
        """When Gemini returns probe_needed=True, clarification_fired=True in event."""
        from apps.recommendation.services import parse_query

        mock_resp = _make_gemini_response_with_probe(probe_needed=True)
        emitted_events = []

        with patch('apps.recommendation.services._get_client') as mock_gc, \
             patch('apps.recommendation.services.event_log.emit_event',
                   side_effect=lambda *a, **kw: emitted_events.append((a, kw))):
            mock_client = MagicMock()
            mock_client.models.generate_content.return_value = mock_resp
            mock_gc.return_value = mock_client

            with _RecommendationOverride(context_caching_enabled=False):
                result = parse_query("새로 올릴 주택 프로젝트 참고용 찾아요.")

        assert result is not None
        timing_events = [e for e in emitted_events if e[0][0] == 'parse_query_timing']
        assert len(timing_events) == 1, "Exactly one parse_query_timing event expected"
        kw = timing_events[0][1]
        assert kw.get('clarification_fired') is True, (
            f"Expected clarification_fired=True, got {kw.get('clarification_fired')!r}"
        )

    def test_clarification_fired_false_when_terminal_response(self):
        """When Gemini returns probe_needed=False, clarification_fired=False in event."""
        from apps.recommendation.services import parse_query

        mock_resp = _make_gemini_response_with_probe(probe_needed=False)
        emitted_events = []

        with patch('apps.recommendation.services._get_client') as mock_gc, \
             patch('apps.recommendation.services.event_log.emit_event',
                   side_effect=lambda *a, **kw: emitted_events.append((a, kw))):
            mock_client = MagicMock()
            mock_client.models.generate_content.return_value = mock_resp
            mock_gc.return_value = mock_client

            with _RecommendationOverride(context_caching_enabled=False):
                result = parse_query("concrete brutalist museum")

        assert result is not None
        timing_events = [e for e in emitted_events if e[0][0] == 'parse_query_timing']
        assert len(timing_events) == 1
        kw = timing_events[0][1]
        assert kw.get('clarification_fired') is False, (
            f"Expected clarification_fired=False, got {kw.get('clarification_fired')!r}"
        )

    def test_query_complexity_class_in_event_for_brutalist_query(self):
        """Brutalist query produces query_complexity_class='brutalist' in event."""
        from apps.recommendation.services import parse_query

        mock_resp = _make_gemini_response_with_probe(probe_needed=False)
        emitted_events = []

        with patch('apps.recommendation.services._get_client') as mock_gc, \
             patch('apps.recommendation.services.event_log.emit_event',
                   side_effect=lambda *a, **kw: emitted_events.append((a, kw))):
            mock_client = MagicMock()
            mock_client.models.generate_content.return_value = mock_resp
            mock_gc.return_value = mock_client

            with _RecommendationOverride(context_caching_enabled=False):
                parse_query("concrete brutalist museum")

        timing_events = [e for e in emitted_events if e[0][0] == 'parse_query_timing']
        kw = timing_events[0][1]
        assert kw.get('query_complexity_class') == 'brutalist', (
            f"Expected 'brutalist', got {kw.get('query_complexity_class')!r}"
        )

    def test_backward_compat_existing_fields_preserved(self):
        """All 10 base + IMP-5 fields still present alongside new M4 fields."""
        from apps.recommendation.services import parse_query

        mock_resp = _make_gemini_response_with_probe(probe_needed=False, cached_tokens=None)
        emitted_events = []

        with patch('apps.recommendation.services._get_client') as mock_gc, \
             patch('apps.recommendation.services.event_log.emit_event',
                   side_effect=lambda *a, **kw: emitted_events.append((a, kw))):
            mock_client = MagicMock()
            mock_client.models.generate_content.return_value = mock_resp
            mock_gc.return_value = mock_client

            with _RecommendationOverride(context_caching_enabled=False):
                result = parse_query("concrete brutalist museum")

        assert result is not None
        timing_events = [e for e in emitted_events if e[0][0] == 'parse_query_timing']
        assert len(timing_events) == 1
        kw = timing_events[0][1]

        # All 6 base fields (IMP-4 era)
        assert 'gemini_total_ms' in kw, "gemini_total_ms missing"
        assert 'ttft_ms' in kw, "ttft_ms missing"
        assert 'gen_ms' in kw, "gen_ms missing"
        assert 'input_tokens' in kw, "input_tokens missing"
        assert 'output_tokens' in kw, "output_tokens missing"
        assert 'thinking_tokens' in kw, "thinking_tokens missing"

        # All 4 IMP-5 fields (context caching era)
        assert 'cache_hit' in kw, "cache_hit missing"
        assert 'cached_input_tokens' in kw, "cached_input_tokens missing"
        assert 'cache_name_hash' in kw, "cache_name_hash missing"
        assert 'caching_mode' in kw, "caching_mode missing"

        # New M4 fields
        assert 'clarification_fired' in kw, "clarification_fired missing (M4)"
        assert 'query_complexity_class' in kw, "query_complexity_class missing (M4)"

    def test_failure_path_emits_safe_defaults(self):
        """Gemini API error -> fallback returned; no parse_query_timing emitted (Gemini never responded).

        When the Gemini call itself raises (exception path), parse_query_timing is not
        emitted -- only a 'failure' event fires. The timing event is only emitted after
        a Gemini response (even a malformed one) is received.
        """
        from apps.recommendation.services import parse_query

        emitted_events = []

        with patch('apps.recommendation.services._get_client') as mock_gc, \
             patch('apps.recommendation.services.event_log.emit_event',
                   side_effect=lambda *a, **kw: emitted_events.append((a, kw))):
            mock_client = MagicMock()
            mock_client.models.generate_content.side_effect = RuntimeError("quota exceeded")
            mock_gc.return_value = mock_client

            with _RecommendationOverride(context_caching_enabled=False):
                result = parse_query("concrete brutalist museum")

        # Should return graceful fallback, not raise
        assert result is not None
        assert result.get('reply') == '이해를 잘 못 했어요. 일단 이 쪽으로 찾아볼게요.'

        # Timing event is NOT emitted (exception fired before response received)
        timing_events = [e for e in emitted_events if e[0][0] == 'parse_query_timing']
        assert len(timing_events) == 0, (
            "parse_query_timing should not be emitted when Gemini API raises"
        )

        # A 'failure' event IS emitted
        failure_events = [e for e in emitted_events if e[0][0] == 'failure']
        assert len(failure_events) >= 1, "failure event must be emitted on Gemini exception"

    def test_failure_on_json_parse_emits_timing_with_none_clarification(self):
        """Gemini responds (200 OK) but returns invalid JSON -> timing event fires with
        clarification_fired=None (pre-parse fails, no value to commit)."""
        from apps.recommendation.services import parse_query

        # Mock Gemini to return garbage text (not valid JSON)
        resp = MagicMock()
        resp.text = "NOT VALID JSON {{{{"
        usage = MagicMock()
        usage.prompt_token_count = 50
        usage.candidates_token_count = 5
        usage.thoughts_token_count = 0
        usage.cached_content_token_count = None
        resp.usage_metadata = usage

        emitted_events = []

        with patch('apps.recommendation.services._get_client') as mock_gc, \
             patch('apps.recommendation.services.event_log.emit_event',
                   side_effect=lambda *a, **kw: emitted_events.append((a, kw))):
            mock_client = MagicMock()
            mock_client.models.generate_content.return_value = resp
            mock_gc.return_value = mock_client

            with _RecommendationOverride(context_caching_enabled=False):
                result = parse_query("concrete brutalist museum")

        # Fallback returned
        assert result.get('reply') == '이해를 잘 못 했어요. 일단 이 쪽으로 찾아볼게요.'

        # parse_query_timing IS emitted (Gemini responded; timing was measured)
        timing_events = [e for e in emitted_events if e[0][0] == 'parse_query_timing']
        assert len(timing_events) == 1, (
            "parse_query_timing must fire even on JSON decode error (timing was measured)"
        )
        kw = timing_events[0][1]

        # clarification_fired should be None (pre-parse failed; unknown state)
        assert kw.get('clarification_fired') is None, (
            f"Expected clarification_fired=None on pre-parse failure, got {kw.get('clarification_fired')!r}"
        )

        # query_complexity_class still populated from user text (heuristic doesn't need Gemini)
        assert kw.get('query_complexity_class') == 'brutalist', (
            f"Expected 'brutalist', got {kw.get('query_complexity_class')!r}"
        )
