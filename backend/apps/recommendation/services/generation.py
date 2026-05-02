"""
generation.py -- Gemini-backed generation functions.

IMP-6 Commit 2: generate_visual_description (Stage 2 background worker).
Sprint 4 §8: generate_persona_report.
Imagen 3: generate_persona_image.

Cross-module symbol access uses the late-bound package reference (_svc) so that
mock.patch('apps.recommendation.services.X') continues to work in tests.
"""
import base64
import json
import logging
import time

from google.genai import types

logger = logging.getLogger('apps.recommendation')

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


def generate_visual_description(filters, raw_query, user_id):
    """IMP-6 Commit 2: Stage 2 worker -- generates visual_description + V_initial.

    Runs in a background thread (daemon=True) spawned by ParseQueryView after
    Stage 1 returns on a terminal turn (probe_needed=False).

    Operation:
        1. Single Gemini call producing ONLY visual_description text (~140-180 tokens).
        2. embed_visual_description(visual_description) -> 384-dim float list.
        3. set_cached_v_initial(user_id, raw_query, v_initial) for SessionCreate late-bind.
        4. Emit 'stage2_timing' event with full telemetry.

    Defensive: catches all exceptions; failures never bubble up to the user.
    SessionCreate falls through to filter-only pool on cache miss (graceful degrade
    per spec v1.5 Topic 01).

    Args:
        filters: dict of parsed filters from Stage 1 result.
        raw_query: str, the verbatim first user message (V_initial cache key component).
        user_id: int, request.user.id.

    Returns:
        visual_description string on success, None on failure.
    """
    # Late-bound package reference for cross-module symbol access.
    from apps.recommendation import services as _svc  # noqa: PLC0415

    t_stage2_start = time.perf_counter()
    gemini_visual_description_ms = None
    hf_inference_ms = None
    input_tokens = None
    output_tokens = None
    v_initial_computed = False
    v_initial_dim = None
    success = False
    error_class = None
    # State-progression outcome: advances as each stage succeeds.
    # Starts at 'gemini_failure' so any uncaught exception before HF is correctly classified.
    outcome = 'gemini_failure'

    try:
        client = _svc._get_client()

        # Build a concise prompt from filters + raw_query for visual description
        filter_parts = []
        if filters.get('program'):
            filter_parts.append(f"program: {filters['program']}")
        if filters.get('style'):
            filter_parts.append(f"style: {filters['style']}")
        if filters.get('material'):
            filter_parts.append(f"material: {filters['material']}")
        if filters.get('location_country'):
            filter_parts.append(f"country: {filters['location_country']}")
        filter_summary = ', '.join(filter_parts) if filter_parts else 'unspecified'

        stage2_prompt = (
            f"Write a vivid 2-4 sentence English architectural description for a building search. "
            f"The user query was: {raw_query!r}. "
            f"Inferred filters: {filter_summary}. "
            f"Output ONLY the description text -- no JSON, no labels, no preamble."
        )

        t_gemini_start = time.perf_counter()
        response = _svc._retry_gemini_call(
            client.models.generate_content,
            model='gemini-2.5-flash',
            contents=stage2_prompt,
            config=types.GenerateContentConfig(
                temperature=0.3,
                thinking_config=types.ThinkingConfig(thinking_budget=0),
            ),
        )
        t_gemini_end = time.perf_counter()
        gemini_visual_description_ms = round((t_gemini_end - t_gemini_start) * 1000, 2)

        _usage = getattr(response, 'usage_metadata', None)
        input_tokens = getattr(_usage, 'prompt_token_count', None) if _usage else None
        output_tokens = getattr(_usage, 'candidates_token_count', None) if _usage else None

        visual_description = (response.text or '').strip()
        if not visual_description:
            logger.warning('IMP-6 Stage 2: Gemini returned empty visual_description')
            error_class = 'EmptyResponse'
            return None

        # Gemini succeeded -- advance outcome state; HF failure now owns the error label.
        outcome = 'hf_failure'

        # Compute V_initial via HuggingFace Inference API (existing embed_visual_description).
        # Time the HF call regardless of its result (hf_inference_ms=None only when HF never fires).
        t_hf_start = time.perf_counter()
        v_initial = _svc.embed_visual_description(visual_description, session=None, user=None)
        hf_inference_ms = round((time.perf_counter() - t_hf_start) * 1000, 2)

        if v_initial is not None:
            # Defensive: verify dimension + non-zero norm before caching
            import numpy as _np
            v_arr = _np.asarray(v_initial, dtype=_np.float32)
            v_norm = _np.linalg.norm(v_arr)
            if len(v_initial) == 384 and v_norm > 0:
                # HF succeeded -- advance outcome state; cache failure now owns the error label.
                outcome = 'cache_failure'
                try:
                    _svc.set_cached_v_initial(user_id, raw_query, v_initial)
                except Exception as cache_exc:
                    logger.warning(
                        'IMP-6 Stage 2: set_cached_v_initial failed: %s: %s',
                        type(cache_exc).__name__, str(cache_exc),
                    )
                    error_class = type(cache_exc).__name__
                    return None
                v_initial_computed = True
                v_initial_dim = len(v_initial)
                logger.debug(
                    'IMP-6 Stage 2: V_initial cached for user=%s query_len=%d',
                    user_id, len(raw_query or ''),
                )
                # All stages passed -- advance to success.
                outcome = 'success'
                success = True
            else:
                logger.warning(
                    'IMP-6 Stage 2: V_initial dim=%d norm=%.4f -- skipping cache',
                    len(v_initial), v_norm,
                )
                error_class = 'BadVInitialVector'
                # outcome stays 'hf_failure' -- bad vector counts as HF-stage failure
        else:
            logger.warning('IMP-6 Stage 2: embed_visual_description returned None')
            error_class = 'EmbedFailed'
            # outcome stays 'hf_failure'

        return visual_description

    except Exception as e:
        error_class = type(e).__name__
        logger.warning(
            'IMP-6 generate_visual_description failed: %s: %s',
            type(e).__name__, str(e),
        )
        return None
    finally:
        # IMP-6 stage2_timing schema (per spec v1.7 §6):
        #   - stage2_total_ms / gemini_visual_description_ms / hf_inference_ms /
        #     pool_rerank_ms / outcome (in this commit)
        #   - v_initial_ready_at_first_card / cards_exposed_when_ready (DEFERRED
        #     to Commit 3 -- requires cross-request timing coordination between
        #     this Stage 2 thread and SessionCreateView's first-card-sent timing)
        # Extra non-spec fields (gemini_input/output_tokens, v_initial_computed/dim,
        # success, error_class) preserved for richer diagnostic.
        t_stage2_total = round((time.perf_counter() - t_stage2_start) * 1000, 2)
        _svc.event_log.emit_event(
            'stage2_timing',
            session=None,
            user=None,
            gemini_visual_description_ms=gemini_visual_description_ms,
            gemini_input_tokens=input_tokens,
            gemini_output_tokens=output_tokens,
            hf_inference_ms=hf_inference_ms,
            pool_rerank_ms=None,
            outcome=outcome,
            v_initial_computed=v_initial_computed,
            v_initial_dim=v_initial_dim,
            success=success,
            error_class=error_class,
            stage2_total_ms=t_stage2_total,
        )


