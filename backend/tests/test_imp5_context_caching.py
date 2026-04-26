"""
test_imp5_context_caching.py -- IMP-5: Gemini explicit context caching.

Spec v1.5 §11.1: cache the 5924-token bilingual _CHAT_PHASE_SYSTEM_PROMPT in
Gemini's context cache to reduce parse_query TTFT.

Tests:
- TestSettingsDefaults: new settings keys present and default OFF
- TestPromptHashStable: content-hash helper is deterministic and 8 hex chars
- TestEnsureChatCacheLazyInit:
  - cache MISS -> Gemini caches.create() called, resource name stored in Django cache
  - cache HIT  -> caches.create() NOT called; stored name returned directly
  - caches.create() failure -> returns None gracefully (no raise)
- TestParseQueryWithCaching:
  - flag OFF -> uncached path (system_instruction= used, IMP-5 fields =None/'none')
  - flag ON, create succeeds -> cached path (cached_content= used, caching_mode='explicit')
  - flag ON, create fails -> falls back to uncached path transparently
- TestParseQuery404Recovery:
  - flag ON, cache exists in Django, Gemini call raises 404 ->
    Django entry evicted, uncached retry succeeds
- TestParseQueryTimingEventExtended:
  - IMP-5 fields (cache_hit, cached_input_tokens, cache_name_hash, caching_mode)
    present in emitted event in both cached and uncached calls
- TestBackwardCompat:
  - flag OFF -> parse_query returns same shape as before IMP-5
"""
import pytest
from unittest.mock import patch, MagicMock
from django.conf import settings
from django.core.cache import cache


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_FAKE_PARSE_RESULT_JSON = """{
    "probe_needed": false,
    "probe_question": null,
    "reply": "test reply",
    "filters": {
        "location_country": null, "program": null, "material": null, "style": null,
        "year_min": null, "year_max": null, "min_area": null, "max_area": null
    },
    "filter_priority": [],
    "raw_query": "hello",
    "visual_description": "test description"
}"""


def _make_gemini_response(text=_FAKE_PARSE_RESULT_JSON, cached_tokens=None):
    """Build a minimal MagicMock that quacks like a Gemini generate_content response."""
    resp = MagicMock()
    resp.text = text
    usage = MagicMock()
    usage.prompt_token_count = 100
    usage.candidates_token_count = 50
    usage.thoughts_token_count = 0
    usage.cached_content_token_count = cached_tokens
    resp.usage_metadata = usage
    return resp


def _make_cache_obj(name='cachedContents/abc123'):
    obj = MagicMock()
    obj.name = name
    return obj


# ---------------------------------------------------------------------------
# TestSettingsDefaults
# ---------------------------------------------------------------------------

class TestSettingsDefaults:
    def test_context_caching_enabled_defaults_false(self):
        rc = settings.RECOMMENDATION
        assert 'context_caching_enabled' in rc
        assert rc['context_caching_enabled'] is False

    def test_context_caching_ttl_seconds_defaults_3600(self):
        rc = settings.RECOMMENDATION
        assert 'context_caching_ttl_seconds' in rc
        assert rc['context_caching_ttl_seconds'] == 3600


# ---------------------------------------------------------------------------
# TestPromptHashStable
# ---------------------------------------------------------------------------

class TestPromptHashStable:
    def test_hash_is_8_hex_chars(self):
        from apps.recommendation.services import _get_prompt_hash
        h = _get_prompt_hash()
        assert len(h) == 8
        assert all(c in '0123456789abcdef' for c in h)

    def test_hash_is_deterministic(self):
        from apps.recommendation.services import _get_prompt_hash
        assert _get_prompt_hash() == _get_prompt_hash()

    def test_cache_name_contains_prefix_and_hash(self):
        from apps.recommendation.services import _get_cache_name, _get_prompt_hash
        name = _get_cache_name()
        assert name.startswith('archi-tinder-chat-')
        assert name.endswith(_get_prompt_hash())

    def test_django_cache_key_contains_cache_name(self):
        from apps.recommendation.services import _get_django_cache_key, _get_cache_name
        key = _get_django_cache_key()
        assert _get_cache_name() in key


# ---------------------------------------------------------------------------
# TestEnsureChatCacheLazyInit
# ---------------------------------------------------------------------------

