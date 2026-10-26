"""
generation.py -- Gemini-backed generation functions.

Sprint 4 §8: generate_persona_report.
Gemini-native image generation: generate_persona_image (replaces Imagen 3).
TASTE-BOARD-NAME: generate_taste_board_name (auto-name Taste session boards).

Cross-module symbol access uses the late-bound package reference (_svc) so that
mock.patch('apps.recommendation.services.X') continues to work in tests.
"""
import base64
import json
import logging
import re
import time
from collections import Counter

from django.conf import settings
from google.genai import types

from ._pattern_text import (
    build_fallback_paragraph,
    numbers_allowed,
)
from ._report_prompts import build_persona_prompt
from .taste_facts import AXES as _TASTE_AXES
from .taste_facts import compute_taste_facts, extract_axis_values

logger = logging.getLogger('apps.recommendation')


_REPORT_TEXT_FIELDS = ('persona_type', 'one_liner', 'pattern_paragraph', 'description')


def _extract_lang_block(raw, lang_key):
    """Return a normalised {persona_type, one_liner, pattern_paragraph,
    description} dict from raw[lang_key], or None if that key is absent / not
    a dict / missing any required field entirely (a dict present but missing
    one field still counts -- missing fields default to '')."""
    block = raw.get(lang_key) if isinstance(raw, dict) else None
    if not isinstance(block, dict):
        return None
    return {field: block.get(field, '') for field in _REPORT_TEXT_FIELDS}


def _fetch_taste_rows(building_ids):
    """Fetch the taste-axis attributes of `building_ids` (publishable-gated) in
    one query on the buildings connection. Returns a list of row dicts."""
    from apps.recommendation import services as _svc  # noqa: PLC0415

    if not building_ids:
        return []
    placeholders = ','.join(['%s'] * len(building_ids))
    with _svc.connection.cursor() as cur:
        cur.execute(
            f'SELECT canonical_bld_id, program, style, atmosphere, color_tone,'
            f' material_visual, typology_primary, typology_tags, architectural_elements,'
            f' project_year, location_country, architect_names, architects_text,'
            f' visual_description'
            f' FROM canonical_v2_buildings'
            f' WHERE canonical_bld_id IN ({placeholders}) AND is_publishable = true',
            list(building_ids),
        )
        return _svc._dictfetchall(cur)


