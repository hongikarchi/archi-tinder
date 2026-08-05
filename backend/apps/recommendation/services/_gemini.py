"""
_gemini.py -- Low-level Gemini API client wrapper and retry logic.

BACK-LLM-PROVIDER-1: provider dispatch (gemini | openai) behind settings.LLM_PROVIDER,
for A/B testing the text-parse path via tools/db_qc.py. Image generation
(generation.py _gen_native) previously was pinned to Gemini regardless of
LLM_PROVIDER via _get_gemini_client() -- see that function's docstring.

BACK-LLM-PROVIDER-2: image generation now has its OWN independent switch,
settings.LLM_IMAGE_PROVIDER (gemini|openai, default gemini) -- separate from
LLM_PROVIDER so text/image providers mix freely. _get_gemini_client() and
_get_openai_client() are the two always-provider-X escape hatches _gen_native
picks between; _get_client() (the LLM_PROVIDER-switched seam) is unaffected
and remains text-path-only.

Self-contained: no imports from sibling sub-modules (LLM-AB-KNOB-1's
_OPENAI_STRICT_PARSE_SCHEMA is the sole exception, and it is imported
lazily INSIDE _dispatch_generate's openai branch to preserve this at
module-import time).
"""
import logging
import queue
import time
from threading import Thread as _Thread

from django.conf import settings
from google import genai
from google.api_core import exceptions as gax_exceptions
from google.genai import errors as genai_errors

logger = logging.getLogger('apps.recommendation')

# `_Thread` captures the real `threading.Thread` class at module-load time
# so the timeout wrapper is immune to tests that mock `threading.Thread`
# globally (e.g. `_DiscThread` in test_imp8_async_prefetch.py). Without this
# capture, a leaked synchronous Thread mock would make hung Gemini calls
# return their value before the deadline can fire, breaking the timeout
# guarantee that production depends on.

_client = None

# BACK-LLM-PROVIDER-1: separate singleton for the always-Gemini client used by
# the image path (generation.py _gen_native), independent of LLM_PROVIDER/_client.
_gemini_client = None

# BACK-LLM-PROVIDER-2: separate singleton for the always-OpenAI client used by
# the image path when settings.LLM_IMAGE_PROVIDER='openai', independent of
# LLM_PROVIDER/_client and of _gemini_client above.
_openai_client = None

_GEMINI_MAX_RETRIES = 1
_GEMINI_RETRY_DELAY = 1.0  # seconds

# Permanent errors — retry provides no benefit; fast-fail immediately.
# 403/401/400/404 indicate a config or auth issue that won't resolve on retry.
# NOTE: the live google-genai SDK (v1.x, api_key backend) raises
# google.genai.errors.ClientError/ServerError with an HTTP .code — NOT the
# google.api_core.exceptions.* family. The gax tuple below is kept only for
# defensive/legacy compatibility; _is_fatal_gemini() handles BOTH families.
_FATAL_GEMINI_EXC = (
    gax_exceptions.PermissionDenied,   # 403
    gax_exceptions.Unauthenticated,    # 401
    gax_exceptions.InvalidArgument,    # 400
    gax_exceptions.NotFound,           # 404
)


def _is_openai_status_error(e):
    """Lazy-import openai and return True iff e is an openai.APIStatusError.

    Lazy import keeps import-time cost at zero when LLM_PROVIDER=gemini (the
    default) and openai is merely installed, not used. Returns False (not an
    exception) when openai is not importable at all.
    """
    try:
        import openai
    except ImportError:
        return False
    return isinstance(e, openai.APIStatusError)