class TestEnsureChatCacheLazyInit:
    def setup_method(self):
        cache.clear()

    def test_cache_miss_calls_gemini_create_and_stores_in_django(self):
        from apps.recommendation.services import _ensure_chat_cache, _get_django_cache_key
        mock_client = MagicMock()
        mock_client.caches.create.return_value = _make_cache_obj('cachedContents/xyz999')

        result = _ensure_chat_cache(mock_client)

        assert result == 'cachedContents/xyz999'
        mock_client.caches.create.assert_called_once()
        assert cache.get(_get_django_cache_key()) == 'cachedContents/xyz999'

    def test_cache_hit_skips_gemini_create(self):
        from apps.recommendation.services import _ensure_chat_cache, _get_django_cache_key
        cache.set(_get_django_cache_key(), 'cachedContents/existing', timeout=3600)
        mock_client = MagicMock()

        result = _ensure_chat_cache(mock_client)

        assert result == 'cachedContents/existing'
        mock_client.caches.create.assert_not_called()

    def test_gemini_create_failure_returns_none_gracefully(self):
        from apps.recommendation.services import _ensure_chat_cache, _get_django_cache_key
        mock_client = MagicMock()
        mock_client.caches.create.side_effect = RuntimeError('quota exceeded')

        result = _ensure_chat_cache(mock_client)

        assert result is None
        assert cache.get(_get_django_cache_key()) is None

    def test_gemini_create_uses_correct_model_and_ttl(self):
        from apps.recommendation.services import _ensure_chat_cache
        mock_client = MagicMock()
        mock_client.caches.create.return_value = _make_cache_obj('cachedContents/t1')

        _ensure_chat_cache(mock_client)

        create_kwargs = mock_client.caches.create.call_args
        assert create_kwargs is not None
        # model positional-or-keyword arg
        bound = create_kwargs
        model_arg = bound.kwargs.get('model') or (bound.args[0] if bound.args else None)
        assert model_arg == 'gemini-2.5-flash'

    def test_gemini_create_config_ttl_matches_setting(self):
        from apps.recommendation.services import _ensure_chat_cache
        mock_client = MagicMock()
        mock_client.caches.create.return_value = _make_cache_obj('cachedContents/t2')

        with self.settings_override(context_caching_ttl_seconds=7200):
            _ensure_chat_cache(mock_client)

        create_call = mock_client.caches.create.call_args
        config_arg = create_call.kwargs.get('config') or create_call.args[1]
        # Verify the TTL string '7200s' was passed through to the config
        assert config_arg is not None
        assert config_arg.ttl == '7200s'

    def settings_override(self, **kwargs):
        """Context manager: temporarily override RECOMMENDATION keys."""
        return _RecommendationOverride(**kwargs)


class _RecommendationOverride:
    """Minimal context manager to override RECOMMENDATION dict keys in tests."""
    def __init__(self, **overrides):
        self._overrides = overrides
        self._original = {}

    def __enter__(self):
        rc = settings.RECOMMENDATION
        for k, v in self._overrides.items():
            self._original[k] = rc.get(k)
            rc[k] = v
        return self

    def __exit__(self, *args):
        rc = settings.RECOMMENDATION
        for k, v in self._original.items():
            if v is None:
                rc.pop(k, None)
            else:
                rc[k] = v


