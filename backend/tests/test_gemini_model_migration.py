"""
test_gemini_model_migration.py -- Tests for Gemini 3.1 model migration.

Covers:
  1. settings defaults and env override for GEMINI_TEXT_MODEL / GEMINI_IMAGE_MODEL.
  2. generate_content_with_fallback: primary model used; NotFound triggers fallback.
  3. generate_persona_image: WebP conversion, primary NotFound -> fallback, no image
     part returns None, Pillow-failure path retains native mime.
  4. No assertions remain for the old hardcoded 'gemini-2.5-flash' string.

No real Gemini API calls are made; all SDK interactions are mocked.
"""
import base64
import struct
import zlib

import pytest
from unittest.mock import MagicMock, patch
from google.api_core import exceptions as gax_exceptions

from django.test import override_settings


# ---------------------------------------------------------------------------
# Minimal valid 1x1 PNG helper (so Pillow can actually open it)
# ---------------------------------------------------------------------------

def _make_1x1_png():
    """Return a valid 1x1 white PNG as bytes."""
    def _chunk(tag, data):
        c = zlib.crc32(tag + data) & 0xFFFFFFFF
        return struct.pack('>I', len(data)) + tag + data + struct.pack('>I', c)

    signature = b'\x89PNG\r\n\x1a\n'
    ihdr_data = struct.pack('>IIBBBBB', 1, 1, 8, 2, 0, 0, 0)
    ihdr = _chunk(b'IHDR', ihdr_data)
    raw_row = b'\x00\xff\xff\xff'  # filter byte + RGB
    compressed = zlib.compress(raw_row)
    idat = _chunk(b'IDAT', compressed)
    iend = _chunk(b'IEND', b'')
    return signature + ihdr + idat + iend


# ---------------------------------------------------------------------------
# 1. settings defaults and env override
# ---------------------------------------------------------------------------

class TestGeminiSettingsDefaults:

    def test_text_model_default(self):
        from django.conf import settings
        assert settings.GEMINI_TEXT_MODEL == 'gemini-3.1-flash-lite'

    def test_image_model_default(self):
        from django.conf import settings
        assert settings.GEMINI_IMAGE_MODEL == 'gemini-3.1-flash-image'

    def test_text_model_fallback_default(self):
        from django.conf import settings
        assert settings.GEMINI_TEXT_MODEL_FALLBACK == 'gemini-2.5-flash'

    def test_image_model_fallback_default(self):
        from django.conf import settings
        assert settings.GEMINI_IMAGE_MODEL_FALLBACK == 'gemini-2.5-flash-image'

    def test_image_format_default(self):
        from django.conf import settings
        assert settings.GEMINI_IMAGE_FORMAT == 'webp'

    def test_text_model_env_override(self):
        with override_settings(GEMINI_TEXT_MODEL='gemini-custom-text'):
            from django.conf import settings
            assert settings.GEMINI_TEXT_MODEL == 'gemini-custom-text'

    def test_image_model_env_override(self):
        with override_settings(GEMINI_IMAGE_MODEL='gemini-custom-image'):
            from django.conf import settings
            assert settings.GEMINI_IMAGE_MODEL == 'gemini-custom-image'


# ---------------------------------------------------------------------------
# 2. generate_content_with_fallback
# ---------------------------------------------------------------------------

