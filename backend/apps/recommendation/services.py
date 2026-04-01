"""
services.py — Gemini LLM integration for query parsing and persona report generation.
"""
import json
import logging
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


def parse_query(query_text):
    """
    Parse a natural-language query into structured filters using Gemini.
    Returns {'reply': str, 'filters': dict}.
    """
    try:
        client = _get_client()
        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=query_text,
            config=types.GenerateContentConfig(
                system_instruction=_PARSE_QUERY_PROMPT,
                response_mime_type='application/json',
                temperature=0.2,
            ),
        )
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
    except Exception as e:
        logger.error('parse_query error: %s', e)
        return {'reply': 'I had trouble understanding that. Try again?', 'filters': {}, 'filter_priority': []}


def generate_persona_report(liked_building_ids):
    """
    Generate an architect persona report from a list of liked building_ids.
    Returns a dict with persona fields, or None on failure.
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
        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=summary,
            config=types.GenerateContentConfig(
                system_instruction=_PERSONA_PROMPT,
                response_mime_type='application/json',
                temperature=0.7,
            ),
        )
        return json.loads(response.text)
    except Exception as e:
        logger.error('generate_persona_report error: %s', e)
        return None
