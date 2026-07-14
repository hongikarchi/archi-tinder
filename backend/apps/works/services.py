"""apps.works.services — background processing for uploaded Works.

FULL-WORKS-1: _process_work runs in a daemon thread after Work creation.
It calls Gemini to validate the architectural content, then updates
is_publishable + gate_reason on the Work row.

If the Work model does not have gemini result fields, the summary is stored
in gate_reason (cleared to '' when publishable=True) and is_publishable is
set to True.
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

_GEMINI_RESPONSE_SCHEMA = {
    'type': 'object',
    'properties': {
        'is_architectural': {'type': 'boolean'},
        'style': {'type': 'string'},
        'color_tone': {'type': 'string'},
        'atmosphere': {
            'type': 'string',
            'enum': _ATMOSPHERE_ENUM,
        },
        'material_visual': {'type': 'string'},
        'visual_description': {'type': 'string'},
    },
    'required': [
        'is_architectural',
        'style',
        'color_tone',
        'atmosphere',
        'material_visual',
        'visual_description',
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


def _do_process_work(work_id: int) -> None:
    """Core processing logic — separated for easier testing."""
    from apps.works.models import Work

    try:
        work = Work.objects.get(pk=work_id)
    except Work.DoesNotExist:
        logger.warning('_process_work: Work id=%s not found', work_id)
        return

    if not work.r2_keys:
        work.is_publishable = False
        work.gate_reason = 'No images uploaded.'
        work.save(update_fields=['is_publishable', 'gate_reason', 'updated_at'])
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
        work.is_publishable = False
        work.gate_reason = 'Validation skipped: WORKS_PUBLIC_BASE_URL not configured.'
        work.save(update_fields=['is_publishable', 'gate_reason', 'updated_at'])
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
        work.is_publishable = False
        work.gate_reason = 'Validation unavailable: Gemini not configured or transient error.'
        work.save(update_fields=['is_publishable', 'gate_reason', 'updated_at'])
        return

    if not gemini_result.get('is_architectural', False):
        work.is_publishable = False
        work.gate_reason = 'Not recognized as architectural work'
        work.save(update_fields=['is_publishable', 'gate_reason', 'updated_at'])
        return

    # --- HuggingFace embedding (best-effort; failure does not block publish) ---
    visual_description = gemini_result.get('visual_description', '')
    if visual_description:
        try:
            _call_hf_embed(visual_description)
        except Exception as exc:
            logger.warning('HF embedding failed for work_id=%s: %s', work_id, exc)

    # Publish the work.
    work.is_publishable = True
    work.gate_reason = ''
    work.save(update_fields=['is_publishable', 'gate_reason', 'updated_at'])
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

        client = genai.Client(api_key=api_key)
        model = settings.GEMINI_IMAGE_MODEL or settings.GEMINI_TEXT_MODEL

        prompt = (
            'You are an architectural expert. Analyse this image and respond '
            'in strict JSON following the provided schema. '
            'Set is_architectural=false if the image does not depict a building '
            'or architectural structure.'
        )

        response = client.models.generate_content(
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
        )
        import json
        text = response.text
        return json.loads(text)
    except Exception as exc:
        logger.warning('Gemini image call failed: %s', exc)
        return None


def _call_hf_embed(text: str):
    """Request a 384-dim embedding from HuggingFace Inference API.

    Returns the embedding list on success, or raises on failure.
    The caller catches exceptions so failure does not block publishing.
    """
    import requests

    hf_token = settings.HF_TOKEN
    if not hf_token:
        return None

    url = (
        'https://api-inference.huggingface.co/pipeline/feature-extraction/'
        'sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2'
    )
    headers = {'Authorization': f'Bearer {hf_token}'}
    resp = requests.post(url, headers=headers, json={'inputs': [text]}, timeout=10)
    resp.raise_for_status()
    data = resp.json()
    # HF returns [[...384 floats...]] for a single-item inputs list.
    if isinstance(data, list) and len(data) > 0:
        return data[0]
    return data