def generate_persona_report(liked_building_ids, disliked_building_ids=None, language='ko'):
    """
    Generate an architect persona report from liked (+ optionally disliked)
    canonical_bld_ids. BACK-LLM-5: taste text is grounded in deterministic
    swipe facts (taste_facts.compute_taste_facts) rather than left to the LLM
    to infer unconstrained -- the model phrases/interprets facts it is handed,
    it does not invent them.

    FULL-REPORT-BILINGUAL (2026-09-27): ONE Gemini call now returns BOTH a
    Korean and an English version of the human-readable fields (see
    _report_prompts.build_persona_prompt). Both are stored under
    report['i18n']['ko'] / ['en'] (4 text fields each) so the frontend can
    switch UI language instantly without another API call. The top-level
    persona_type/one_liner/pattern_paragraph/description keys are ALSO kept,
    set to the `language`-matching version (fallback 'ko'), for backward
    compatibility with existing consumers (SaveBoardModal default name,
    generate_persona_image, share text, older frontend builds) that only
    ever read the flat top-level fields.

    Backward compatible: callers passing only `liked_building_ids` (the
    pre-BACK-LLM-5 call shape) still work -- disliked_building_ids defaults to
    none and language defaults to 'ko'.

    Returns a dict with persona fields (+ `taste_facts`, backend-attached, see
    below) on success. Raises an exception with a descriptive message on
    failure (caller handles response). Returns None only if no building data
    is found for the given ids.

    Args:
        liked_building_ids:    list[str] canonical_bld_id.
        disliked_building_ids: list[str] canonical_bld_id, or None.
        language:               'ko' or 'en' (UserProfile.language); used to
            pick which language populates the top-level (non-i18n) fields.
            Default 'ko'.
    """
    from apps.recommendation import services as _svc  # noqa: PLC0415

    liked_building_ids = list(liked_building_ids or [])
    disliked_building_ids = list(disliked_building_ids or [])

    if not liked_building_ids:
        return None

    lang = language if language in ('ko', 'en') else 'ko'
    rc = settings.RECOMMENDATION

    # Fetch attributes of liked+disliked buildings (publishable-gated) in one
    # query -- taste_facts needs BOTH sides to compute shown-set ratios.
    all_ids = list(dict.fromkeys(liked_building_ids + disliked_building_ids))
    rows = _fetch_taste_rows(all_ids)

    if not rows:
        return None

    rows_by_id = {r['canonical_bld_id']: r for r in rows if r.get('canonical_bld_id')}

    taste_facts = compute_taste_facts(rows_by_id, liked_building_ids, disliked_building_ids, rc)
    facts = taste_facts.get('facts', [])
    tier = taste_facts.get('tier', 'none')
    # 'facts' = like/dislike facts (strict or relaxed), 'composition' = liked-only
    # counts, 'interpretive' = no grounded fact -> number-free paragraph from tags.
    pattern_mode = {
        'strict': 'facts', 'relaxed': 'facts', 'composition': 'composition',
    }.get(tier, 'interpretive')

    # Liked-only tag frequencies (for the interpretive `description` paragraph
    # -- NOT the shown-vs-not-shown ratio math that drives `pattern_paragraph`,
    # which comes from `facts` above). Reuses taste_facts.extract_axis_values
    # so counting stays axis-for-axis consistent with the fact math.
    liked_id_set = set(liked_building_ids)
    liked_tag_frequencies = {}
    for axis in _TASTE_AXES:
        counter = Counter()
        for bid in liked_id_set:
            row = rows_by_id.get(bid)
            if not row:
                continue
            for value in extract_axis_values(row, axis):
                counter[value] += 1
        if counter:
            liked_tag_frequencies[axis] = dict(counter.most_common(10))

    # Up to 5 liked visual_description excerpts, truncated to ~300 chars each.
    liked_visual_excerpts = []
    for bid in liked_building_ids:
        row = rows_by_id.get(bid)
        vd = (row or {}).get('visual_description')
        if vd:
            liked_visual_excerpts.append(vd[:300])
        if len(liked_visual_excerpts) >= 5:
            break

    payload = {
        'language': lang,
        'liked_count': len(liked_id_set),
        'pattern_mode': pattern_mode,
        'facts': [
            {k: v for k, v in fact.items() if k != 'building_ids'}
            for fact in facts
        ],
        'liked_tag_frequencies': liked_tag_frequencies,
        'liked_visual_description_excerpts': liked_visual_excerpts,
    }
    contents = json.dumps(payload, ensure_ascii=False)

    try:
        # USER DECISION 2026-08-05: persona text stays Gemini even when the
        # parse/board text provider is switched to openai (B pick).
        client = _svc._get_gemini_client()

        response = _svc.generate_content_with_fallback(
            client,
            provider='gemini',
            contents=contents,
            config=types.GenerateContentConfig(
                system_instruction=build_persona_prompt(lang),
                response_mime_type='application/json',
                temperature=0.7,
                thinking_config=types.ThinkingConfig(thinking_budget=0),
            ),
        )
        raw = json.loads(response.text)
    except json.JSONDecodeError as e:
        logger.error('generate_persona_report JSON decode error: %s', e)
        _svc.event_log.emit_event(
            'failure',
            session=None,
            user=None,
            failure_type='gemini_parse',
            recovery_path='none',
            error_class='JSONDecodeError',
            error_message=str(e)[:200],
        )
        raise ValueError('Gemini returned an invalid response format. Please try again.')
    except Exception as e:
        logger.error('generate_persona_report failed after retries: %s: %s', type(e).__name__, e)
        _svc.event_log.emit_event(
            'failure',
            session=None,
            user=None,
            failure_type='gemini_parse',
            recovery_path='none',
            error_class=type(e).__name__,
            error_message=str(e)[:200],
        )
        raise RuntimeError(f'Persona report generation failed: {type(e).__name__}. Please try again later.')

    # FULL-REPORT-BILINGUAL: raw is expected to be {"ko": {...4 fields}, "en":
    # {...4 fields}, "dominant_programs": [...], ...}. Older model output (or
    # a model that ignored the ko/en instruction) may instead be the flat
    # pre-BACK-LLM-5-bilingual shape (the 4 text fields directly at the top
    # level) -- treat that as the single `lang` the caller requested.
    ko_block = _extract_lang_block(raw, 'ko')
    en_block = _extract_lang_block(raw, 'en')

    if ko_block is None and en_block is None:
        flat_block = (
            {field: raw.get(field, '') for field in _REPORT_TEXT_FIELDS}
            if isinstance(raw, dict) else {field: '' for field in _REPORT_TEXT_FIELDS}
        )
        if lang == 'en':
            en_block = flat_block
        else:
            ko_block = flat_block

    if ko_block is None:
        logger.warning(
            'generate_persona_report: ko block missing/malformed in Gemini output; filling from en',
        )
        ko_block = dict(en_block)
    elif en_block is None:
        logger.warning(
            'generate_persona_report: en block missing/malformed in Gemini output; filling from ko',
        )
        en_block = dict(ko_block)

    chosen = ko_block if lang == 'ko' else en_block
    report = {
        'persona_type': chosen['persona_type'],
        'one_liner': chosen['one_liner'],
        'pattern_paragraph': chosen['pattern_paragraph'],
        'description': chosen['description'],
        'dominant_programs': (raw.get('dominant_programs') or []) if isinstance(raw, dict) else [],
        'dominant_styles': (raw.get('dominant_styles') or []) if isinstance(raw, dict) else [],
        'dominant_materials': (raw.get('dominant_materials') or []) if isinstance(raw, dict) else [],
        'i18n': {'ko': ko_block, 'en': en_block},
    }

    # 2026-10-25 product decision: pattern_paragraph is ALWAYS present. Every
    # number must come from real data, so LLM text is guarded and blanks are
    # filled deterministically (see _pattern_text.py).
    pattern_source = {'strict': 'facts', 'relaxed': 'relaxed', 'composition': 'composition'}.get(
        tier, 'interpretive',
    )
    used_fallback = False
    for key in ('ko', 'en'):
        block = report['i18n'][key]
        text = (block.get('pattern_paragraph') or '').strip()
        if text and not numbers_allowed(text, facts, pattern_mode):
            logger.warning(
                'generate_persona_report: %s pattern_paragraph has ungrounded numbers (mode=%s); using fallback',
                key, pattern_mode,
            )
            text = ''
        if not text:
            text, kind = build_fallback_paragraph(facts, liked_tag_frequencies, key)
            used_fallback = True
            logger.warning(
                'generate_persona_report: blank/rejected %s pattern_paragraph; deterministic fallback (%s)',
                key, kind,
            )
        block['pattern_paragraph'] = text
    if used_fallback:
        pattern_source = 'fallback'
    report['pattern_paragraph'] = report['i18n'][lang]['pattern_paragraph']
    report['pattern_source'] = pattern_source
    # Backend-computed, not LLM. Not rendered directly by the frontend
    # (BACK-LLM-5 spec: "화면에는 표시하지 않습니다") -- but IS persisted on
    # project.final_report. The report is OWNER-ONLY: non-owners get
    # final_report/analysis_report/axis_scores nulled (report_stale False) from
    # ProjectSerializer, and /recommendations/ is owner-only. The owner still
    # receives it, and serializers.py's `disliked_ids` invariant (never exposed
    # to ANY caller, owner included) therefore applies here:
    # a dislike fact's `building_ids` are disliked
    # canonical_bld_ids, so they must be stripped before attaching. A like
    # fact's `building_ids` are liked ids, already exposed via the
    # `liked_ids` field on the same serializer, so those are kept (useful
    # for future audit/debug UIs without re-deriving them).
    report['taste_facts'] = {
        'summary': taste_facts['summary'],
        'tier': tier,
        'facts': [
            fact if fact.get('polarity') in ('like', 'composition')
            else {k: v for k, v in fact.items() if k != 'building_ids'}
            for fact in facts
        ],
    }
    return report


