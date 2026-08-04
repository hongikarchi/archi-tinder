"""
test_llm_provider.py -- BACK-LLM-PROVIDER-1: OpenAI provider dispatch tests.

Covers the text-parse path A/B provider switch in
apps.recommendation.services._gemini:
  1. default provider (gemini) -> _get_client() builds a genai.Client.
  2. LLM_PROVIDER=openai -> _get_client() builds an openai.OpenAI singleton.
  3. _dispatch_generate openai path: chat.completions.create -> _NormalizedResponse
     .text / .usage_metadata.{prompt_token_count,candidates_token_count} correct.
  4. contents translation: genai types.Content list (user/model roles) ->
     messages (user/assistant) in order, system_instruction prepended.
  5. json mode: response_mime_type='application/json' -> response_format
     json_object + a JSON instruction note in the system message.
  6. error taxonomy: openai.APIStatusError -> _is_fatal_gemini / _is_model_unavailable
     match the SAME 4xx-except-429-fatal / 400|404-unavailable logic as Gemini.
  7. fairness: the timeout kwarg passes through to _retry_gemini_call unchanged
     on both dispatch branches.

No real Gemini or OpenAI API calls are made. Module-level singletons
(_gemini._client / _gemini._gemini_client) are reset around every test that
touches _get_client()/_get_gemini_client() to avoid cross-test leakage.
"""
from unittest.mock import MagicMock

import httpx
import openai
import pytest
from django.test import override_settings
from google.genai import types

from apps.recommendation.services import _gemini


@pytest.fixture(autouse=True)
def _reset_client_singletons():
    """Reset both module-level client singletons before and after each test."""
    _gemini._client = None
    _gemini._gemini_client = None
    yield
    _gemini._client = None
    _gemini._gemini_client = None


def _make_status_error(status_code, message='error'):
    """Build a real openai.APIStatusError with the given HTTP status code."""
    request = httpx.Request('POST', 'https://api.openai.com/v1/chat/completions')
    response = httpx.Response(status_code, request=request)
    return openai.APIStatusError(message, response=response, body=None)


# ---------------------------------------------------------------------------
# 1 + 2: _get_client() provider dispatch
# ---------------------------------------------------------------------------

class TestGetClientProviderDispatch:

    def test_default_provider_gemini_builds_genai_client(self, monkeypatch):
        """Default LLM_PROVIDER='gemini' -> _get_client() returns a genai.Client
        built via genai.Client(api_key=...), NOT an OpenAI client."""
        sentinel = MagicMock(name='genai_client_instance')
        mock_genai_client_cls = MagicMock(return_value=sentinel)
        monkeypatch.setattr(_gemini.genai, 'Client', mock_genai_client_cls)

        with override_settings(LLM_PROVIDER='gemini', GEMINI_API_KEY='fake-gemini-key'):
            client = _gemini._get_client()

        assert client is sentinel
        mock_genai_client_cls.assert_called_once_with(api_key='fake-gemini-key')

    def test_openai_provider_builds_openai_singleton(self, monkeypatch):
        """LLM_PROVIDER='openai' -> _get_client() builds openai.OpenAI(api_key=...)."""
        sentinel = MagicMock(name='openai_client_instance')
        mock_openai_cls = MagicMock(return_value=sentinel)
        monkeypatch.setattr(openai, 'OpenAI', mock_openai_cls)

        with override_settings(LLM_PROVIDER='openai', OPENAI_API_KEY='fake-openai-key'):
            client = _gemini._get_client()

        assert client is sentinel
        mock_openai_cls.assert_called_once_with(api_key='fake-openai-key')

    def test_openai_provider_client_is_singleton(self, monkeypatch):
        """Second _get_client() call under LLM_PROVIDER=openai reuses the same
        module-level singleton (no second OpenAI() construction)."""
        mock_openai_cls = MagicMock(side_effect=lambda **kw: MagicMock())
        monkeypatch.setattr(openai, 'OpenAI', mock_openai_cls)

        with override_settings(LLM_PROVIDER='openai', OPENAI_API_KEY='fake-openai-key'):
            first = _gemini._get_client()
            second = _gemini._get_client()

        assert first is second
        mock_openai_cls.assert_called_once()

    def test_get_gemini_client_always_genai_regardless_of_provider(self, monkeypatch):
        """_get_gemini_client() always builds a genai.Client, even when
        LLM_PROVIDER='openai' -- the image path's escape hatch."""
        sentinel = MagicMock(name='genai_client_instance')
        mock_genai_client_cls = MagicMock(return_value=sentinel)
        monkeypatch.setattr(_gemini.genai, 'Client', mock_genai_client_cls)

        with override_settings(LLM_PROVIDER='openai', GEMINI_API_KEY='fake-gemini-key'):
            client = _gemini._get_gemini_client()

        assert client is sentinel
        mock_genai_client_cls.assert_called_once_with(api_key='fake-gemini-key')

    def test_get_gemini_client_independent_singleton_from_get_client(self, monkeypatch):
        """_gemini_client and _client are separate singletons -- building one
        does not populate the other."""
        monkeypatch.setattr(_gemini.genai, 'Client', lambda **kw: MagicMock())
        monkeypatch.setattr(openai, 'OpenAI', lambda **kw: MagicMock())

        with override_settings(LLM_PROVIDER='openai', OPENAI_API_KEY='k', GEMINI_API_KEY='k'):
            _gemini._get_client()
            assert _gemini._gemini_client is None  # not built yet
            _gemini._get_gemini_client()
            assert _gemini._gemini_client is not None
            assert _gemini._client is not _gemini._gemini_client