# ---------------------------------------------------------------------------
# TestParseQueryWithCaching
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestParseQueryWithCaching:
    def setup_method(self):
        cache.clear()

    def test_flag_off_uses_uncached_path(self):
        """Flag OFF -> system_instruction in config, IMP-5 fields absent/none."""
        from apps.recommendation.services import parse_query

        mock_resp = _make_gemini_response(cached_tokens=None)
        emitted_events = []

        with patch('apps.recommendation.services._get_client') as mock_gc, \
             patch('apps.recommendation.services.event_log.emit_event',
                   side_effect=lambda *a, **kw: emitted_events.append((a, kw))):
            mock_client = MagicMock()
            mock_client.models.generate_content.return_value = mock_resp
            mock_gc.return_value = mock_client

            with _RecommendationOverride(context_caching_enabled=False):
                result = parse_query('hello')

        assert result is not None
        assert result.get('probe_needed') is False

        # Verify generate_content was called with system_instruction (not cached_content)
        call_config = mock_client.models.generate_content.call_args.kwargs.get('config')
        assert call_config is not None
        # cached_content should be None/unset; system_instruction should be set
        assert getattr(call_config, 'system_instruction', None) is not None
        assert not getattr(call_config, 'cached_content', None)

        # Check timing event for IMP-5 fields
        timing_events = [e for e in emitted_events if e[0][0] == 'parse_query_timing']
        assert len(timing_events) == 1
        kw = timing_events[0][1]
        assert kw.get('caching_mode') == 'none'
        assert kw.get('cache_name_hash') is None

    def test_flag_on_cached_path_uses_cached_content_arg(self):
        """Flag ON, create succeeds -> cached_content= used, caching_mode='explicit'."""
        from apps.recommendation.services import parse_query

        mock_resp = _make_gemini_response(cached_tokens=5924)
        emitted_events = []

        with patch('apps.recommendation.services._get_client') as mock_gc, \
             patch('apps.recommendation.services._ensure_chat_cache',
                   return_value='cachedContents/live123') as mock_ensure, \
             patch('apps.recommendation.services.event_log.emit_event',
                   side_effect=lambda *a, **kw: emitted_events.append((a, kw))):
            mock_client = MagicMock()
            mock_client.models.generate_content.return_value = mock_resp
            mock_gc.return_value = mock_client

            with _RecommendationOverride(context_caching_enabled=True):
                result = parse_query('museum query')

        assert result is not None
        mock_ensure.assert_called_once_with(mock_client)

        call_config = mock_client.models.generate_content.call_args.kwargs.get('config')
        assert getattr(call_config, 'cached_content', None) == 'cachedContents/live123'
        # system_instruction should NOT be set on cached path
        assert not getattr(call_config, 'system_instruction', None)

        timing_events = [e for e in emitted_events if e[0][0] == 'parse_query_timing']
        assert len(timing_events) == 1
        kw = timing_events[0][1]
        assert kw.get('caching_mode') == 'explicit'
        assert kw.get('cache_hit') is True
        assert kw.get('cached_input_tokens') == 5924

    def test_flag_on_ensure_fails_falls_back_uncached(self):
        """Flag ON, _ensure_chat_cache returns None -> falls back to uncached path."""
        from apps.recommendation.services import parse_query

        mock_resp = _make_gemini_response(cached_tokens=None)
        emitted_events = []

        with patch('apps.recommendation.services._get_client') as mock_gc, \
             patch('apps.recommendation.services._ensure_chat_cache', return_value=None), \
             patch('apps.recommendation.services.event_log.emit_event',
                   side_effect=lambda *a, **kw: emitted_events.append((a, kw))):
            mock_client = MagicMock()
            mock_client.models.generate_content.return_value = mock_resp
            mock_gc.return_value = mock_client

            with _RecommendationOverride(context_caching_enabled=True):
                result = parse_query('museum query')

        assert result is not None

        call_config = mock_client.models.generate_content.call_args.kwargs.get('config')
        assert getattr(call_config, 'system_instruction', None) is not None

        timing_events = [e for e in emitted_events if e[0][0] == 'parse_query_timing']
        kw = timing_events[0][1]
        assert kw.get('caching_mode') == 'none'


# ---------------------------------------------------------------------------
# TestParseQuery404Recovery
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestParseQuery404Recovery:
    def setup_method(self):
        cache.clear()

    def test_gemini_404_evicts_django_cache_and_retries_uncached(self):
        """Gemini call with cache raises 404 -> Django evicted, uncached retry succeeds."""
        from apps.recommendation.services import parse_query, _get_django_cache_key

        # Seed the Django cache with a stale resource name
        cache.set(_get_django_cache_key(), 'cachedContents/stale', timeout=3600)

        mock_resp = _make_gemini_response(cached_tokens=None)
        call_count = {'n': 0}

        def fake_generate_content(model, contents, config):
            call_count['n'] += 1
            cached = getattr(config, 'cached_content', None)
            if cached == 'cachedContents/stale':
                raise Exception('404 Resource not found: NOT_FOUND')
            return mock_resp

        with patch('apps.recommendation.services._get_client') as mock_gc, \
             patch('apps.recommendation.services._ensure_chat_cache',
                   return_value='cachedContents/stale'), \
             patch('apps.recommendation.services.event_log.emit_event'):
            mock_client = MagicMock()
            mock_client.models.generate_content.side_effect = fake_generate_content
            mock_gc.return_value = mock_client

            with _RecommendationOverride(context_caching_enabled=True):
                result = parse_query('hello')

        assert result is not None
        assert result.get('probe_needed') is False
        # Django cache entry must have been evicted
        assert cache.get(_get_django_cache_key()) is None
        # _retry_gemini_call fires 2 attempts with cached path (initial + 1 retry)
        # before the 404 handler catches it; then 1 more uncached call succeeds.
        # Total = 3.
        assert call_count['n'] == 3

    def test_non_404_exception_propagates_to_fallback(self):
        """Non-404 Gemini error should not be swallowed by the 404 handler."""
        from apps.recommendation.services import parse_query

        with patch('apps.recommendation.services._get_client') as mock_gc, \
             patch('apps.recommendation.services._ensure_chat_cache', return_value=None), \
             patch('apps.recommendation.services.event_log.emit_event'):
            mock_client = MagicMock()
            mock_client.models.generate_content.side_effect = RuntimeError('network error')
            mock_gc.return_value = mock_client

            with _RecommendationOverride(context_caching_enabled=False):
                result = parse_query('hello')

        # Should return the fallback dict, not raise
        assert result is not None
        assert result.get('reply') == '이해를 잘 못 했어요. 일단 이 쪽으로 찾아볼게요.'


