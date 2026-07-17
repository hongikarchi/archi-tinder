"""apps.works.services — background processing for uploaded Works.

FULL-WORKS-1: _process_work runs in a daemon thread after Work creation.
It calls Gemini to validate the architectural content, then updates
is_publishable + gate_reason on the Work row.

gate_reason holds a short human-readable explanation of why a work failed
the gate (or '' when publishable); it does not store the Gemini visual
summary. Any failure (misconfiguration, Gemini unavailable/timeout, or
is_architectural=False) fails closed — is_publishable stays False.
"""
import logging

from django.conf import settings

logger = logging.getLogger('apps.works')

_ATMOSPHERE_ENUM = [
    'Minimalist',
    'Industrial',
    'Organic',
    'Brutalist',
    'Futuristic',
    'Historical',
    'Vernacular',
    'Deconstructivist',
    'Modernist',
    'Postmodernist',
    'High-tech',
    'Ecological',
]

# Trimmed to the fields the gate logic actually consumes: is_architectural
# gates publishing, atmosphere is logged. The Work model has no columns to
# persist style / color_tone / material_visual / visual_description, so
# those were dropped from the schema (previously requested only to feed the
# now-deleted HF embedding call).
_GEMINI_RESPONSE_SCHEMA = {
    'type': 'object',
    'properties': {
        'is_architectural': {'type': 'boolean'},
        'atmosphere': {
            'type': 'string',
            'enum': _ATMOSPHERE_ENUM,
        },
    },
    'required': [
        'is_architectural',
        'atmosphere',
    ],
}


def _process_work(work_id: int) -> None:
    """Validate a Work via Gemini and update is_publishable.

    Designed to run in a daemon thread (fire-and-forget).  Closes DB
    connections on both entry and exit so the spawning Django worker's
    connection is not inadvertently reused across threads (mirrors the
    swipe telemetry thread pattern).
    """
    from django.db import connections as _connections
    _connections.close_all()

    try:
        _do_process_work(work_id)
    except Exception as exc:
        logger.warning('_process_work failed for work_id=%s: %s', work_id, exc, exc_info=True)
    finally:
        _connections.close_all()


def _finish(work, publishable: bool, reason: str) -> None:
    """Set is_publishable + gate_reason and save. Shared tail of every gate branch."""
    work.is_publishable = publishable
    work.gate_reason = reason
    work.save(update_fields=['is_publishable', 'gate_reason', 'updated_at'])


def _do_process_work(work_id: int) -> None:
    """Core processing logic — separated for easier testing."""
    from apps.works.models import Work

    try:
        work = Work.objects.get(pk=work_id)
    except Work.DoesNotExist:
        logger.warning('_process_work: Work id=%s not found', work_id)
        return

    if not work.r2_keys:
        _finish(work, False, 'No images uploaded.')
        return

    public_base = settings.WORKS_PUBLIC_BASE_URL.rstrip('/')
    if not public_base:
        # Misconfiguration — building an invalid relative URL masquerades as a
        # Gemini outage and bypasses moderation.  Fail-closed with an explicit
        # signal so admins can distinguish from genuine Gemini unavailability.
        logger.warning(
            '_process_work: WORKS_PUBLIC_BASE_URL is not configured for work_id=%s; '
            'failing closed (is_publishable stays False).', work_id,
        )
        _finish(work, False, 'Validation skipped: WORKS_PUBLIC_BASE_URL not configured.')
        return

    cover_url = f'{public_base}/{work.r2_keys[0]}'

    # --- Gemini validation ---
    gemini_result = _call_gemini_image(cover_url)
    if gemini_result is None:
        # Distinguish: key absent (configuration gap) vs transient failure.
        # Both cases fail-closed to prevent arbitrary imagery from being published.
        logger.warning(
            'Gemini validation unavailable for work_id=%s (key unset or transient error); '
            'failing closed (is_publishable stays False).', work_id,
        )
        _finish(work, False, 'Validation unavailable: Gemini not configured or transient error.')
        return

    if not gemini_result.get('is_architectural', False):
        _finish(work, False, 'Not recognized as architectural work')
        return

    # Publish the work.
    _finish(work, True, '')
    logger.info('work_id=%s published (atmosphere=%s)', work_id, gemini_result.get('atmosphere'))


def _call_gemini_image(image_url: str):
    """Call Gemini to classify the architectural content of an image.

    Returns a parsed dict on success, or None when Gemini is not configured
    or the call fails after retries.
    """
    api_key = settings.GEMINI_API_KEY
    if not api_key:
        return None

    try:
        from google import genai
        from google.genai import types as genai_types

        from apps.recommendation.services._gemini import _retry_gemini_call

        client = genai.Client(api_key=api_key)
        model = settings.GEMINI_IMAGE_MODEL or settings.GEMINI_TEXT_MODEL

        prompt = (
            'You are an architectural expert. Analyse this image and respond '
            'in strict JSON following the provided schema. '
            'Set is_architectural=false if the image does not depict a building '
            'or architectural structure.'
        )

        # Routed through _retry_gemini_call (15s deadline) rather than a raw
        # client.models.generate_content call — the raw SDK can hang 30-40s
        # with no timeout, and every other Gemini call site in the repo goes
        # through this guard (see apps.recommendation.services._gemini).
        response = _retry_gemini_call(
            client.models.generate_content,
            model=model,
            contents=[
                genai_types.Part.from_uri(file_uri=image_url, mime_type='image/webp'),
                prompt,
            ],
            config=genai_types.GenerateContentConfig(
                response_mime_type='application/json',
                response_schema=_GEMINI_RESPONSE_SCHEMA,
                temperature=0.0,
            ),
            timeout=15.0,
        )
        import json
        text = response.text
        return json.loads(text)
    except Exception as exc:
        logger.warning('Gemini image call failed: %s', exc)
        return None