# ---------------------------------------------------------------------------
# 3: _dispatch_generate openai path — normalization
# ---------------------------------------------------------------------------

class TestDispatchGenerateOpenaiNormalization:

    def _make_chat_completion(
        self, text='{"ok": true}', prompt_tokens=42,
        completion_tokens=7, cached_tokens=None,
    ):
        message = MagicMock()
        message.content = text
        choice = MagicMock()
        choice.message = message
        completion = MagicMock()
        completion.choices = [choice]

        usage = MagicMock()
        usage.prompt_tokens = prompt_tokens
        usage.completion_tokens = completion_tokens
        if cached_tokens is not None:
            details = MagicMock()
            details.cached_tokens = cached_tokens
            usage.prompt_tokens_details = details
        else:
            usage.prompt_tokens_details = None
        completion.usage = usage
        return completion

    def test_normalized_text_and_usage(self, monkeypatch):
        completion = self._make_chat_completion(
            text='{"filters": {}}', prompt_tokens=100, completion_tokens=20, cached_tokens=15,
        )
        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = completion

        with override_settings(LLM_PROVIDER='openai'):
            response = _gemini._dispatch_generate(
                mock_client,
                model='gpt-5.6-luna',
                contents='hello',
                config=None,
                timeout=15.0,
            )

        assert response.text == '{"filters": {}}'
        assert response.usage_metadata.prompt_token_count == 100
        assert response.usage_metadata.candidates_token_count == 20
        assert response.usage_metadata.cached_content_token_count == 15
        assert response.model_version == 'gpt-5.6-luna'

    def test_normalized_response_no_cached_tokens(self, monkeypatch):
        """When prompt_tokens_details is absent, cached_content_token_count is None."""
        completion = self._make_chat_completion(cached_tokens=None)
        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = completion

        with override_settings(LLM_PROVIDER='openai'):
            response = _gemini._dispatch_generate(
                mock_client, model='gpt-5.6-luna', contents='hi', config=None, timeout=15.0,
            )

        assert response.usage_metadata.cached_content_token_count is None

    def test_gemini_path_returns_raw_response_unchanged(self):
        """Gemini path (default provider): _dispatch_generate returns the raw
        response object from client.models.generate_content, NOT normalized."""
        raw_response = MagicMock()
        raw_response.text = '{"raw": true}'
        mock_client = MagicMock()
        mock_client.models.generate_content.return_value = raw_response

        with override_settings(LLM_PROVIDER='gemini'):
            response = _gemini._dispatch_generate(
                mock_client, model='gemini-x', contents='hi',
                config=types.GenerateContentConfig(), timeout=15.0,
            )

        assert response is raw_response
        mock_client.models.generate_content.assert_called_once()


# ---------------------------------------------------------------------------
# 4: contents translation
# ---------------------------------------------------------------------------

class TestTranslateContentsToMessages:

    def test_string_contents_single_user_message(self):
        messages = _gemini._translate_contents_to_messages('hello world', None)
        assert messages == [{'role': 'user', 'content': 'hello world'}]

    def test_genai_content_list_role_mapping_and_order(self):
        contents = [
            types.Content(role='user', parts=[types.Part.from_text(text='first')]),
            types.Content(role='model', parts=[types.Part.from_text(text='second')]),
            types.Content(role='user', parts=[types.Part.from_text(text='third')]),
        ]
        messages = _gemini._translate_contents_to_messages(contents, None)

        assert messages == [
            {'role': 'user', 'content': 'first'},
            {'role': 'assistant', 'content': 'second'},
            {'role': 'user', 'content': 'third'},
        ]

    def test_system_instruction_prepended(self):
        config = types.GenerateContentConfig(system_instruction='You are helpful.')
        messages = _gemini._translate_contents_to_messages('hi', config)

        assert messages[0] == {'role': 'system', 'content': 'You are helpful.'}
        assert messages[1] == {'role': 'user', 'content': 'hi'}

    def test_no_system_instruction_no_system_message(self):
        config = types.GenerateContentConfig(temperature=0.2)
        messages = _gemini._translate_contents_to_messages('hi', config)

        assert all(m['role'] != 'system' for m in messages)


