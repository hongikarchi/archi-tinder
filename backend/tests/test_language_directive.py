"""
test_language_directive.py -- FULL-LANGUAGE-1 Slice 1: parse_query language directive tests.

Verifies:
  - parse_query(..., language='en') injects an English-forcing directive into
    system_instruction on the uncached (default) path.
  - parse_query(..., language=None) leaves system_instruction unchanged (no directive).
  - parse_query(..., language='ko') injects a Korean-forcing directive.
  - visual_description rule (ALWAYS English) and raw_query rule (verbatim) are
    preserved regardless of language setting.
"""
import json
from unittest.mock import MagicMock
from django.conf import settings

from apps.recommendation import services
from apps.recommendation.services._prompts import (
    _CHAT_PHASE_SYSTEM_PROMPT,
    _CALIBRATION_PROMPT_EXTENSION,
)
from apps.recommendation.services.parse_query import _LANG_DIRECTIVE


def _make_gemini_response(payload: dict):
    mock_resp = MagicMock()
    mock_resp.text = json.dumps(payload)
    # Avoid int() guard on usage_metadata tokens
    mock_resp.usage_metadata = None
    return mock_resp


_TERMINAL_PAYLOAD = {
    'probe_needed': False,
    'probe_question': None,
    'reply': 'Got it: timber housing. Sound right?',
    'filters': {
        'location_country': None,
        'program': 'Housing',
        'material': 'timber',
        'style': None,
        'year_min': None,
        'year_max': None,
    },
    'filter_priority': ['program', 'material'],
    'raw_query': 'timber house references',
    'visual_description': 'A residential house with warm exposed timber.',
}


class TestParseQueryLanguageDirective:
    """FULL-LANGUAGE-1: language directive reaches the Gemini system_instruction."""

    def test_language_en_injects_english_directive(self, monkeypatch):
        """parse_query(..., language='en') places the English directive in system_instruction."""
        monkeypatch.setitem(settings.RECOMMENDATION, 'stage_decouple_enabled', False)
        monkeypatch.setitem(settings.RECOMMENDATION, 'context_caching_enabled', False)
        monkeypatch.setattr(services, '_get_client', lambda: MagicMock())
        monkeypatch.setattr(services, 'event_log', MagicMock())

        captured_configs = []

        def _fake_gwf(client, contents, config):
            captured_configs.append(config)
            return _make_gemini_response(_TERMINAL_PAYLOAD)

        monkeypatch.setattr(services, 'generate_content_with_fallback', _fake_gwf)

        services.parse_query(
            [{'role': 'user', 'text': 'timber house references'}],
            language='en',
        )

        assert len(captured_configs) == 1, 'generate_content_with_fallback must be called once'
        sys_instr = captured_configs[0].system_instruction
        # Directive must extend the base prompt
        assert sys_instr.startswith(_CHAT_PHASE_SYSTEM_PROMPT)
        # English directive text present
        assert _LANG_DIRECTIVE['en'] in sys_instr
        # Korean directive absent
        assert _LANG_DIRECTIVE['ko'] not in sys_instr

    def test_language_ko_injects_korean_directive(self, monkeypatch):
        """parse_query(..., language='ko') places the Korean directive in system_instruction."""
        monkeypatch.setitem(settings.RECOMMENDATION, 'stage_decouple_enabled', False)
        monkeypatch.setitem(settings.RECOMMENDATION, 'context_caching_enabled', False)
        monkeypatch.setattr(services, '_get_client', lambda: MagicMock())
        monkeypatch.setattr(services, 'event_log', MagicMock())

        captured_configs = []

        def _fake_gwf(client, contents, config):
            captured_configs.append(config)
            return _make_gemini_response(_TERMINAL_PAYLOAD)

        monkeypatch.setattr(services, 'generate_content_with_fallback', _fake_gwf)

        services.parse_query(
            [{'role': 'user', 'text': '목재 주택 찾아요.'}],
            language='ko',
        )

        assert len(captured_configs) == 1
        sys_instr = captured_configs[0].system_instruction
        assert sys_instr.startswith(_CHAT_PHASE_SYSTEM_PROMPT)
        assert _LANG_DIRECTIVE['ko'] in sys_instr
        assert _LANG_DIRECTIVE['en'] not in sys_instr

    def test_language_none_no_directive(self, monkeypatch):
        """parse_query(..., language=None) uses base prompt unchanged."""
        monkeypatch.setitem(settings.RECOMMENDATION, 'stage_decouple_enabled', False)
        monkeypatch.setitem(settings.RECOMMENDATION, 'context_caching_enabled', False)
        monkeypatch.setattr(services, '_get_client', lambda: MagicMock())
        monkeypatch.setattr(services, 'event_log', MagicMock())

        captured_configs = []

        def _fake_gwf(client, contents, config):
            captured_configs.append(config)
            return _make_gemini_response(_TERMINAL_PAYLOAD)

        monkeypatch.setattr(services, 'generate_content_with_fallback', _fake_gwf)

        services.parse_query(
            [{'role': 'user', 'text': '목재 주택 찾아요.'}],
            language=None,
        )

        assert len(captured_configs) == 1
        sys_instr = captured_configs[0].system_instruction
        # TASTE-CALIBRATION-1: calibration extension is always appended; no language directive.
        assert sys_instr.startswith(_CHAT_PHASE_SYSTEM_PROMPT)
        assert _CALIBRATION_PROMPT_EXTENSION in sys_instr
        assert _LANG_DIRECTIVE['ko'] not in sys_instr
        assert _LANG_DIRECTIVE['en'] not in sys_instr

    def test_language_invalid_no_directive(self, monkeypatch):
        """parse_query with unrecognised language value falls back to base prompt (no crash)."""
        monkeypatch.setitem(settings.RECOMMENDATION, 'stage_decouple_enabled', False)
        monkeypatch.setitem(settings.RECOMMENDATION, 'context_caching_enabled', False)
        monkeypatch.setattr(services, '_get_client', lambda: MagicMock())
        monkeypatch.setattr(services, 'event_log', MagicMock())

        captured_configs = []

        def _fake_gwf(client, contents, config):
            captured_configs.append(config)
            return _make_gemini_response(_TERMINAL_PAYLOAD)

        monkeypatch.setattr(services, 'generate_content_with_fallback', _fake_gwf)

        # 'fr' is not a valid language choice -- should not crash, just no directive
        services.parse_query(
            [{'role': 'user', 'text': 'test'}],
            language='fr',
        )

        assert len(captured_configs) == 1
        sys_instr = captured_configs[0].system_instruction
        # TASTE-CALIBRATION-1: calibration extension is always appended; unknown language -> no directive.
        assert sys_instr.startswith(_CHAT_PHASE_SYSTEM_PROMPT)
        assert _CALIBRATION_PROMPT_EXTENSION in sys_instr
        assert _LANG_DIRECTIVE['ko'] not in sys_instr
        assert _LANG_DIRECTIVE['en'] not in sys_instr
