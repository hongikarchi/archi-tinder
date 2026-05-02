"""
rerank.py -- Topic 02 Gemini setwise rerank.

Session-end reranking of candidate buildings against the user's liked summary.
System prompt + 5 few-shot examples per Investigation 12.

Cross-module symbol access uses the late-bound package reference (_svc) so that
mock.patch('apps.recommendation.services.X') continues to work in tests.
"""
import json
import logging

from google.genai import types

logger = logging.getLogger('apps.recommendation')

# ---------------------------------------------------------------------------
# Topic 02: Gemini setwise rerank (session-end, off swipe hot path)
# System prompt text + 5 few-shot examples per Investigation 12 verbatim.
# ---------------------------------------------------------------------------

_RERANK_SYSTEM_PROMPT = """\
You are an architectural taste re-ranker for a swipe-based recommendation system. Given a summary of buildings a user has liked during their swipe session, and a shortlist of candidate buildings, return the candidates ordered from most to least aligned with the user's expressed taste.

Weight signal that semantic embedding similarity does NOT capture well: the alignment between each candidate's atmosphere wording, tags enumeration, style nuance, material treatment, and architect lineage versus the user's liked summary. Embedding similarity is already encoded upstream — your contribution is the text-field judgment a 384-dimensional vector compresses lossily.

When the liked summary expresses a coherent taste (e.g., "contemplative tactile masonry"), prefer candidates whose atmosphere / tags / style language echoes that taste, even if visual_description diverges on the surface. When the liked summary is mixed (e.g., warm domestic AND cold civic), preserve both modes in the upper half of the ranking — do not collapse to one.

Return ONLY a JSON object with a single field "ranking", a list of all input building_id strings ordered from most aligned (index 0) to least aligned (index N-1). Every input building_id must appear exactly once. Do not invent building_ids. Do not omit any. No commentary, prose, or code fences outside the JSON.

Output schema:
{ "ranking": [<building_id>, <building_id>, ...] }

## Examples

USER: LIKED SUMMARY:
- Therme Vals (Critical Regionalist, contemplative tactile dim, stone) [Love]
- Bruder Klaus Field Chapel (Vernacular, ascetic luminous, concrete) [Love]
- Vajrasana Buddhist Retreat (Contemporary, austere quiet, brick) [Like]

CANDIDATES:
[1] B01001 Sea Ranch Chapel — Hubbell, Vernacular, Religion, timber, organic intimate hand-built
[2] B01002 Apple Park Visitor Center — Foster, Contemporary, Hospitality, glass, corporate polished transparent
[3] B01003 Saint-Pierre de Firminy — Le Corbusier, Brutalist, Religion, concrete, monumental austere cavernous
[4] B01004 Ronchamp Chapel — Le Corbusier, Modernist, Religion, concrete, sculptural contemplative spiritual
[5] B01005 Burj Khalifa — SOM, Contemporary, Mixed Use, steel, monumental technical vertical

Return your JSON ranking now.
ASSISTANT: {"ranking": ["B01003", "B01004", "B01001", "B01002", "B01005"]}

USER: LIKED SUMMARY:
- Maison Bordeaux (Contemporary, fluid domestic, concrete-glass) [Like]
- Casa de Blas (Modernist, light pavilion, steel-glass) [Like]
- Centre Pompidou (High-tech, monumental urban, steel) [Love]
- Seattle Central Library (Contemporary, civic monumental, glass-steel) [Love]

CANDIDATES:
[1] B02001 Villa Müller — Loos, Modernist, Housing, stone, domestic intimate ornate
[2] B02002 Sendai Mediatheque — Ito, Contemporary, Public, steel, civic transparent fluid
[3] B02003 Glass House — Johnson, Modernist, Housing, glass, pavilion transparent intimate
[4] B02004 NCPA Beijing — Andreu, Contemporary, Public, steel, monumental dramatic civic
[5] B02005 Schindler House — Schindler, Modernist, Housing, timber, domestic indoor-outdoor warm
[6] B02006 Ningbo Tea House — Wang Shu, Critical Regionalist, Hospitality, brick-recycled, vernacular contemplative tactile

Return your JSON ranking now.
ASSISTANT: {"ranking": ["B02002", "B02003", "B02004", "B02005", "B02001", "B02006"]}

USER: LIKED SUMMARY:
- Sharp Centre for Design (High-tech, playful, steel-color) [Like]
- Lou Ruvo Center (Deconstructivist, sculptural, steel) [Like]
- Walt Disney Concert Hall (Deconstructivist, sculptural, steel) [Love]

CANDIDATES:
[1] B03001 Guangzhou Opera House — Hadid, Parametric, Public, steel-glass, fluid sculptural dramatic
[2] B03002 Strip Mall (1985) — Unknown, Vernacular, Mixed Use, stucco, bland anonymous commercial
[3] B03003 Jewish Museum Berlin — Libeskind, Deconstructivist, Museum, zinc-titanium, fragmented somber sculptural
[4] B03004 Heydar Aliyev Center — Hadid, Parametric, Public, concrete-fiberglass, fluid monumental sweeping
[5] B03005 Vitra Fire Station — Hadid, Deconstructivist, Other, concrete, angular dynamic sharp

Return your JSON ranking now.
ASSISTANT: {"ranking": ["B03005", "B03003", "B03004", "B03001", "B03002"]}

USER: LIKED SUMMARY:
- Therme Vals (Critical Regionalist, contemplative tactile dim, stone) [Love]
- Salk Institute (Modernist, monumental contemplative, concrete) [Love]
- Kimbell Art Museum (Modernist, contemplative luminous, concrete) [Like]

CANDIDATES:
[1] B04001 Generic Office Tower — anon, Contemporary, Office, glass-steel, sleek polished neutral
[2] B04002 Hill House (Mackintosh) — Mackintosh, Arts and Crafts, Housing, stone, austere refined contemplative
[3] B04003 Modern Suburban Home — anon, Contemporary, Housing, mixed, comfortable airy bright
[4] B04004 Yokohama Port Terminal — FOA, Parametric, Transport, steel-glass, fluid public dynamic
[5] B04005 Maison de Verre — Chareau, Modernist, Housing, glass-steel, transparent industrial layered
[6] B04006 Wabi Tea House — anon, Vernacular, Religion, timber-paper, austere quiet contemplative

Return your JSON ranking now.
ASSISTANT: {"ranking": ["B04002", "B04006", "B04005", "B04004", "B04003", "B04001"]}

USER: LIKED SUMMARY:
- Glass Pavilion at Toledo Museum (Contemporary, transparent floating, glass) [Like]

CANDIDATES:
[1] B05001 Farnsworth House — Mies, Modernist, Housing, steel-glass, transparent floating austere
[2] B05002 De Young Museum — Herzog & de Meuron, Contemporary, Museum, copper, weathered tactile civic
[3] B05003 Ningbo History Museum — Wang Shu, Critical Regionalist, Museum, <none>, vernacular textured layered
[4] B05004 Mosque of Cordoba — historical, Islamic, Religion, stone-brick, majestic dim mystical
[5] B05005 New National Gallery — Mies, Modernist, Public, steel-glass, transparent monumental austere

Return your JSON ranking now.
ASSISTANT: {"ranking": ["B05001", "B05005", "B05002", "B05004", "B05003"]}
"""