def generate_persona_report(liked_building_ids):
    """
    Generate an architect persona report from a list of liked building_ids.
    Returns a dict with persona fields on success.
    Raises an exception with a descriptive message on failure (caller handles response).
    Returns None only if no building data is found.
    """
    from apps.recommendation import services as _svc  # noqa: PLC0415

    if not liked_building_ids:
        return None

    # Fetch attributes of liked buildings
    placeholders = ','.join(['%s'] * len(liked_building_ids))
    with _svc.connection.cursor() as cur:
        cur.execute(
            f'SELECT program, style, atmosphere, material, architect, location_country '
            f'FROM architecture_vectors WHERE building_id IN ({placeholders})',
            liked_building_ids,
        )
        rows = _svc._dictfetchall(cur)

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
        client = _svc._get_client()

        def _call():
            return client.models.generate_content(
                model='gemini-2.5-flash',
                contents=summary,
                config=types.GenerateContentConfig(
                    system_instruction=_PERSONA_PROMPT,
                    response_mime_type='application/json',
                    temperature=0.7,
                    thinking_config=types.ThinkingConfig(thinking_budget=0),
                ),
            )

        response = _svc._retry_gemini_call(_call)
        return json.loads(response.text)
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


def generate_persona_image(report):
    """
    Generate an AI architecture image from a persona report using Imagen 3.
    Returns {'image_data': base64_str, 'mime_type': str, 'prompt': str} or None on failure.
    """
    from apps.recommendation import services as _svc  # noqa: PLC0415

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

        client = _svc._get_client()

        def _call():
            return client.models.generate_images(
                model='imagen-3.0-generate-002',
                prompt=prompt,
                config=types.GenerateImagesConfig(
                    number_of_images=1,
                    aspect_ratio='16:9',
                ),
            )

        response = _svc._retry_gemini_call(_call)

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
