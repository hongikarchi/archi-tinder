"""
services.py -- Gemini LLM integration for query parsing and persona report generation.
"""
import base64
import json
import logging
import time
from django.conf import settings
from django.db import connection
from google import genai
from google.genai import types

from .engine import _dictfetchall

logger = logging.getLogger('apps.recommendation')

_client = None

def _get_client():
    global _client
    if _client is None:
        _client = genai.Client(api_key=settings.GEMINI_API_KEY)
    return _client


PROGRAM_VALUES = [
    'Housing', 'Office', 'Museum', 'Education', 'Religion', 'Sports',
    'Transport', 'Hospitality', 'Healthcare', 'Public', 'Mixed Use',
    'Landscape', 'Infrastructure', 'Other',
]

_PARSE_QUERY_PROMPT = """You are an architectural search assistant. Extract structured search filters from the user's natural language query.

Available program types (use only these exact values):
Housing, Office, Museum, Education, Religion, Sports, Transport, Hospitality, Healthcare, Public, Mixed Use, Landscape, Infrastructure, Other

Return ONLY valid JSON with this exact structure (use null for fields not mentioned):
{
  "reply": "Brief conversational acknowledgement of what you understood",
  "filters": {
    "location_country": null,
    "program": null,
    "material": null,
    "style": null,
    "year_min": null,
    "year_max": null,
    "min_area": null,
    "max_area": null
  },
  "filter_priority": ["program", "location_country", "style"]
}

filter_priority is an array of the filter keys you actually extracted (non-null), ordered from most essential to the user intent to least essential. Only include keys that have non-null values in filters."""

_PERSONA_PROMPT = """You are an architectural taste analyst. Based on the buildings a user has liked, generate a short persona archetype that describes their architectural aesthetic.

Return ONLY valid JSON with this exact structure:
{
  "persona_type": "A short poetic name like 'The Minimalist' or 'The Pragmatist'",
  "one_liner": "A single evocative sentence about their taste",
  "description": "2-3 sentences elaborating on their architectural sensibility",
  "dominant_programs": ["list of program types from: Housing, Office, Museum, Education, Religion, Sports, Transport, Hospitality, Healthcare, Public, Mixed Use, Landscape, Infrastructure, Other"],
  "dominant_styles": ["2-3 architectural style words"],
  "dominant_materials": ["2-3 material words"]
}"""

_GEMINI_MAX_RETRIES = 1
_GEMINI_RETRY_DELAY = 1.0  # seconds


def _retry_gemini_call(func, *args, **kwargs):
    """
    Execute a Gemini API call with one retry on failure.
    Logs the specific error on each attempt.
    Returns the result on success, raises on final failure.
    """
    last_error = None
    for attempt in range(_GEMINI_MAX_RETRIES + 1):
        try:
            return func(*args, **kwargs)
        except Exception as e:
            last_error = e
            logger.warning(
                'Gemini API call failed (attempt %d/%d): %s: %s',
                attempt + 1, _GEMINI_MAX_RETRIES + 1,
                type(e).__name__, str(e),
            )
            if attempt < _GEMINI_MAX_RETRIES:
                time.sleep(_GEMINI_RETRY_DELAY)
    raise last_error


def parse_query(query_text):
    """
    Parse a natural-language query into structured filters using Gemini.
    Returns {'reply': str, 'filters': dict, 'filter_priority': list}.
    On failure (after retry), returns a fallback with empty filters.
    """
    try:
        client = _get_client()

        def _call():
            return client.models.generate_content(
                model='gemini-2.5-flash',
                contents=query_text,
                config=types.GenerateContentConfig(
                    system_instruction=_PARSE_QUERY_PROMPT,
                    response_mime_type='application/json',
                    temperature=0.2,
                ),
            )

        response = _retry_gemini_call(_call)
        data = json.loads(response.text)

        # Sanitize: ensure program is a valid value (case-insensitive match -> canonical form)
        filters = data.get('filters', {})
        if filters.get('program'):
            program = filters['program']
            if program not in PROGRAM_VALUES:
                # Try title-casing (e.g. "housing" -> "Housing")
                titled = program.title()
                filters['program'] = titled if titled in PROGRAM_VALUES else None
        return {
            'reply':           data.get('reply', ''),
            'filters':         filters,
            'filter_priority': data.get('filter_priority', []),
        }
    except json.JSONDecodeError as e:
        logger.error('parse_query JSON decode error: %s', e)
        return {'reply': 'I had trouble understanding that. Try again?', 'filters': {}, 'filter_priority': []}
    except Exception as e:
        logger.error('parse_query failed after retries: %s: %s', type(e).__name__, e)
        return {'reply': 'I had trouble understanding that. Try again?', 'filters': {}, 'filter_priority': []}