# ---------------------------------------------------------------------------
# TestParseQueryTimingEventExtended
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestParseQueryTimingEventExtended:
    def setup_method(self):
        cache.clear()

    def test_uncached_call_emits_none_imp5_fields(self):
        from apps.recommendation.services import parse_query

        mock_resp = _make_gemini_response(cached_tokens=None)
        emitted_events = []

        with patch('apps.recommendation.services._get_client') as mock_gc, \
             patch('apps.recommendation.services.event_log.emit_event',
                   side_effect=lambda *a, **kw: emitted_events.append((a, kw))):
            mock_client = MagicMock()
            mock_client.models.generate_content.return_value = mock_resp
            mock_gc.return_value = mock_client

            with _RecommendationOverride(context_caching_enabled=False):
                parse_query('hello')

        timing = next(e for e in emitted_events if e[0][0] == 'parse_query_timing')
        kw = timing[1]
        # Existing fields preserved
        assert 'gemini_total_ms' in kw
        assert 'ttft_ms' in kw
        assert 'gen_ms' in kw
        assert 'input_tokens' in kw
        assert 'output_tokens' in kw
        assert 'thinking_tokens' in kw
        # IMP-5 fields present, values correct for uncached
        assert 'cache_hit' in kw
        assert 'cached_input_tokens' in kw
        assert 'cache_name_hash' in kw
        assert 'caching_mode' in kw
        assert kw['caching_mode'] == 'none'
        assert kw['cache_name_hash'] is None

    def test_cached_call_emits_explicit_caching_mode(self):
        from apps.recommendation.services import parse_query

        mock_resp = _make_gemini_response(cached_tokens=5924)
        emitted_events = []

        with patch('apps.recommendation.services._get_client') as mock_gc, \
             patch('apps.recommendation.services._ensure_chat_cache',
                   return_value='cachedContents/live'), \
             patch('apps.recommendation.services.event_log.emit_event',
                   side_effect=lambda *a, **kw: emitted_events.append((a, kw))):
            mock_client = MagicMock()
            mock_client.models.generate_content.return_value = mock_resp
            mock_gc.return_value = mock_client

            with _RecommendationOverride(context_caching_enabled=True):
                parse_query('museum')

        timing = next(e for e in emitted_events if e[0][0] == 'parse_query_timing')
        kw = timing[1]
        assert kw['caching_mode'] == 'explicit'
        assert kw['cache_hit'] is True
        assert kw['cached_input_tokens'] == 5924
        from apps.recommendation.services import _get_prompt_hash
        assert kw['cache_name_hash'] == _get_prompt_hash()


# ---------------------------------------------------------------------------
# TestBackwardCompat
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestBackwardCompat:
    def setup_method(self):
        cache.clear()

    def test_flag_off_parse_query_returns_correct_shape(self):
        """Flag OFF: parse_query returns the same dict shape as before IMP-5."""
        from apps.recommendation.services import parse_query

        mock_resp = _make_gemini_response()

        with patch('apps.recommendation.services._get_client') as mock_gc, \
             patch('apps.recommendation.services.event_log.emit_event'):
            mock_client = MagicMock()
            mock_client.models.generate_content.return_value = mock_resp
            mock_gc.return_value = mock_client

            with _RecommendationOverride(context_caching_enabled=False):
                result = parse_query([{'role': 'user', 'text': 'hello'}])

        expected_keys = {
            'probe_needed', 'probe_question', 'reply', 'filters',
            'filter_priority', 'raw_query', 'visual_description',
        }
        assert set(result.keys()) == expected_keys

    def test_flag_off_bare_string_input_still_works(self):
        """Bare-string legacy caller still functions with IMP-5 present."""
        from apps.recommendation.services import parse_query

        mock_resp = _make_gemini_response()

        with patch('apps.recommendation.services._get_client') as mock_gc, \
             patch('apps.recommendation.services.event_log.emit_event'):
            mock_client = MagicMock()
            mock_client.models.generate_content.return_value = mock_resp
            mock_gc.return_value = mock_client

            with _RecommendationOverride(context_caching_enabled=False):
                result = parse_query('museo en agua')

        assert isinstance(result, dict)
        assert result.get('raw_query') == 'hello'  # verbatim from fake JSON response

        # Verify the bare string was actually wrapped into a single-turn contents list
        # (not passed as a raw string). parse_query wraps bare strings as:
        #   [{'role': 'user', 'text': input}] -> types.Content(role='user', parts=[...])
        contents = mock_client.models.generate_content.call_args.kwargs['contents']
        assert isinstance(contents, list), 'bare-string input must be wrapped to a list'
        assert len(contents) == 1, 'bare-string should produce exactly one Content turn'
        # SDK Content object shape: .role str, .parts list of Part objects with .text
        first = contents[0]
        assert first.role == 'user'
        assert len(first.parts) == 1
        assert first.parts[0].text == 'museo en agua'