def _is_fatal_gemini(e):
    """
    True if e is a permanent Gemini/OpenAI error that must NOT be retried.

    google-genai ClientError carries an HTTP .code: any 4xx is permanent
    EXCEPT 429 (rate limit — transient, should retry). ServerError (5xx) is
    transient. Falls back to the legacy gax tuple for non-google-genai paths.

    BACK-LLM-PROVIDER-1: openai.APIStatusError carries .status_code with the
    SAME semantics (4xx fatal except 429) -- same function, same name, so
    _retry_gemini_call's fast-fail branch works unmodified for both providers.
    """
    if isinstance(e, genai_errors.ClientError):
        code = getattr(e, 'code', None)
        return code is not None and 400 <= code < 500 and code != 429
    if _is_openai_status_error(e):
        code = getattr(e, 'status_code', None)
        return code is not None and 400 <= code < 500 and code != 429
    return isinstance(e, _FATAL_GEMINI_EXC)


def _is_model_unavailable(e):
    """
    True if e signals the requested MODEL is unavailable/invalid (404 NotFound
    or 400 InvalidArgument) — the case where retrying with a fallback model
    helps. Excludes 401/403 (auth — a different model on the same key won't
    help). Recognises the google-genai ClientError family, legacy gax, and
    (BACK-LLM-PROVIDER-1) openai.APIStatusError via the same 400/404 codes.
    """
    if isinstance(e, genai_errors.ClientError):
        return getattr(e, 'code', None) in (400, 404)
    if _is_openai_status_error(e):
        return getattr(e, 'status_code', None) in (400, 404)
    return isinstance(e, (gax_exceptions.NotFound, gax_exceptions.InvalidArgument))


def _get_client():
    """Provider-switched client seam.

    LLM_PROVIDER='openai' -> lazy-import openai, build/return a module-level
    OpenAI singleton. Default ('gemini') -> existing genai.Client path,
    UNCHANGED (byte-for-byte identical behaviour to pre-BACK-LLM-PROVIDER-1).

    KEEP THIS NAME: ~45 existing tests patch
    'apps.recommendation.services._get_client' — this is the provider-dispatch
    boundary per the BACK-LLM-PROVIDER-1 design; no parallel provider-prefixed
    public function is introduced.
    """
    global _client
    if settings.LLM_PROVIDER == 'openai':
        if _client is None:
            import openai  # noqa: PLC0415 -- lazy: zero import cost on the gemini path
            _client = openai.OpenAI(api_key=settings.OPENAI_API_KEY)
        return _client
    if _client is None:
        _client = genai.Client(api_key=settings.GEMINI_API_KEY)
    return _client


def _get_gemini_client():
    """Always-Gemini client, independent of settings.LLM_PROVIDER.

    BACK-LLM-PROVIDER-1: the image-generation path (generation.py _gen_native)
    calls client.models.generate_content directly -- an OpenAI client has no
    such attribute, so that path must never receive the provider-switched
    client from _get_client() when LLM_PROVIDER='openai'. This function is the
    dedicated escape hatch: a SEPARATE module-level singleton
    (_gemini_client), always genai.Client, regardless of LLM_PROVIDER.
    _get_client() remains the sole provider-switched public seam.
    """
    global _gemini_client
    if _gemini_client is None:
        _gemini_client = genai.Client(api_key=settings.GEMINI_API_KEY)
    return _gemini_client


def _get_openai_client():
    """Always-OpenAI client, independent of settings.LLM_PROVIDER.

    BACK-LLM-PROVIDER-2: mirrors _get_gemini_client() above, but for the image
    path when settings.LLM_IMAGE_PROVIDER='openai'. A SEPARATE module-level
    singleton (_openai_client) from both _client (the text-path provider-switched
    seam) and _gemini_client (the image path's always-Gemini escape hatch) --
    LLM_PROVIDER and LLM_IMAGE_PROVIDER are independent switches, so the openai
    image client must not be conflated with the openai text client even though
    both would build an identical openai.OpenAI(api_key=...) instance.
    """
    global _openai_client
    if _openai_client is None:
        import openai  # noqa: PLC0415 -- lazy: zero import cost when LLM_IMAGE_PROVIDER=gemini
        _openai_client = openai.OpenAI(api_key=settings.OPENAI_API_KEY)
    return _openai_client