# ---------------------------------------------------------------------------
# TASTE-BOARD-NAME: auto-name helper
# ---------------------------------------------------------------------------

# Priority order for deterministic fallback name construction.
_NAME_FILTER_PRIORITY = ['style', 'program', 'typology_primary', 'material', 'location_country']

# Characters to keep when sanitising Gemini output (alnum + spaces).
_NAME_KEEP_RE = re.compile(r'[^A-Za-z0-9 ]')


def _sanitise_board_name(raw):
    """Strip, collapse whitespace, keep alnum+spaces, Title Case, clamp ≤2 words ≤40 chars."""
    if not raw or not isinstance(raw, str):
        return ''
    cleaned = _NAME_KEEP_RE.sub('', raw).strip()
    # Collapse runs of whitespace
    cleaned = re.sub(r'\s+', ' ', cleaned)
    words = cleaned.split()[:2]
    name = ' '.join(w.capitalize() for w in words)
    return name[:40]


def _deterministic_board_name(filters):
    """Build a name from the most salient filter values (≤2 words, Title Case).

    Priority: style > program > typology_primary > material > location_country.
    Returns 'Untitled' when no usable filter exists.
    """
    parts = []
    for key in _NAME_FILTER_PRIORITY:
        val = filters.get(key)
        if val and isinstance(val, str) and val.strip():
            parts.append(val.strip().capitalize())
        if len(parts) == 2:
            break
    if parts:
        return ' '.join(parts)[:40]
    return 'Untitled'