# ---------------------------------------------------------------------------
# 5: json mode translation
# ---------------------------------------------------------------------------

class TestJsonModeTranslation:

    def test_json_mode_sets_response_format_and_system_note(self, monkeypatch):
        completion = MagicMock()
        completion.choices = [MagicMock(message=MagicMock(content='{}'))]
        completion.usage = None
        mock_client = MagicMock()
        captured = {}

        def _fake_create(**kwargs):
            captured.update(kwargs)
            return completion

        mock_client.chat.completions.create.side_effect = _fake_create

        config = types.GenerateContentConfig(
            system_instruction='System prompt text.',
            response_mime_type='application/json',
            temperature=0.2,
        )

        with override_settings(LLM_PROVIDER='openai'):
            _gemini._dispatch_generate(
                mock_client, model='gpt-5.6-luna', contents='hi', config=config, timeout=15.0,
            )

        assert captured['response_format'] == {'type': 'json_object'}
        system_msg = next(m for m in captured['messages'] if m['role'] == 'system')
        assert 'JSON' in system_msg['content']
        assert 'System prompt text.' in system_msg['content']
        # temperature is intentionally NOT forwarded on the openai path
        # (gpt-5.x reasoning models 400 on non-default values).
        assert 'temperature' not in captured

    def test_json_mode_without_system_instruction_still_notes_json(self):
        completion = MagicMock()
        completion.choices = [MagicMock(message=MagicMock(content='{}'))]
        completion.usage = None
        mock_client = MagicMock()
        captured = {}

        def _fake_create(**kwargs):
            captured.update(kwargs)
            return completion

        mock_client.chat.completions.create.side_effect = _fake_create

        config = types.GenerateContentConfig(response_mime_type='application/json')

        with override_settings(LLM_PROVIDER='openai'):
            _gemini._dispatch_generate(
                mock_client, model='gpt-5.6-luna', contents='hi', config=config, timeout=15.0,
            )

        system_msgs = [m for m in captured['messages'] if m['role'] == 'system']
        assert len(system_msgs) == 1
        assert 'JSON' in system_msgs[0]['content']

    def test_response_schema_ignored_on_openai_path(self):
        """config.response_schema must NOT be forwarded to chat.completions.create --
        json mode stays json_object-only (non-strict)."""
        completion = MagicMock()
        completion.choices = [MagicMock(message=MagicMock(content='{}'))]
        completion.usage = None
        mock_client = MagicMock()
        captured = {}

        def _fake_create(**kwargs):
            captured.update(kwargs)
            return completion

        mock_client.chat.completions.create.side_effect = _fake_create

        config = types.GenerateContentConfig(
            response_mime_type='application/json',
            response_schema={'type': 'OBJECT', 'required': ['a', 'b']},
        )

        with override_settings(LLM_PROVIDER='openai'):
            _gemini._dispatch_generate(
                mock_client, model='gpt-5.6-luna', contents='hi', config=config, timeout=15.0,
            )

        assert 'response_schema' not in captured
        assert 'json_schema' not in captured
        assert captured['response_format'] == {'type': 'json_object'}


# ---------------------------------------------------------------------------
# 6: error taxonomy — openai.APIStatusError
# ---------------------------------------------------------------------------

class TestErrorTaxonomyOpenai:

    def test_403_is_fatal_no_retry(self):
        e = _make_status_error(403)
        assert _gemini._is_fatal_gemini(e) is True

    def test_429_is_not_fatal_retries(self):
        e = _make_status_error(429)
        assert _gemini._is_fatal_gemini(e) is False

    def test_404_is_model_unavailable(self):
        e = _make_status_error(404)
        assert _gemini._is_model_unavailable(e) is True

    def test_400_is_model_unavailable(self):
        e = _make_status_error(400)
        assert _gemini._is_model_unavailable(e) is True

    def test_403_is_not_model_unavailable(self):
        """403 (auth) must NOT trigger model-fallback -- a different model on the
        same key won't fix an auth error."""
        e = _make_status_error(403)
        assert _gemini._is_model_unavailable(e) is False

    def test_500_is_not_fatal(self):
        e = _make_status_error(500)
        assert _gemini._is_fatal_gemini(e) is False

    def test_retry_gemini_call_fast_fails_on_403_openai_error(self, monkeypatch):
        """End-to-end: _retry_gemini_call must fast-fail (no retry) on a fatal
        openai.APIStatusError, exactly like it does for genai ClientError."""
        fn = MagicMock(side_effect=_make_status_error(403))
        with pytest.raises(openai.APIStatusError):
            _gemini._retry_gemini_call(fn, timeout=10.0)
        fn.assert_called_once()

    def test_retry_gemini_call_retries_on_429_openai_error(self, monkeypatch):
        """429 is transient -- _retry_gemini_call retries once."""
        monkeypatch.setattr(_gemini.time, 'sleep', lambda _: None)
        fn = MagicMock(side_effect=_make_status_error(429))
        with pytest.raises(openai.APIStatusError):
            _gemini._retry_gemini_call(fn, timeout=10.0)
        assert fn.call_count == 2