def _liked_summary_for_rerank(liked_ids):
    """
    Build a liked-summary string for rerank_candidates from project.liked_ids.

    Input liked_ids: list of str or {id, intensity} dicts (supports both legacy
    and new shapes). Intensity >= 1.5 is tagged [Love], < 1.5 is tagged [Like].

    Fetches building metadata (name_en, style, atmosphere, material) from
    architecture_vectors via batch SQL. Falls back to building_id only when
    metadata fetch fails or a row is missing.

    Truncated to approximately 1 K tokens (70 lines max) per Investigation 12
    BACK-RNK-3.

    Returns a string with one bullet per building.
    """
    from apps.recommendation import services as _svc  # noqa: PLC0415

    if not liked_ids:
        return ''

    # Normalise to list of (building_id, intensity) tuples
    entries = []
    for item in liked_ids:
        if isinstance(item, str):
            entries.append((item, 1.0))
        elif isinstance(item, dict) and 'id' in item:
            intensity = float(item.get('intensity', 1.0))
            entries.append((item['id'], intensity))

    if not entries:
        return ''

    # Truncate to ~70 entries (~1 K token budget at ~14 tokens/line)
    MAX_ENTRIES = 70
    entries = entries[-MAX_ENTRIES:]  # keep most recent (current taste)

    building_ids = [bid for bid, _ in entries]
    intensity_map = {bid: intensity for bid, intensity in entries}

    # Fetch metadata from architecture_vectors
    metadata_map = {}
    try:
        placeholders = ','.join(['%s'] * len(building_ids))
        with _svc.connection.cursor() as cur:
            cur.execute(
                f'SELECT building_id, name_en, style, atmosphere, material '
                f'FROM architecture_vectors WHERE building_id IN ({placeholders})',
                building_ids,
            )
            rows = _svc._dictfetchall(cur)
        for row in rows:
            metadata_map[row['building_id']] = row
    except Exception as e:
        logger.warning('_liked_summary_for_rerank metadata fetch failed: %s', e)

    lines = []
    for bid in building_ids:
        intensity = intensity_map.get(bid, 1.0)
        tag = '[Love]' if intensity >= 1.5 else '[Like]'
        meta = metadata_map.get(bid)
        if meta:
            name_en = meta.get('name_en') or bid
            style = meta.get('style') or ''
            atmosphere = meta.get('atmosphere') or ''
            material = meta.get('material') or '<none>'
            parts = ', '.join(p for p in [style, atmosphere, material] if p)
            lines.append(f'- {name_en} ({parts}) {tag}')
        else:
            lines.append(f'- {bid} {tag}')

    return '\n'.join(lines)