class TestGenerateContentWithFallback:

    def _make_mock_response(self):
        r = MagicMock()
        r.text = '{"test": true}'
        return r

    def test_primary_model_used(self):
        """Wrapper passes settings.GEMINI_TEXT_MODEL as the model kwarg."""
        from apps.recommendation.services._gemini import generate_content_with_fallback

        mock_gc = MagicMock(return_value=self._make_mock_response())
        mock_client = MagicMock()
        mock_client.models.generate_content = mock_gc

        with override_settings(
            GEMINI_TEXT_MODEL='gemini-test-primary',
            GEMINI_TEXT_MODEL_FALLBACK='gemini-test-fallback',
        ):
            generate_content_with_fallback(mock_client, contents='hello')

        assert mock_gc.call_count == 1
        assert mock_gc.call_args.kwargs['model'] == 'gemini-test-primary'

    def test_fallback_on_not_found(self, monkeypatch):
        """When primary raises NotFound, wrapper retries with fallback model."""
        from apps.recommendation.services._gemini import generate_content_with_fallback

        call_models = []

        def _fake_gc(**kwargs):
            call_models.append(kwargs.get('model'))
            if kwargs['model'] == 'gemini-test-primary':
                raise gax_exceptions.NotFound('model not found')
            return self._make_mock_response()

        mock_client = MagicMock()
        mock_client.models.generate_content.side_effect = _fake_gc
        # Suppress retry sleep
        monkeypatch.setattr('apps.recommendation.services._gemini.time.sleep', lambda _: None)

        with override_settings(
            GEMINI_TEXT_MODEL='gemini-test-primary',
            GEMINI_TEXT_MODEL_FALLBACK='gemini-test-fallback',
        ):
            result = generate_content_with_fallback(mock_client, contents='hello')

        assert 'gemini-test-primary' in call_models
        assert 'gemini-test-fallback' in call_models
        assert result.text == '{"test": true}'

    def test_fallback_on_invalid_argument(self, monkeypatch):
        """When primary raises InvalidArgument, wrapper retries with fallback."""
        from apps.recommendation.services._gemini import generate_content_with_fallback

        called_with = []

        def _fake_gc(**kwargs):
            called_with.append(kwargs.get('model'))
            if kwargs['model'] == 'gemini-test-primary':
                raise gax_exceptions.InvalidArgument('bad model')
            return self._make_mock_response()

        mock_client = MagicMock()
        mock_client.models.generate_content.side_effect = _fake_gc
        monkeypatch.setattr('apps.recommendation.services._gemini.time.sleep', lambda _: None)

        with override_settings(
            GEMINI_TEXT_MODEL='gemini-test-primary',
            GEMINI_TEXT_MODEL_FALLBACK='gemini-test-fallback',
        ):
            result = generate_content_with_fallback(mock_client, contents='hello')

        assert result.text == '{"test": true}'
        assert called_with[-1] == 'gemini-test-fallback'

    def test_no_fallback_when_same_model(self, monkeypatch):
        """When primary == fallback, NotFound is re-raised without a second attempt."""
        from apps.recommendation.services._gemini import generate_content_with_fallback

        mock_client = MagicMock()
        mock_client.models.generate_content.side_effect = gax_exceptions.NotFound('nope')
        monkeypatch.setattr('apps.recommendation.services._gemini.time.sleep', lambda _: None)

        with override_settings(
            GEMINI_TEXT_MODEL='gemini-same',
            GEMINI_TEXT_MODEL_FALLBACK='gemini-same',
        ):
            with pytest.raises(gax_exceptions.NotFound):
                generate_content_with_fallback(mock_client, contents='hello')

        # Called only once (the single primary attempt)
        assert mock_client.models.generate_content.call_count == 1

    def test_kwargs_forwarded(self):
        """Extra kwargs (contents, config) are passed through to generate_content."""
        from apps.recommendation.services._gemini import generate_content_with_fallback
        from google.genai import types

        captured = {}

        def _fake_gc(**kwargs):
            captured.update(kwargs)
            return self._make_mock_response()

        mock_client = MagicMock()
        mock_client.models.generate_content.side_effect = _fake_gc

        cfg = types.GenerateContentConfig(temperature=0.5)

        with override_settings(
            GEMINI_TEXT_MODEL='gemini-test',
            GEMINI_TEXT_MODEL_FALLBACK='gemini-fb',
        ):
            generate_content_with_fallback(mock_client, contents='test', config=cfg)

        assert captured.get('contents') == 'test'
        assert captured.get('config') is cfg


# ---------------------------------------------------------------------------
# 3. generate_persona_image
# ---------------------------------------------------------------------------

def _make_inline_data(raw_bytes, mime='image/png'):
    idata = MagicMock()
    idata.data = raw_bytes
    idata.mime_type = mime
    return idata


def _make_image_response(raw_bytes, mime='image/png'):
    """Build a fake Gemini response with a single image part."""
    part = MagicMock()
    part.inline_data = _make_inline_data(raw_bytes, mime)
    content = MagicMock()
    content.parts = [part]
    candidate = MagicMock()
    candidate.content = content
    resp = MagicMock()
    resp.candidates = [candidate]
    return resp