def _retry_gemini_call(func, *args, timeout=15.0, **kwargs):
    """
    Execute a Gemini API call with one retry on transient failure.

    Permanent errors (4xx auth/permission/invalid) fast-fail immediately —
    retry cannot help and would waste 30-40 s of SDK timeout per attempt.
    Transient errors (5xx, ResourceExhausted, unknown) get one retry after
    _GEMINI_RETRY_DELAY seconds.

    timeout: hard wall-clock deadline in seconds for each attempt. Default 15s.
    On deadline expiry, raises TimeoutError (treated as transient — retried
    once, then re-raised on second failure). Callers that need longer
    deadlines (e.g. persona report generation) should pass timeout=N
    explicitly.

    Implementation: each attempt runs `func` in a daemon thread that pushes
    its result (or error) onto a Queue. The caller blocks on Queue.get with
    a timeout. Using Queue.get instead of Thread.is_alive avoids dependence
    on threading.Thread instance attributes — robust against test mocks that
    substitute Thread with a partial-API stand-in. Daemon threads also die
    with the process so a hung SDK call cannot block pytest or interpreter
    exit; the orphan worker exits naturally when the SDK call returns.

    Returns the result on success, raises on final failure.
    """
    for attempt in range(_GEMINI_MAX_RETRIES + 1):
        result_queue = queue.Queue(maxsize=1)

        def _runner():
            try:
                result_queue.put(('ok', func(*args, **kwargs)))
            except BaseException as e:
                result_queue.put(('err', e))

        _Thread(target=_runner, daemon=True).start()

        try:
            kind, value = result_queue.get(timeout=timeout)
        except queue.Empty:
            logger.warning(
                'Gemini API call timeout (attempt %d/%d) after %.1fs',
                attempt + 1, _GEMINI_MAX_RETRIES + 1, timeout,
            )
            if attempt == _GEMINI_MAX_RETRIES:
                raise TimeoutError(
                    f'Gemini call exceeded {timeout}s after '
                    f'{_GEMINI_MAX_RETRIES + 1} attempts'
                )
            time.sleep(_GEMINI_RETRY_DELAY)
            continue

        if kind == 'err':
            e = value
            if _is_fatal_gemini(e):
                logger.warning(
                    'Gemini API permanent error (no retry): %s: %s',
                    type(e).__name__, str(e),
                )
                raise e
            logger.warning(
                'Gemini API call failed (attempt %d/%d): %s: %s',
                attempt + 1, _GEMINI_MAX_RETRIES + 1,
                type(e).__name__, str(e),
            )
            if attempt == _GEMINI_MAX_RETRIES:
                raise e
            time.sleep(_GEMINI_RETRY_DELAY)
            continue

        return value


class _NormalizedResponse:
    """BACK-LLM-PROVIDER-1: wraps an OpenAI ChatCompletion to match the small
    surface of a google-genai GenerateContentResponse that callers actually
    read (grepped against every usage_metadata/.text access in parse_query.py
    and generation.py):

      .text                                -> choices[0].message.content
      .usage_metadata.prompt_token_count       -> usage.prompt_tokens
      .usage_metadata.candidates_token_count   -> usage.completion_tokens
      .usage_metadata.cached_content_token_count
          -> usage.prompt_tokens_details.cached_tokens (None if absent)
      .usage_metadata.thoughts_token_count -> None (OpenAI has no equivalent
          field surfaced here; callers already do getattr(..., None)-safe reads)
      .model_version                       -> the model string used

    Never used on the Gemini path -- genai responses pass through _dispatch_generate
    untouched.
    """

    class _UsageMetadata:
        def __init__(self, prompt_token_count, candidates_token_count, cached_content_token_count):
            self.prompt_token_count = prompt_token_count
            self.candidates_token_count = candidates_token_count
            self.cached_content_token_count = cached_content_token_count
            self.thoughts_token_count = None

    def __init__(self, chat_completion, model):
        choice = (chat_completion.choices or [None])[0]
        message = getattr(choice, 'message', None) if choice else None
        self.text = getattr(message, 'content', None) if message else None
        usage = getattr(chat_completion, 'usage', None)
        prompt_tokens = getattr(usage, 'prompt_tokens', None) if usage else None
        completion_tokens = getattr(usage, 'completion_tokens', None) if usage else None
        details = getattr(usage, 'prompt_tokens_details', None) if usage else None
        cached_tokens = getattr(details, 'cached_tokens', None) if details else None
        self.usage_metadata = self._UsageMetadata(prompt_tokens, completion_tokens, cached_tokens)
        self.model_version = model