# ---------------------------------------------------------------------------
# 7: fairness — timeout kwarg passthrough
# ---------------------------------------------------------------------------

class TestTimeoutFairness:

    def test_openai_path_forwards_timeout_to_retry_gemini_call(self, monkeypatch):
        """_dispatch_generate's openai branch must invoke the SAME
        _retry_gemini_call wrapper (via the services facade) with the caller's
        timeout value unchanged."""
        completion = MagicMock()
        completion.choices = [MagicMock(message=MagicMock(content='{}'))]
        completion.usage = None
        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = completion

        captured_timeout = {}
        real_retry = _gemini._retry_gemini_call

        def _spy_retry(func, *args, timeout=15.0, **kwargs):
            captured_timeout['value'] = timeout
            return real_retry(func, *args, timeout=timeout, **kwargs)

        from apps.recommendation import services as _svc
        monkeypatch.setattr(_svc, '_retry_gemini_call', _spy_retry)

        with override_settings(LLM_PROVIDER='openai'):
            _gemini._dispatch_generate(
                mock_client, model='gpt-5.6-luna', contents='hi', config=None, timeout=8.5,
            )

        assert captured_timeout['value'] == 8.5

    def test_default_timeout_is_15s_both_providers(self, monkeypatch):
        """generate_content_with_fallback's default timeout=15.0 is unchanged and
        applies identically regardless of provider."""
        from apps.recommendation.services._gemini import generate_content_with_fallback
        import inspect

        sig = inspect.signature(generate_content_with_fallback)
        assert sig.parameters['timeout'].default == 15.0

    def test_gemini_path_forwards_timeout_unchanged(self, monkeypatch):
        """Gemini path: timeout kwarg reaches _retry_gemini_call unchanged (no
        provider-based deadline skew -- fairness for A/B testing)."""
        raw_response = MagicMock()
        raw_response.text = '{}'
        mock_client = MagicMock()
        mock_client.models.generate_content.return_value = raw_response

        captured_timeout = {}
        real_retry = _gemini._retry_gemini_call

        def _spy_retry(func, *args, timeout=15.0, **kwargs):
            captured_timeout['value'] = timeout
            return real_retry(func, *args, timeout=timeout, **kwargs)

        from apps.recommendation import services as _svc
        monkeypatch.setattr(_svc, '_retry_gemini_call', _spy_retry)

        with override_settings(LLM_PROVIDER='gemini'):
            _gemini._dispatch_generate(
                mock_client, model='gemini-x', contents='hi',
                config=types.GenerateContentConfig(), timeout=8.5,
            )

        assert captured_timeout['value'] == 8.5


# ---------------------------------------------------------------------------
# generate_content_with_fallback: openai path has no model-fallback swap
# ---------------------------------------------------------------------------

class TestGenerateContentWithFallbackOpenaiNoSwap:

    def test_openai_path_single_model_no_fallback_reraise(self, monkeypatch):
        """On model-unavailable (404), the openai path re-raises instead of
        swapping to a fallback model (unlike the gemini dual-model path)."""
        from apps.recommendation.services._gemini import generate_content_with_fallback

        mock_client = MagicMock()
        mock_client.chat.completions.create.side_effect = _make_status_error(404)
        monkeypatch.setattr(_gemini.time, 'sleep', lambda _: None)

        with override_settings(LLM_PROVIDER='openai', OPENAI_TEXT_MODEL='gpt-5.6-luna'):
            with pytest.raises(openai.APIStatusError):
                generate_content_with_fallback(mock_client, contents='hello')

        # Called at most twice (the _retry_gemini_call transient-would-be-retry
        # path never fires for a fatal-shaped 404 the way NotFound genai fallback
        # does) -- critically, chat.completions.create is never invoked with a
        # second *different* model, because there is only ever one openai model.
        models_used = {
            c.kwargs.get('model') for c in mock_client.chat.completions.create.call_args_list
        }
        assert models_used == {'gpt-5.6-luna'}