def _dedup_board_name(base_name, profile):
    """Return base_name or base_name (N) such that it is unique for this user's Projects."""
    from apps.recommendation.models import Project  # local import to avoid circular
    existing = set(
        Project.objects.filter(user=profile).values_list('name', flat=True)
    )
    if base_name not in existing:
        return base_name
    n = 1
    while True:
        candidate = f'{base_name} ({n})'
        if candidate not in existing:
            return candidate
        n += 1


def _gemini_board_name_raw(filters, raw_query):
    """Call Gemini and return the sanitised name string (or '' on any failure).

    THREAD-SAFE: pure Gemini + CPU work only — NO ORM / DB access.
    Intended to run in a background thread inside create_session so the
    8 s timeout overlaps with pool construction.  All DB work (fallback
    from filters, dedup) MUST happen on the calling (main) thread after
    this returns.

    Args:
        filters:   dict — active_filters (legacy image_focus key ignored).
        raw_query: str  — verbatim user search text.

    Returns:
        str — sanitised ≤2-word Title Case name, or '' if Gemini failed.
    """
    from apps.recommendation import services as _svc  # noqa: PLC0415

    filters = filters or {}
    raw_query = (raw_query or '').strip()
    try:
        client = _svc._get_client()
        filter_json = json.dumps(
            {k: v for k, v in filters.items() if v},
            ensure_ascii=False,
        )
        prompt = (
            'Return ONLY a 2-word-or-less English architectural theme name in Title Case'
            ' — no punctuation, no quotes, no preamble — summarizing this architecture'
            f' search. filters={filter_json}, query={raw_query!r}.'
            ' Examples: Brick House, Japanese Modern, Brutalist Civic, Coastal Pavilion.'
        )
        response = _svc.generate_content_with_fallback(
            client,
            contents=prompt,
            config=types.GenerateContentConfig(
                temperature=0.3,
                thinking_config=types.ThinkingConfig(thinking_budget=0),
            ),
            timeout=8.0,
        )
        return _sanitise_board_name(response.text or '')
    except Exception as exc:
        logger.info(
            '_gemini_board_name_raw failed (%s: %s); caller will use deterministic fallback',
            type(exc).__name__, str(exc)[:120],
        )
        return ''


def generate_taste_board_name(profile, filters, raw_query, visual_description=None):
    """Return a ≤2-word English Title-Case board name derived from the search context.

    Synchronous convenience wrapper (Gemini + fallback + dedup in one call).
    For the session-creation hot-path use _gemini_board_name_raw in a thread
    and call _deterministic_board_name + _dedup_board_name on the main thread.

    1. Try a Gemini call (8 s hard timeout).
    2. On Gemini failure / empty / bad output: deterministic fallback from filters.
    3. Dedup with ' (N)' suffix against existing Project names for this user.

    Args:
        profile:            UserProfile instance (used for dedup query).
        filters:            dict of active_filters from the session request.
        raw_query:          str, the verbatim user search text (may be empty).
        visual_description: str or None (reserved for future use).

    Returns:
        str — unique board name for this user, never empty.
    """
    filters = filters or {}
    gemini_name = _gemini_board_name_raw(filters, raw_query)
    base_name = gemini_name if gemini_name else _deterministic_board_name(filters)
    return _dedup_board_name(base_name, profile)