def rerank_candidates(candidates, liked_summary):
    """
    Gemini 2.5-flash setwise rerank of candidate buildings against the user's
    liked_summary. Returns full ordering (length matches input) -- list of
    building_ids from most to least aligned with taste.

    Input candidates: list of dicts with keys building_id, name_en, atmosphere,
    material, architect, style, program (Investigation 12 I/O design Inputs).
    Truncated to 60 candidates max per spec.

    On failure (parse error, timeout, partial coverage, validation): logs
    WARNING and returns input order (cosine_rank as-is). Per spec 5.4:
    silent graceful degradation.
    """
    from apps.recommendation import services as _svc  # noqa: PLC0415

    if not candidates:
        return []

    # Truncate to 60 per spec
    candidates = candidates[:60]
    input_ids = [c['building_id'] for c in candidates]

    # Build user prompt (compact one-line-per-candidate per Investigation 12)
    candidate_lines = []
    for i, c in enumerate(candidates, start=1):
        bid = c.get('building_id', '')
        name_en = c.get('name_en', '')
        architect = c.get('architect', '') or 'anon'
        style = c.get('style', '') or ''
        program = c.get('program', '') or ''
        material = c.get('material', '') or '<none>'
        atmosphere = c.get('atmosphere', '') or ''
        candidate_lines.append(
            f'[{i}] {bid} {name_en} — {architect}, {style}, {program}, {material}, {atmosphere}'
        )

    user_prompt = (
        f'LIKED SUMMARY:\n{liked_summary}\n\n'
        f'CANDIDATES:\n' + '\n'.join(candidate_lines) + '\n\nReturn your JSON ranking now.'
    )

    try:
        client = _svc._get_client()

        def _call():
            return client.models.generate_content(
                model='gemini-2.5-flash',
                contents=user_prompt,
                config=types.GenerateContentConfig(
                    system_instruction=_RERANK_SYSTEM_PROMPT,
                    response_mime_type='application/json',
                    temperature=0.0,
                    thinking_config=types.ThinkingConfig(thinking_budget=0),
                ),
            )

        response = _svc._retry_gemini_call(_call)
        raw_text = response.text

    except Exception as e:
        logger.warning(
            'rerank_candidates Gemini call failed (exception): %s: %s',
            type(e).__name__, str(e),
        )
        _svc.event_log.emit_event(
            'failure',
            session=None,
            user=None,
            failure_type='gemini_rerank',
            recovery_path='cosine_fallback',
            rerank_status='exception',
            error_class=type(e).__name__,
            error_message=str(e)[:200],
        )
        return list(input_ids)

    # Validate per Investigation 12 BACK-RNK-6
    return _validate_rerank_response(raw_text, input_ids)