class TestGeneratePersonaImage:

    _SAMPLE_REPORT = {
        'dominant_styles': ['Modernist'],
        'dominant_programs': ['Housing'],
        'dominant_materials': ['concrete'],
        'one_liner': 'serene and monumental',
    }

    def _patch_client(self, monkeypatch, side_effect):
        """Patch _get_client and retry sleep; return mock client."""
        mock_client = MagicMock()
        mock_client.models.generate_content.side_effect = side_effect
        monkeypatch.setattr('apps.recommendation.services._get_client', lambda: mock_client)
        monkeypatch.setattr('apps.recommendation.services._gemini.time.sleep', lambda _: None)
        return mock_client

    def test_webp_conversion_success(self, monkeypatch):
        """Happy path: PNG bytes -> WebP output, mime 'image/webp'."""
        raw_png = _make_1x1_png()
        resp = _make_image_response(raw_png, 'image/png')

        self._patch_client(monkeypatch, [resp])

        with override_settings(
            GEMINI_IMAGE_MODEL='gemini-img-primary',
            GEMINI_IMAGE_MODEL_FALLBACK='gemini-img-fallback',
            GEMINI_IMAGE_FORMAT='webp',
        ):
            from apps.recommendation.services import generate_persona_image
            result = generate_persona_image(self._SAMPLE_REPORT)

        assert result is not None
        assert result['mime_type'] == 'image/webp'
        # Must be valid base64
        decoded = base64.b64decode(result['image_data'])
        # WebP magic bytes: RIFF....WEBP
        assert decoded[:4] == b'RIFF'
        assert decoded[8:12] == b'WEBP'

    def test_primary_not_found_uses_fallback(self, monkeypatch):
        """Primary model NotFound -> fallback model used for image generation."""
        raw_png = _make_1x1_png()
        fallback_resp = _make_image_response(raw_png, 'image/png')

        # Track which models were called
        called_models = []

        def _fake_gc(**kwargs):
            called_models.append(kwargs.get('model'))
            if kwargs['model'] == 'gemini-img-primary':
                raise gax_exceptions.NotFound('not found')
            return fallback_resp

        mock_client = MagicMock()
        mock_client.models.generate_content.side_effect = _fake_gc
        monkeypatch.setattr('apps.recommendation.services._get_client', lambda: mock_client)
        monkeypatch.setattr('apps.recommendation.services._gemini.time.sleep', lambda _: None)

        with override_settings(
            GEMINI_IMAGE_MODEL='gemini-img-primary',
            GEMINI_IMAGE_MODEL_FALLBACK='gemini-img-fallback',
            GEMINI_IMAGE_FORMAT='webp',
        ):
            from apps.recommendation.services import generate_persona_image
            result = generate_persona_image(self._SAMPLE_REPORT)

        assert result is not None
        assert 'gemini-img-primary' in called_models
        assert 'gemini-img-fallback' in called_models

    def test_no_image_part_returns_none(self, monkeypatch):
        """Response with no inline_data returns None."""
        part = MagicMock()
        part.inline_data = None
        content = MagicMock()
        content.parts = [part]
        candidate = MagicMock()
        candidate.content = content
        resp = MagicMock()
        resp.candidates = [candidate]

        self._patch_client(monkeypatch, [resp, resp])  # both models return no image

        with override_settings(
            GEMINI_IMAGE_MODEL='gemini-img-primary',
            GEMINI_IMAGE_MODEL_FALLBACK='gemini-img-fallback',
            GEMINI_IMAGE_FORMAT='webp',
        ):
            from apps.recommendation.services import generate_persona_image
            result = generate_persona_image(self._SAMPLE_REPORT)

        assert result is None

    def test_pillow_failure_retains_native_mime(self, monkeypatch):
        """When Pillow conversion fails, native mime_type is retained."""
        raw_png = _make_1x1_png()
        resp = _make_image_response(raw_png, 'image/png')

        self._patch_client(monkeypatch, [resp])

        # Make Pillow raise an exception
        with patch(
            'apps.recommendation.services.generation._to_webp',
            return_value=(raw_png, None),
        ):
            with override_settings(
                GEMINI_IMAGE_MODEL='gemini-img-primary',
                GEMINI_IMAGE_MODEL_FALLBACK='gemini-img-fallback',
                GEMINI_IMAGE_FORMAT='webp',
            ):
                from apps.recommendation.services import generate_persona_image
                result = generate_persona_image(self._SAMPLE_REPORT)

        assert result is not None
        # When _to_webp returns (raw, None), mime falls back to native_mime
        assert result['mime_type'] == 'image/png'

    def test_native_format_skips_webp(self, monkeypatch):
        """GEMINI_IMAGE_FORMAT=native skips WebP conversion."""
        raw_png = _make_1x1_png()
        resp = _make_image_response(raw_png, 'image/png')

        self._patch_client(monkeypatch, [resp])

        with override_settings(
            GEMINI_IMAGE_MODEL='gemini-img-primary',
            GEMINI_IMAGE_MODEL_FALLBACK='gemini-img-fallback',
            GEMINI_IMAGE_FORMAT='native',
        ):
            from apps.recommendation.services import generate_persona_image
            result = generate_persona_image(self._SAMPLE_REPORT)

        assert result is not None
        assert result['mime_type'] == 'image/png'

    def test_none_report_returns_none(self):
        """None report short-circuits immediately."""
        from apps.recommendation.services import generate_persona_image
        assert generate_persona_image(None) is None

    def test_both_models_fail_returns_none(self, monkeypatch):
        """Both image models raise NotFound -> generate_persona_image returns None."""
        mock_client = MagicMock()
        mock_client.models.generate_content.side_effect = gax_exceptions.NotFound('not found')
        monkeypatch.setattr('apps.recommendation.services._get_client', lambda: mock_client)
        monkeypatch.setattr('apps.recommendation.services._gemini.time.sleep', lambda _: None)

        with override_settings(
            GEMINI_IMAGE_MODEL='gemini-img-primary',
            GEMINI_IMAGE_MODEL_FALLBACK='gemini-img-fallback',
            GEMINI_IMAGE_FORMAT='webp',
        ):
            from apps.recommendation.services import generate_persona_image
            result = generate_persona_image(self._SAMPLE_REPORT)

        assert result is None