def _gen_native(client, prompt):
    """
    Attempt native image generation via the provider selected by
    settings.LLM_IMAGE_PROVIDER (gemini|openai, default gemini). Returns
    (raw_bytes, mime_type, used_model) on success, or (None, None, None) if
    no image part is found or all attempts fail (gemini branch only -- the
    openai branch re-raises instead, see below).

    raw_bytes is the raw image bytes (not base64) in both branches -- the
    openai branch base64-decodes resp.data[0].b64_json before returning.

    BACK-LLM-PROVIDER-2: LLM_IMAGE_PROVIDER is INDEPENDENT of LLM_PROVIDER (the
    text-parse switch) so text/image providers mix freely.

    gemini branch (default): tries settings.GEMINI_IMAGE_MODEL first, then
    settings.GEMINI_IMAGE_MODEL_FALLBACK on NotFound/InvalidArgument. Uses
    _svc._get_gemini_client() (always genai, separate singleton) -- the
    caller-supplied `client` is IGNORED here, exactly as before
    BACK-LLM-PROVIDER-2 (BACK-LLM-PROVIDER-1 behaviour preserved unchanged).

    openai branch: single model (settings.OPENAI_IMAGE_MODEL), NO fallback
    loop -- re-raises on failure. Uses _svc._get_openai_client() (always
    openai, separate singleton from the text-path client). gpt-image models
    always return b64_json (response_format is NOT a valid param for them),
    so the b64_json field is decoded directly; mime is always image/png.
    """
    from apps.recommendation import services as _svc  # noqa: PLC0415

    if settings.LLM_IMAGE_PROVIDER == 'openai':
        client = _svc._get_openai_client()
        resp = _svc._retry_gemini_call(
            client.images.generate,
            timeout=45.0,
            model=settings.OPENAI_IMAGE_MODEL,
            prompt=prompt,
            size='1536x1024',
            quality=settings.OPENAI_IMAGE_QUALITY,
        )
        raw = base64.b64decode(resp.data[0].b64_json)
        return raw, 'image/png', settings.OPENAI_IMAGE_MODEL

    client = _svc._get_gemini_client()

    for model in (settings.GEMINI_IMAGE_MODEL, settings.GEMINI_IMAGE_MODEL_FALLBACK):
        try:
            resp = _svc._retry_gemini_call(
                client.models.generate_content,
                model=model,
                contents=[prompt],
                config=types.GenerateContentConfig(
                    response_modalities=['TEXT', 'IMAGE'],
                    image_config=types.ImageConfig(aspect_ratio='16:9'),
                ),
                timeout=45.0,
            )
            # Empty/safety-filtered response (no candidates or no parts) -> try next model.
            cand = (resp.candidates or [None])[0]
            content = getattr(cand, 'content', None) if cand else None
            parts = getattr(content, 'parts', None) if content else None
            for part in (parts or []):
                idata = getattr(part, 'inline_data', None)
                if idata and getattr(idata, 'data', None):
                    return idata.data, idata.mime_type, model
        except Exception as e:
            if _svc._is_model_unavailable(e):
                logger.warning('image model %s rejected (%s); trying next', model, type(e).__name__)
                continue
            raise
    return None, None, None


def _to_webp(raw):
    """
    Convert raw image bytes to WebP format using Pillow.

    Returns (webp_bytes, 'image/webp') on success, or (raw, None) if Pillow
    fails (caller falls back to the native mime_type).
    """
    try:
        from io import BytesIO

        from PIL import Image
        img = Image.open(BytesIO(raw)).convert('RGB')
        buf = BytesIO()
        img.save(buf, format='WEBP', quality=82, method=6)
        return buf.getvalue(), 'image/webp'
    except Exception as e:
        logger.warning('webp convert failed: %s: %s', type(e).__name__, e)
        return raw, None


_FACTS_IMAGE_DEFAULT_ATMOSPHERE = 'serene and monumental'