def _validate_rerank_response(raw_text, input_ids):
    """
    Validate Gemini rerank response. Returns ordered list of building_ids on
    success or input_ids (cosine order) on any validation failure.

    Validation steps per Investigation 12:
    1. JSON parses
    2. 'ranking' key exists, is a list, all elements are strings
    3. set(ranking) == set(input_ids) AND len(ranking) == len(input_ids)
    """
    from apps.recommendation import services as _svc  # noqa: PLC0415

    input_id_set = set(input_ids)

    # Step 1: JSON parse
    try:
        obj = json.loads(raw_text)
    except (json.JSONDecodeError, ValueError) as e:
        logger.warning(
            'rerank_candidates validation failed [parse_fail]: %s', e,
        )
        _svc.event_log.emit_event(
            'failure',
            session=None,
            user=None,
            failure_type='gemini_rerank',
            recovery_path='cosine_fallback',
            rerank_status='parse_fail',
        )
        return list(input_ids)

    # Step 2: ranking key exists, is a list, all strings
    ranking = obj.get('ranking')
    if not isinstance(ranking, list):
        logger.warning(
            'rerank_candidates validation failed [wrong_type]: ranking is %s',
            type(ranking).__name__,
        )
        _svc.event_log.emit_event(
            'failure',
            session=None,
            user=None,
            failure_type='gemini_rerank',
            recovery_path='cosine_fallback',
            rerank_status='wrong_type',
        )
        return list(input_ids)

    if not all(isinstance(item, str) for item in ranking):
        logger.warning(
            'rerank_candidates validation failed [wrong_type]: ranking contains non-strings',
        )
        _svc.event_log.emit_event(
            'failure',
            session=None,
            user=None,
            failure_type='gemini_rerank',
            recovery_path='cosine_fallback',
            rerank_status='wrong_type',
        )
        return list(input_ids)

    # Step 3: set equality + length check (catches duplicates and missing/extra ids)
    if len(ranking) != len(input_ids) or set(ranking) != input_id_set:
        # Distinguish missing ids from extra ids from duplicates for logging
        ranking_set = set(ranking)
        if len(set(ranking)) != len(ranking):
            tag = 'duplicates'
        elif not ranking_set.issubset(input_id_set) or not input_id_set.issubset(ranking_set):
            tag = 'id_mismatch'
        else:
            tag = 'id_mismatch'
        logger.warning(
            'rerank_candidates validation failed [%s]: got %d ids, expected %d',
            tag, len(ranking), len(input_ids),
        )
        _svc.event_log.emit_event(
            'failure',
            session=None,
            user=None,
            failure_type='gemini_rerank',
            recovery_path='cosine_fallback',
            rerank_status=tag,
        )
        return list(input_ids)

    return ranking