def generate_persona_report(liked_building_ids):
    """
    Generate an architect persona report from a list of liked building_ids.
    Returns a dict with persona fields on success.
    Raises an exception with a descriptive message on failure (caller handles response).
    Returns None only if no building data is found.
    """
    if not liked_building_ids:
        return None

    # Fetch attributes of liked buildings
    placeholders = ','.join(['%s'] * len(liked_building_ids))
    with connection.cursor() as cur:
        cur.execute(
            f'SELECT program, style, atmosphere, material, architect, location_country '
            f'FROM architecture_vectors WHERE building_id IN ({placeholders})',
            liked_building_ids,
        )
        rows = _dictfetchall(cur)

    if not rows:
        return None

    # Aggregate for the prompt
    programs    = [r['program']          for r in rows if r.get('program')]
    styles      = [r['style']            for r in rows if r.get('style')]
    atmospheres = [r['atmosphere']       for r in rows if r.get('atmosphere')]
    materials   = [r['material']         for r in rows if r.get('material')]
    architects  = [r['architect']        for r in rows if r.get('architect')]
    countries   = [r['location_country'] for r in rows if r.get('location_country')]

    summary = (
        f"The user liked {len(rows)} buildings.\n"
        f"Programs: {', '.join(programs)}\n"
        f"Styles: {', '.join(styles)}\n"
        f"Atmospheres: {', '.join(atmospheres)}\n"
        f"Materials: {', '.join(materials)}\n"
        f"Architects: {', '.join(architects[:10])}\n"
        f"Countries: {', '.join(countries)}"
    )

    try:
        client = _get_client()

        def _call():
            return client.models.generate_content(
                model='gemini-2.5-flash',
                contents=summary,
                config=types.GenerateContentConfig(
                    system_instruction=_PERSONA_PROMPT,
                    response_mime_type='application/json',
                    temperature=0.7,
                ),
            )

        response = _retry_gemini_call(_call)
        return json.loads(response.text)
    except json.JSONDecodeError as e:
        logger.error('generate_persona_report JSON decode error: %s', e)
        raise ValueError('Gemini returned an invalid response format. Please try again.')
    except Exception as e:
        logger.error('generate_persona_report failed after retries: %s: %s', type(e).__name__, e)
        raise RuntimeError(f'Persona report generation failed: {type(e).__name__}. Please try again later.')


def generate_persona_image(report):
    """
    Generate an AI architecture image from a persona report using Imagen 3.
    Returns {'image_data': base64_str, 'mime_type': str, 'prompt': str} or None on failure.
    """
    if not report:
        return None

    try:
        style = (report.get('dominant_styles') or ['Contemporary'])[0]
        program = (report.get('dominant_programs') or ['Housing'])[0]
        materials = ', '.join(report.get('dominant_materials') or ['concrete'])
        one_liner = report.get('one_liner', 'serene and monumental')

        prompt = (
            f"A photorealistic architectural photograph of a building. "
            f"{style} style, {program} typology, atmosphere: {one_liner}. "
            f"Materials: {materials}. "
            f"Professional architectural photography, golden hour lighting, high quality, 8k resolution."
        )

        client = _get_client()

        def _call():
            return client.models.generate_images(
                model='imagen-3.0-generate-002',
                prompt=prompt,
                config=types.GenerateImagesConfig(
                    number_of_images=1,
                    aspect_ratio='16:9',
                ),
            )

        response = _retry_gemini_call(_call)

        image_bytes = response.generated_images[0].image.image_bytes
        base64_str = base64.b64encode(image_bytes).decode('utf-8')

        return {
            'image_data': base64_str,
            'mime_type': 'image/png',
            'prompt': prompt,
        }
    except Exception as e:
        logger.error('generate_persona_image error: %s: %s', type(e).__name__, e)
        return None