def _translate_contents_to_messages(contents, config):
    """BACK-LLM-PROVIDER-1: translate genai `contents` (+ config.system_instruction)
    into an OpenAI chat `messages` list.

    Accepts:
      - a plain string (single user turn -- the shape generation.py/rerank.py pass)
      - a list of google.genai types.Content (the shape parse_query.py builds),
        each with .role ('user'|'model') and .parts[*].text

    genai role 'model' maps to OpenAI 'assistant'; 'user' passes through.
    config.system_instruction (a plain str in this codebase) is prepended as a
    'system' message when present. When json mode is requested
    (config.response_mime_type == 'application/json'), a one-line instruction
    is appended to the system message ('Return ONLY a single JSON object.')
    since config.response_schema is NOT translated on the openai path (schema
    stays json_object-only, non-strict -- see _dispatch_generate docstring).
    """
    messages = []

    system_instruction = getattr(config, 'system_instruction', None) if config else None
    json_mode = bool(config and getattr(config, 'response_mime_type', None) == 'application/json')
    system_text = system_instruction if isinstance(system_instruction, str) else None
    if json_mode:
        json_note = 'Return ONLY a single JSON object.'
        system_text = f'{system_text}\n\n{json_note}' if system_text else json_note
    if system_text:
        messages.append({'role': 'system', 'content': system_text})

    if isinstance(contents, str):
        messages.append({'role': 'user', 'content': contents})
        return messages

    for turn in contents or []:
        role = getattr(turn, 'role', 'user') or 'user'
        role = 'assistant' if role == 'model' else 'user'
        parts = getattr(turn, 'parts', None) or []
        text = ''.join(getattr(p, 'text', '') or '' for p in parts)
        messages.append({'role': role, 'content': text})

    return messages


def _dispatch_generate(client, *, model, contents, config=None, timeout, provider=None):
    """BACK-LLM-PROVIDER-1: provider-agnostic single-call dispatch.

    Gemini path: unchanged -- calls _retry_gemini_call(client.models.generate_content, ...)
    exactly as before this change existed.

    OpenAI path: translates (contents, config) into OpenAI chat kwargs, then
    calls the SAME _retry_gemini_call thread-timeout wrapper around
    client.chat.completions.create, with the SAME timeout value (fairness for
    A/B testing -- no provider gets a longer deadline). Returns a
    _NormalizedResponse so callers' response.text / response.usage_metadata.*
    reads keep working unmodified.

    Routed through the services-package facade (_svc._retry_gemini_call), NOT
    the local name -- see generate_content_with_fallback's docstring for why
    (FULL-REFACTOR-1 mock.patch lesson).
    """
    from apps.recommendation import services as _svc

    if (provider or settings.LLM_PROVIDER) != 'openai':
        return _svc._retry_gemini_call(
            client.models.generate_content,
            model=model,
            contents=contents,
            config=config,
            timeout=timeout,
        )

    messages = _translate_contents_to_messages(contents, config)
    kwargs = {
        'model': model,
        'messages': messages,
    }
    # temperature intentionally NOT forwarded: gpt-5.x reasoning-class models
    # reject any non-default value with 400 unsupported_value (empirically hit
    # 2026-08-04 — "Only the default (1) value is supported").
    json_mode = bool(config and getattr(config, 'response_mime_type', None) == 'application/json')
    response_schema = getattr(config, 'response_schema', None) if config else None
    if json_mode and settings.OPENAI_STRICT_SCHEMA and response_schema is None:
        # LLM-AB-KNOB-1: opt-in strict structured output for the LEGACY parse
        # path only (response_schema is None there -- the stage1 path always
        # sets response_schema=_STAGE1_RESPONSE_SCHEMA, a Gemini-shaped schema
        # that must NOT be translated/forwarded here, so it falls through to
        # the plain json_object branch below unchanged).
        from ._prompts import _OPENAI_STRICT_PARSE_SCHEMA  # noqa: PLC0415 -- lazy, keeps module self-contained
        kwargs['response_format'] = {
            'type': 'json_schema',
            'json_schema': {
                'name': 'parse_result',
                'strict': True,
                'schema': _OPENAI_STRICT_PARSE_SCHEMA,
            },
        }
    elif json_mode:
        kwargs['response_format'] = {'type': 'json_object'}
    # config.thinking_config is intentionally IGNORED on the openai path -- see
    # this function's docstring + module design notes. config.response_schema
    # is ignored too EXCEPT as the strict-mode gate above (never translated/
    # forwarded verbatim -- Gemini schema shape != OpenAI json_schema shape).

    # Validated at settings load (allowlist); empty string means "do not send".
    reasoning_effort = getattr(settings, 'OPENAI_REASONING_EFFORT', '')
    if reasoning_effort:
        kwargs['reasoning_effort'] = reasoning_effort

    response = _svc._retry_gemini_call(
        client.chat.completions.create,
        timeout=timeout,
        **kwargs,
    )

    return _NormalizedResponse(response, model)


