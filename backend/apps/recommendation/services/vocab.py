"""
vocab.py -- Live DB vocabulary provider for the 5 grounded filter axes.

BACK-PARSER-VOCAB-1: grounds the Gemini query parser prompt + validation in
the ACTUAL values present in canonical_v2_buildings (is_publishable=true),
rather than free-form LLM guesses. Covers style, atmosphere, color_tone,
typology_primary, architectural_elements. `program` is intentionally excluded
-- PROGRAM_VALUES in _prompts.py is already the correct hand-curated bucket
list and is not a live-DB vocabulary axis.

Self-contained: no sibling-module imports beyond Django cache/db, so it can
be imported early without circular-import risk. Cross-module callers reach
this via the services facade (`_svc.get_axis_vocab()`), per the FULL-REFACTOR-1
late-binding contract documented in _gemini.py's docstring -- this keeps
mock.patch('apps.recommendation.services.get_axis_vocab') working.
"""
import logging

from django.core.cache import cache as django_cache
from django.db import connections

logger = logging.getLogger('apps.recommendation')

_AXIS_VOCAB_CACHE_KEY = 'axis_vocab:v1'
_AXIS_VOCAB_CACHE_TTL_SECONDS = 60 * 60 * 24  # 24h

# Scalar (single-value TEXT column) axes -- SELECT DISTINCT <col>.
_SCALAR_AXES = ('style', 'atmosphere', 'color_tone', 'typology_primary')

# Array (TEXT[] column) axis -- SELECT DISTINCT unnest(<col>).
_ARRAY_AXES = ('architectural_elements',)

# ---------------------------------------------------------------------------
# Snapshot fallback -- fetched 2026-08-04 from canonical_v2_buildings,
# is_publishable=true, 36,864 rows. Used whenever the live buildings-DB query
# fails (connection error, missing column, etc.) or returns an empty axis.
# Keep in sync with the live corpus; db_qc.py WARNs on drift (non-fatal).
# ---------------------------------------------------------------------------
_VOCAB_SNAPSHOT = {
    'style': [
        'Contemporary', 'Minimalist', 'Vernacular', 'Industrial', 'Organic',
        'Modernist', 'High-Tech', 'Brutalist', 'Postmodern', 'Neo-Classical',
        'Parametric', 'Deconstructivist',
    ],
    'atmosphere': [
        'Serene', 'Urban', 'Contemplative', 'Intimate', 'Dynamic', 'Warm',
        'Playful', 'Rustic', 'Industrial', 'Monumental', 'Raw', 'Futuristic',
    ],
    'color_tone': [
        'Neutral', 'Earth', 'Light', 'Warm', 'Vibrant', 'Dark', 'Cool', 'Monochrome',
    ],
    'typology_primary': [
        'House', 'Office', 'Apartment', 'Housing', 'Museum', 'Retail', 'Park',
        'Restaurant', 'Civic Building', 'School', 'Sports Centre', 'Hotel',
        'Industrial', 'Pavilion', 'Religious Building', 'Theatre', 'Gallery',
        'Library', 'University', 'Hospital', 'Kindergarten', 'Bridge',
        'Mixed Use', 'Winery', 'Shopping Centre', 'Care Home', 'Train Station',
        'Car Park', 'Warehouse', 'Memorial', 'Stadium', 'Airport',
        'Student Housing', 'Concert Hall', 'Bank',
    ],
    'architectural_elements': [
        'Facade', 'Stair', 'Roof', 'Entrance', 'Garden', 'Courtyard',
        'Corridor', 'Fireplace', 'Atrium', 'Balcony', 'Terrace', 'Canopy',
        'Column',
    ],
}


def _fetch_scalar_axis(cursor, axis):
    """SELECT DISTINCT <axis> for a single-value TEXT column. Returns list[str]."""
    cursor.execute(
        f'SELECT DISTINCT {axis} FROM canonical_v2_buildings '
        f'WHERE is_publishable = true AND {axis} IS NOT NULL'
    )
    return [row[0] for row in cursor.fetchall()]


def _fetch_array_axis(cursor, axis):
    """SELECT DISTINCT unnest(<axis>) for a TEXT[] column. Returns list[str]."""
    cursor.execute(
        f'SELECT DISTINCT e FROM canonical_v2_buildings, unnest({axis}) e '
        f'WHERE is_publishable = true'
    )
    return [row[0] for row in cursor.fetchall()]


def get_axis_vocab():
    """Return dict[axis_name -> list[str]] for the 5 grounded axes.

    Lookup order:
      1. Django cache ('axis_vocab:v1') -- fast path, 24h TTL.
      2. Live raw SQL on connections['buildings'] (read-only, is_publishable=true
         gated) -- on success, cache.set(..., 60*60*24) and return.
      3. On ANY exception, or when a given axis comes back empty, fall back to
         _VOCAB_SNAPSHOT PER-AXIS (a failure on one axis does not blank the others).

    Never raises. Import-light: no DB access happens at import time -- only
    inside this function, at call time.
    """
    try:
        cached = django_cache.get(_AXIS_VOCAB_CACHE_KEY)
        if cached:
            return cached
    except Exception as exc:
        # Cache backend itself unreachable -- fall through to the live/snapshot
        # path below rather than raising (Never raises invariant).
        logger.warning('get_axis_vocab: cache read failed (%s); proceeding to DB fetch', exc)

    result = {}
    try:
        with connections['buildings'].cursor() as cursor:
            for axis in _SCALAR_AXES:
                try:
                    values = _fetch_scalar_axis(cursor, axis)
                except Exception as exc:
                    logger.warning(
                        'get_axis_vocab: scalar axis %s query failed (%s); '
                        'using snapshot fallback for this axis',
                        axis, exc,
                    )
                    values = []
                result[axis] = values if values else list(_VOCAB_SNAPSHOT[axis])

            for axis in _ARRAY_AXES:
                try:
                    values = _fetch_array_axis(cursor, axis)
                except Exception as exc:
                    logger.warning(
                        'get_axis_vocab: array axis %s query failed (%s); '
                        'using snapshot fallback for this axis',
                        axis, exc,
                    )
                    values = []
                result[axis] = values if values else list(_VOCAB_SNAPSHOT[axis])
    except Exception as exc:
        # Connection-level failure (e.g. buildings DB unreachable) -- full snapshot fallback.
        logger.warning(
            'get_axis_vocab: buildings DB connection failed (%s); using full snapshot fallback',
            exc,
        )
        return {axis: list(values) for axis, values in _VOCAB_SNAPSHOT.items()}

    try:
        django_cache.set(_AXIS_VOCAB_CACHE_KEY, result, _AXIS_VOCAB_CACHE_TTL_SECONDS)
    except Exception as exc:
        logger.warning('get_axis_vocab: cache write failed (%s); returning uncached result', exc)
    return result