def build_image_report_from_facts(liked_building_ids, disliked_building_ids=None):
    """FULL-REPORT-IMG-1: build a pseudo persona report for generate_persona_image
    from Python-computed taste facts ONLY (no LLM, no stored final_report), so
    the persona image can start generating in parallel with the report.

    Returns the dict shape generate_persona_image reads --
    {dominant_styles, dominant_programs, dominant_materials, one_liner} -- or
    None when none of the ids resolve to a publishable building row.

    Each dominant_* list is led by the values of the `like` facts on the
    matching axis (compute_taste_facts: strongest liked-vs-shown signal),
    then topped up with the most frequent value among LIKED buildings so a
    short swipe session (no fact clears its thresholds) still yields a
    grounded prompt. `one_liner` is a deterministic phrase from the liked
    atmosphere (fallback color_tone) values -- no LLM call.
    """
    liked_building_ids = list(liked_building_ids or [])
    disliked_building_ids = list(disliked_building_ids or [])
    if not liked_building_ids:
        return None

    all_ids = list(dict.fromkeys(liked_building_ids + disliked_building_ids))
    rows = _fetch_taste_rows(all_ids)
    if not rows:
        return None
    rows_by_id = {r['canonical_bld_id']: r for r in rows if r.get('canonical_bld_id')}

    taste_facts = compute_taste_facts(
        rows_by_id, liked_building_ids, disliked_building_ids, settings.RECOMMENDATION,
    )
    like_facts = [f for f in taste_facts.get('facts', []) if f.get('polarity') == 'like']

    liked_unique = list(dict.fromkeys(liked_building_ids))

    def _top_values(axis, limit):
        values = [f['value'] for f in like_facts if f.get('axis') == axis]
        counter = Counter()
        for bid in liked_unique:  # ordered iteration keeps ties deterministic
            row = rows_by_id.get(bid)
            if row:
                for value in sorted(extract_axis_values(row, axis)):
                    counter[value] += 1
        for value, _count in counter.most_common():
            if value not in values:
                values.append(value)
        return values[:limit]

    atmosphere = _top_values('atmosphere', 2) or _top_values('color_tone', 2)
    return {
        'dominant_styles': _top_values('style', 1),
        'dominant_programs': _top_values('program', 1),
        'dominant_materials': _top_values('material_visual', 3),
        'one_liner': ', '.join(atmosphere) if atmosphere else _FACTS_IMAGE_DEFAULT_ATMOSPHERE,
    }


def generate_persona_image(report):
    """
    Generate an AI architecture image from a persona report using Gemini-native
    image generation (response_modalities=['TEXT','IMAGE']).

    Falls back from settings.GEMINI_IMAGE_MODEL to settings.GEMINI_IMAGE_MODEL_FALLBACK
    on model rejection.  Output is converted to WebP when settings.GEMINI_IMAGE_FORMAT
    == 'webp' (default) using Pillow.

    Returns {'image_data': base64_str, 'mime_type': str, 'prompt': str} or None on
    failure.  Emits 'persona_image_timing' event with latency + outcome.
    """
    from apps.recommendation import services as _svc  # noqa: PLC0415

    if not report:
        return None

    t_img_start = time.perf_counter()
    used_model = None
    outcome = 'none'

    try:
        style = (report.get('dominant_styles') or ['Contemporary'])[0]
        program = (report.get('dominant_programs') or ['Housing'])[0]
        materials = ', '.join(report.get('dominant_materials') or ['concrete'])
        one_liner = report.get('one_liner', 'serene and monumental')

        prompt = (
            f"A photorealistic architectural photograph of a building. "
            f"{style} style, {program} typology, atmosphere: {one_liner}. "
            f"Materials: {materials}. "
            f"Professional architectural photography, golden hour lighting, "
            f"high quality, 8k resolution. Wide 16:9 cinematic aspect ratio."
        )

        client = _svc._get_client()

        raw, native_mime, used_model = _gen_native(client, prompt)
        if raw is None:
            outcome = 'model_failure'
            return None

        if settings.GEMINI_IMAGE_FORMAT == 'webp':
            out, mime = _to_webp(raw)
            if mime is None:
                # Pillow conversion failed — use native bytes + native mime
                mime = native_mime
                outcome = 'convert_fallback'
            else:
                outcome = 'success'
        else:
            out, mime = raw, native_mime
            outcome = 'success'

        return {
            'image_data': base64.b64encode(out).decode('utf-8'),
            'mime_type': mime,
            'prompt': prompt,
        }
    except Exception as e:
        logger.error('generate_persona_image error: %s: %s', type(e).__name__, e)
        outcome = 'model_failure'
        return None
    finally:
        gemini_image_ms = round((time.perf_counter() - t_img_start) * 1000, 2)
        _svc.event_log.emit_event(
            'persona_image_timing',
            session=None,
            user=None,
            gemini_image_ms=gemini_image_ms,
            model=used_model,
            outcome=outcome,
        )