def generate_content_with_fallback(client, *, timeout=15.0, provider=None, **kw):
    """
    Call client.models.generate_content (gemini) or client.chat.completions.create
    (openai, BACK-LLM-PROVIDER-1) with automatic model fallback -- gemini only.

    Uses settings.GEMINI_TEXT_MODEL as the primary model and
    settings.GEMINI_TEXT_MODEL_FALLBACK as the fallback.  Fallback fires when
    the primary model is unavailable/invalid (404 NotFound / 400 InvalidArgument
    — model not available in the API key tier or region). Recognises both the
    google-genai ClientError family and legacy gax errors via _is_model_unavailable.

    BACK-LLM-PROVIDER-1: on the openai path there is a single model
    (settings.OPENAI_TEXT_MODEL) and NO fallback swap -- a model-unavailable
    error is simply re-raised. Gemini's dual-model fallback behaviour is
    unaffected and stays byte-for-byte identical to before this change.

    All keyword args (contents, config, etc.) are forwarded unchanged so the
    caller's timing block, config, and telemetry keep working as before.

    Returns the raw response object (gemini) or a _NormalizedResponse (openai) --
    see _dispatch_generate / _NormalizedResponse docstrings.

    NOTE: the retry is invoked through the services-package facade
    (_svc._retry_gemini_call), NOT the local name, on purpose. Existing tests
    patch 'apps.recommendation.services._retry_gemini_call' (the facade
    re-export). The facade binding and this module's local binding are DIFFERENT
    objects (FULL-REFACTOR-1 lesson: re-export preserves import, not mock.patch
    of a function name). Routing through the facade keeps every existing
    _retry_gemini_call mock seam live, exactly as the pre-wrapper direct call
    sites did.
    """
    resolved = provider or settings.LLM_PROVIDER
    if resolved == 'openai':
        model = settings.OPENAI_TEXT_MODEL
        return _dispatch_generate(client, model=model, timeout=timeout, provider=resolved, **kw)

    primary = settings.GEMINI_TEXT_MODEL
    fb = settings.GEMINI_TEXT_MODEL_FALLBACK
    try:
        return _dispatch_generate(client, model=primary, timeout=timeout, provider=resolved, **kw)
    except Exception as e:
        if _is_model_unavailable(e) and fb and fb != primary:
            logger.warning(
                'text model %s rejected (%s); fallback -> %s',
                primary, type(e).__name__, fb,
            )
            return _dispatch_generate(client, model=fb, timeout=timeout, provider=resolved, **kw)
        raise
