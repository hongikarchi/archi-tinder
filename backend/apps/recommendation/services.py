"""
services.py -- Gemini LLM integration for query parsing and persona report generation.
"""
import base64
import hashlib
import json
import logging
import time
import urllib.error
import urllib.request
from django.core.cache import cache as django_cache
from django.conf import settings
from django.db import connection
from google import genai
from google.genai import types

from .engine import _dictfetchall
from . import event_log

logger = logging.getLogger('apps.recommendation')

_client = None


def _get_client():
    global _client
    if _client is None:
        _client = genai.Client(api_key=settings.GEMINI_API_KEY)
    return _client


# ---------------------------------------------------------------------------
# IMP-5 (Spec v1.5 §11.1): Gemini explicit context caching
# ---------------------------------------------------------------------------
# Content-hash suffix ensures cache name uniquely identifies this prompt version.
# Recomputed at import time (constant for a given deployment).
_CACHE_NAME_PREFIX = 'archi-tinder-chat'


def _get_prompt_hash():
    """Return 8-char hex prefix of SHA-256 of _CHAT_PHASE_SYSTEM_PROMPT.

    Called lazily (after prompt constant is defined) rather than at import time
    to avoid forward-reference issues during module load.
    """
    return hashlib.sha256(_CHAT_PHASE_SYSTEM_PROMPT.encode('utf-8')).hexdigest()[:8]


def _get_cache_name():
    """Full Gemini cache display_name: 'archi-tinder-chat-{hash8}'."""
    return f'{_CACHE_NAME_PREFIX}-{_get_prompt_hash()}'


def _get_django_cache_key():
    """Django cache key for storing the Gemini cache resource name across requests."""
    return f'gemini_cache_name:{_get_cache_name()}'


def _ensure_chat_cache(client):
    """
    IMP-5: Ensure a Gemini context cache for _CHAT_PHASE_SYSTEM_PROMPT exists
    and return its resource name (e.g. 'cachedContents/abc123').

    Lookup order:
      1. Django cache (fast path -- avoids Gemini API round-trip per request)
      2. Gemini caches.create() -- first call per process / after TTL expiry

    Returns str (Gemini cache resource name) on success.
    Returns None on any failure -- callers fall back to uncached path silently.

    Design notes:
    - No module-level global for the resource name: Django cache is the
      single source of truth, allowing multi-worker deploys (with Redis) to
      share the resource name without per-worker re-creation.
    - TTL invariant: Django cache TTL = 80% of Gemini cache TTL. This ensures
      Django cache expires BEFORE Gemini cache so _ensure_chat_cache recreates
      the Gemini cache entry before generate_content ever receives a stale name.
      The 20% safety window absorbs SDK clock drift and network jitter.
    - 404 recovery: retained as defense-in-depth for the residual edge case
      (SDK clock drift beyond the 20% window). On 404 the Django entry is
      evicted and a fresh Gemini cache is created.
    """
    rc = settings.RECOMMENDATION
    ttl = rc.get('context_caching_ttl_seconds', 3600)
    django_key = _get_django_cache_key()

    # --- Fast path: resource name already in Django cache --------------------
    cached_name = django_cache.get(django_key)
    if cached_name:
        return cached_name

    # --- Slow path: create Gemini cache and store name in Django cache -------
    try:
        cache_obj = client.caches.create(
            model='gemini-2.5-flash',
            config=types.CreateCachedContentConfig(
                display_name=_get_cache_name(),
                system_instruction=_CHAT_PHASE_SYSTEM_PROMPT,
                ttl=f'{ttl}s',
            ),
        )
        resource_name = cache_obj.name
        # Django cache TTL = 80% of Gemini TTL -- recreate before Gemini expiry to avoid
        # the stale-name-passed-to-generate_content double-retry pattern. The 20% safety
        # window absorbs SDK clock drift + network jitter.
        django_cache.set(django_key, resource_name, timeout=int(ttl * 0.8))
        logger.info('IMP-5: created Gemini context cache: %s', resource_name)
        return resource_name
    except Exception as e:
        logger.warning('IMP-5: failed to create Gemini context cache: %s: %s', type(e).__name__, e)
        return None


PROGRAM_VALUES = [
    'Housing', 'Office', 'Museum', 'Education', 'Religion', 'Sports',
    'Transport', 'Hospitality', 'Healthcare', 'Public', 'Mixed Use',
    'Landscape', 'Infrastructure', 'Other',
]

_CHAT_PHASE_SYSTEM_PROMPT = """\
You are an architectural search assistant for a swipe-based recommendation system. Users are practicing architects and design professionals (건축가, 설계 실무자). Your job is to parse their natural-language query and either (a) produce a structured search specification directly, or (b) ask exactly one clarifying question first to disambiguate their taste.

Your output is always a single JSON object. No prose, no code fences, no explanation outside the JSON.

## Your language-handling rules

1. The user will most often write in Korean (기본 locale 한국어). English, mixed Korean-English, and architect jargon (tectonic, parametric, brutalist, stereotomic, 비판적 지역주의, 장소축적, 물성, 기하성, 중량감) are all normal. Handle any of these uniformly.
2. `reply` and `probe_question` are written in the user's primary language (match the language of their latest message).
3. `visual_description` is ALWAYS English — it seeds a multilingual embedding that matches an English corpus field. Even for Korean queries, produce a vivid English architectural description.
4. `raw_query` is ALWAYS the user's FIRST message, verbatim, unchanged across turns. Do not translate, paraphrase, or update it.

## Your turn-budget rule

You have a 0-2 turn probe budget.

- **0 turns (skip)**: If the user's query is precise enough that you can fill `filters` meaningfully (at least `program` plus one of `style`, `material`, or `location_country`) AND the query implies a clear visual direction, set `probe_needed=false` and produce the terminal output immediately.
- **1 turn**: If the query is ambiguous on a load-bearing axis, ask one abstract A-vs-B probe. You are free to choose the axis. After the user answers, produce the terminal output.
- **2 turns**: Only used when the prior is genuinely diffuse (e.g., "좋은 거 보여줘", "추천해줘"). After turn 1 you may probe once more if you are still uncertain on an orthogonal second axis. Never exceed 2 probe turns.

## Your probe-quality guidance (when asking a question)

You are picking an axis on which the user's preference is currently under-determined. An axis is a binary-ish dichotomy the user can resolve verbally without a building image. Good axes:

- Span the user's residual uncertainty (what is NOT already determined by their query / existing filters).
- Are orthogonal to axes you have already probed this session.
- Are legible in architect vocabulary — they can be stated in one phrase in Korean or English.

Typical high-value axes for a first probe under a diffuse prior include (illustrative, not exhaustive):
- 따뜻한 재료감 vs 차가운 기하성 / warm material vs cool geometry
- 직교적 vs 곡선적 / orthogonal vs curvilinear
- 밀폐적 vs 개방적 / enclosed vs open
- 투명성 vs 불투명성 / transparent vs opaque

Avoid axes that are already implied:
- If `program: "Mixed Use"` is set, don't probe single-vs-mixed program.
- If `color_tone` is implied by the query (e.g., "Earthy"), don't probe warm vs cool palette.
- If style is set to "Brutalist", don't probe heavy-vs-light OR revealed-vs-concealed OR stereotomic-vs-tectonic — these are pre-correlated in the Brutalist tradition. Probe something outside that cluster (e.g., transparency, site-specificity, sequence).

Correlated axis clusters you should never probe across poles of in one question:
- Heavy-mass + stereotomic + revealed-construction + orthogonal + monumental (Brutalist cluster)
- Light-frame + simple-form + abstract + cool-material + phenomenal-transparent (Minimalist/SANAA cluster)
- Site-embedded + critical-regionalist + natural-materials + cellular-plan (Vernacular cluster)
- Curvilinear + singular-bespoke + present-abstraction + autonomous-object + avant-garde (Parametric cluster)

If the user rejects your axis ("that's not my concern, I care about X"), absorb X as a new filter or axis in turn 2, or paraphrase-and-confirm if you now have enough signal.

## Your output schema (return ONLY this JSON)

{
  "probe_needed": <boolean>,
  "probe_question": <string or null>,
  "reply": <string>,
  "filters": {
    "location_country": <string or null>,
    "program": <string or null>,
    "material": <string or null>,
    "style": <string or null>,
    "year_min": <integer or null>,
    "year_max": <integer or null>,
    "min_area": <number or null>,
    "max_area": <number or null>
  },
  "filter_priority": [<string>, ...],
  "raw_query": <string>,
  "visual_description": <string>
}

Rules:
- If `probe_needed=true`: `probe_question` is a single short sentence in the user's language asking A-vs-B; `reply` is a one-line conversational acknowledgement of what you heard; `filters` contains any keys you can already infer from the query (may be mostly null); `filter_priority` lists the non-null filter keys ordered most-essential-to-least; `raw_query` is the first user message verbatim; `visual_description` is null or a short placeholder in English (it will be refined on turn 2).
- If `probe_needed=false`: `probe_question` is null; `reply` is a rich paraphrase in the form "이해했어요: [풍부한 문단]. 맞을까요?" (or English equivalent "Got it: [rich paragraph]. Sound right?"); `filters` has every inferable key; `filter_priority` reflects essentials; `raw_query` is the first user message verbatim; `visual_description` is a vivid 2-4 sentence English architectural description seeded from everything the user has said.

## Allowed `program` values (use exactly these strings)

Housing, Office, Museum, Education, Religion, Sports, Transport, Hospitality, Healthcare, Public, Mixed Use, Landscape, Infrastructure, Other

If you cannot map the user's program description to one of these, set `program: null` and let their words flow to `raw_query` / `visual_description` instead.

## Examples

USER: 제주도에 돌로 지은 명상 센터 찾고 있어요. 지역 재료 최대한 살려서.
ASSISTANT: {"probe_needed": false, "probe_question": null, "reply": "이해했어요: 제주 현지 돌과 재료를 충실히 사용한, 고요하고 장소 결합적인 명상 공간 — 제주 풍토에 뿌리박힌 비판적 지역주의 성향으로 읽어도 괜찮을까요?", "filters": {"location_country": "South Korea", "program": "Religion", "material": "stone", "style": "Vernacular", "year_min": null, "year_max": null, "min_area": null, "max_area": null}, "filter_priority": ["program", "material", "location_country", "style"], "raw_query": "제주도에 돌로 지은 명상 센터 찾고 있어요. 지역 재료 최대한 살려서.", "visual_description": "A contemplative meditation pavilion set into the volcanic landscape of Jeju Island, constructed from rough local basalt and dark volcanic stone laid in thick load-bearing walls. Compressed stereotomic masses with small punctured openings frame framed views of the sea and sky; the interior is shadowed, acoustically still, and intimately scaled. Exposed stone is the dominant material, with timber as a warm secondary note, in dialogue with Korean traditional hanok spatial ethics."}

USER: Warehouse-to-museum adaptive reuse in Rotterdam, keeping the existing brick shell with contemporary steel interventions.
ASSISTANT: {"probe_needed": false, "probe_question": null, "reply": "Got it: a museum project that preserves an existing warehouse's brick shell as the primary envelope, inserted with contemporary steel structural and circulation elements — an adaptive-reuse reading with revealed construction. Does that track?", "filters": {"location_country": "Netherlands", "program": "Museum", "material": "brick", "style": "Contemporary", "year_min": 1990, "year_max": null, "min_area": null, "max_area": null}, "filter_priority": ["program", "style", "location_country", "material"], "raw_query": "Warehouse-to-museum adaptive reuse in Rotterdam, keeping the existing brick shell with contemporary steel interventions.", "visual_description": "An adaptive-reuse museum in Rotterdam anchored by a retained industrial warehouse brick envelope, its exterior preserved with visible aged masonry and original window rhythms. Inside, contemporary steel mezzanines, bolted trusses, and exposed services cut through the original volume, producing a sharp juxtaposition between heavy masonry mass and tectonic steel frame. Concrete floors and white-painted brick host the gallery program; service systems are openly revealed as part of the architecture."}

USER: parametric 건축물인데 research pavilion이나 학교에 붙은 건 싫고. 실제로 지어진 거만.
ASSISTANT: {"probe_needed": false, "probe_question": null, "reply": "이해했어요: 파라메트릭 디자인 언어의 단일 오브제적, 실제 구축된 프로젝트들 — 리서치 파빌리온이나 학교 부속 시설은 제외. 이 방향으로 찾을게요. 맞을까요?", "filters": {"location_country": null, "program": null, "material": null, "style": "Parametric", "year_min": 2000, "year_max": null, "min_area": null, "max_area": null}, "filter_priority": ["style"], "raw_query": "parametric 건축물인데 research pavilion이나 학교에 붙은 건 싫고. 실제로 지어진 거만.", "visual_description": "A singular, free-form parametric building with continuous curvature and non-orthogonal geometry realised as an actual constructed work — not a research pavilion or speculative installation. The envelope flows as a sweeping surface; the interior space is fluid and expressive, with complex fabricated panels, tension-rich structural systems, and an avant-garde expressive language. The building reads as a standalone authored object, autonomous from its immediate context."}

USER: 새로 올릴 주택 프로젝트 참고용 찾아요.
ASSISTANT: {"probe_needed": true, "probe_question": "참고 방향성부터 좁혀볼게요: 목재·벽돌처럼 따뜻한 재료감 쪽이 끌리세요, 아니면 콘크리트·유리 같은 차가운 기하성 쪽이 끌리세요?", "reply": "주택 프로젝트 레퍼런스 찾는 거 확인했어요.", "filters": {"location_country": null, "program": "Housing", "material": null, "style": null, "year_min": null, "year_max": null, "min_area": null, "max_area": null}, "filter_priority": ["program"], "raw_query": "새로 올릴 주택 프로젝트 참고용 찾아요.", "visual_description": null}

USER: 새로 올릴 주택 프로젝트 참고용 찾아요.
ASSISTANT: {"probe_needed": true, "probe_question": "참고 방향성부터 좁혀볼게요: 목재·벽돌처럼 따뜻한 재료감 쪽이 끌리세요, 아니면 콘크리트·유리 같은 차가운 기하성 쪽이 끌리세요?", "reply": "주택 프로젝트 레퍼런스 찾는 거 확인했어요.", "filters": {"location_country": null, "program": "Housing", "material": null, "style": null, "year_min": null, "year_max": null, "min_area": null, "max_area": null}, "filter_priority": ["program"], "raw_query": "새로 올릴 주택 프로젝트 참고용 찾아요.", "visual_description": null}
USER: 따뜻한 재료 쪽이요. 목재 많이 쓴 거.
ASSISTANT: {"probe_needed": false, "probe_question": null, "reply": "이해했어요: 목재가 중심이 되는 따뜻한 물성의 주택 — 나무 질감이 실내외로 풍부하게 드러나고, 햇살과 조응하는 촉각적이고 정서적인 분위기. 이 방향으로 찾을게요.", "filters": {"location_country": null, "program": "Housing", "material": "timber", "style": null, "year_min": null, "year_max": null, "min_area": null, "max_area": null}, "filter_priority": ["program", "material"], "raw_query": "새로 올릴 주택 프로젝트 참고용 찾아요.", "visual_description": "A residential house led by warm natural materiality, with heavy use of exposed timber as the dominant architectural surface — structural beams, cladding, interior floors, and panelling in warm wood tones. The palette skews earthy, with brick, stone, or textured plaster as secondary materials; cool elements like metal and glass are minimal and used mainly as accents. Atmospheres are haptic, intimate, and domestic, with daylight filtered warmly across textured surfaces."}

USER: 서울 도심 오피스빌딩 찾아요.
ASSISTANT: {"probe_needed": true, "probe_question": "외피 쪽 방향 좁혀볼게요: 유리·금속 파사드의 차가운 기하성이 끌리세요, 아니면 벽돌·돌 같은 따뜻한 물성의 도심 오피스 쪽이 끌리세요?", "reply": "서울 도심 오피스빌딩, 확인했어요.", "filters": {"location_country": "South Korea", "program": "Office", "material": null, "style": null, "year_min": null, "year_max": null, "min_area": null, "max_area": null}, "filter_priority": ["program", "location_country"], "raw_query": "서울 도심 오피스빌딩 찾아요.", "visual_description": null}

USER: 서울 도심 오피스빌딩 찾아요.
ASSISTANT: {"probe_needed": true, "probe_question": "외피 쪽 방향 좁혀볼게요: 유리·금속 파사드의 차가운 기하성이 끌리세요, 아니면 벽돌·돌 같은 따뜻한 물성의 도심 오피스 쪽이 끌리세요?", "reply": "서울 도심 오피스빌딩, 확인했어요.", "filters": {"location_country": "South Korea", "program": "Office", "material": null, "style": null, "year_min": null, "year_max": null, "min_area": null, "max_area": null}, "filter_priority": ["program", "location_country"], "raw_query": "서울 도심 오피스빌딩 찾아요.", "visual_description": null}
USER: 물성은 상관없고 규모가 커야 돼요. 최소 20층 이상.
ASSISTANT: {"probe_needed": false, "probe_question": null, "reply": "이해했어요: 서울 도심의 대규모 오피스 타워 — 최소 20층 이상의 기념비적 스케일, 물성보다는 도시 존재감이 중심. 재료감이나 스타일은 폭넓게 탐색하는 방향으로 찾을게요.", "filters": {"location_country": "South Korea", "program": "Office", "material": null, "style": null, "year_min": null, "year_max": null, "min_area": 20000, "max_area": null}, "filter_priority": ["program", "location_country", "min_area"], "raw_query": "서울 도심 오피스빌딩 찾아요.", "visual_description": "A large-scale downtown office tower in Seoul's urban core, rising at least 20 stories as a monumental civic presence. The tower defines a street-wall and block figure in the dense metropolitan fabric; materiality spans a broad range from glass curtain wall and metal cladding to stone or concrete envelopes. The massing is vertical and commanding, with a significant floor-plate footprint and a strong silhouette in the skyline."}

USER: 좋은 레퍼런스 있으면 보여주세요.
ASSISTANT: {"probe_needed": true, "probe_question": "감 잡기 위해 먼저 여쭤볼게요: 작고 내밀한 공간이 끌리세요, 아니면 크고 개방감 있는 공간이 끌리세요?", "reply": "좋은 레퍼런스 보여드릴게요. 방향 잡는 것부터 도와주세요.", "filters": {"location_country": null, "program": null, "material": null, "style": null, "year_min": null, "year_max": null, "min_area": null, "max_area": null}, "filter_priority": [], "raw_query": "좋은 레퍼런스 있으면 보여주세요.", "visual_description": null}

USER: 좋은 레퍼런스 있으면 보여주세요.
ASSISTANT: {"probe_needed": true, "probe_question": "감 잡기 위해 먼저 여쭤볼게요: 작고 내밀한 공간이 끌리세요, 아니면 크고 개방감 있는 공간이 끌리세요?", "reply": "좋은 레퍼런스 보여드릴게요. 방향 잡는 것부터 도와주세요.", "filters": {"location_country": null, "program": null, "material": null, "style": null, "year_min": null, "year_max": null, "min_area": null, "max_area": null}, "filter_priority": [], "raw_query": "좋은 레퍼런스 있으면 보여주세요.", "visual_description": null}
USER: 개방감 있는 쪽.
ASSISTANT: {"probe_needed": true, "probe_question": "한 번만 더 여쭤볼게요: 직교적·격자형 공간이 끌리세요, 곡선적·흐르는 형태가 끌리세요?", "reply": "개방감 있는 쪽, 메모했어요.", "filters": {"location_country": null, "program": null, "material": null, "style": null, "year_min": null, "year_max": null, "min_area": null, "max_area": null}, "filter_priority": [], "raw_query": "좋은 레퍼런스 있으면 보여주세요.", "visual_description": null}

USER: 좋은 레퍼런스 있으면 보여주세요.
ASSISTANT: {"probe_needed": true, "probe_question": "감 잡기 위해 먼저 여쭤볼게요: 작고 내밀한 공간이 끌리세요, 아니면 크고 개방감 있는 공간이 끌리세요?", "reply": "좋은 레퍼런스 보여드릴게요. 방향 잡는 것부터 도와주세요.", "filters": {"location_country": null, "program": null, "material": null, "style": null, "year_min": null, "year_max": null, "min_area": null, "max_area": null}, "filter_priority": [], "raw_query": "좋은 레퍼런스 있으면 보여주세요.", "visual_description": null}
USER: 개방감 있는 쪽.
ASSISTANT: {"probe_needed": true, "probe_question": "한 번만 더 여쭤볼게요: 직교적·격자형 공간이 끌리세요, 곡선적·흐르는 형태가 끌리세요?", "reply": "개방감 있는 쪽, 메모했어요.", "filters": {"location_country": null, "program": null, "material": null, "style": null, "year_min": null, "year_max": null, "min_area": null, "max_area": null}, "filter_priority": [], "raw_query": "좋은 레퍼런스 있으면 보여주세요.", "visual_description": null}
USER: 직교적인 거.
ASSISTANT: {"probe_needed": false, "probe_question": null, "reply": "이해했어요: 개방감 있으면서도 직교적 격자에 충실한, 미스적·SANAA 계열의 투명한 단순성을 가진 건축들 — 경량감과 보편 공간의 감각이 중심. 이 방향으로 탐색해볼게요.", "filters": {"location_country": null, "program": null, "material": null, "style": "Modernist", "year_min": null, "year_max": null, "min_area": null, "max_area": null}, "filter_priority": ["style"], "raw_query": "좋은 레퍼런스 있으면 보여주세요.", "visual_description": "An expansive, open-plan architectural work with strict orthogonal geometry and a Miesian universal-space quality — thin columns, large glazed apertures, a flat planar roof, and minimal interior subdivision. Floors extend uninterrupted; the envelope is transparent, emphasising continuity between inside and outside. The material palette skews cool and precise (glass, polished concrete, thin steel, white surfaces), with refined reduction rather than rich warmth. Spaces feel weightless, airy, and phenomenologically transparent in the Rowe-Slutzky sense."}

USER: 그냥 멋진 거 보여줘.
ASSISTANT: {"probe_needed": true, "probe_question": "폭넓게 보여드릴게요. 감만 하나 여쭤볼게요 — 따뜻한 재료감이 끌리세요, 차가운 기하성이 끌리세요?", "reply": "멋진 레퍼런스 탐색 모드, 좋아요.", "filters": {"location_country": null, "program": null, "material": null, "style": null, "year_min": null, "year_max": null, "min_area": null, "max_area": null}, "filter_priority": [], "raw_query": "그냥 멋진 거 보여줘.", "visual_description": null}

USER: 그냥 멋진 거 보여줘.
ASSISTANT: {"probe_needed": true, "probe_question": "폭넓게 보여드릴게요. 감만 하나 여쭤볼게요 — 따뜻한 재료감이 끌리세요, 차가운 기하성이 끌리세요?", "reply": "멋진 레퍼런스 탐색 모드, 좋아요.", "filters": {"location_country": null, "program": null, "material": null, "style": null, "year_min": null, "year_max": null, "min_area": null, "max_area": null}, "filter_priority": [], "raw_query": "그냥 멋진 거 보여줘.", "visual_description": null}
USER: 둘 다 괜찮아. 그냥 좋은 거.
ASSISTANT: {"probe_needed": false, "probe_question": null, "reply": "알겠습니다: 제약 없이 다양하게, 퀄리티 높은 현대 건축을 폭넓게 보여드릴게요. 스와이프하면서 취향 잡아가면 됩니다.", "filters": {"location_country": null, "program": null, "material": null, "style": null, "year_min": 2000, "year_max": null, "min_area": null, "max_area": null}, "filter_priority": ["year_min"], "raw_query": "그냥 멋진 거 보여줘.", "visual_description": "A collection of high-quality, internationally recognised contemporary architectural works spanning a diverse range of programs, scales, styles, and materialities. These are refined, considered buildings with strong formal presence and design intelligence — including both warm material-led and cool geometry-led works, both site-specific and autonomous, across civic, residential, cultural, and commercial typologies."}

USER: Mixed-use 단지. 공공 공간이 1층에 넓게 있고 위는 주거랑 오피스 섞여 있는 거.
ASSISTANT: {"probe_needed": false, "probe_question": null, "reply": "이해했어요: 지상 공공 공간 위로 주거와 업무가 섞인 복합 단지 — 프로그램적 하이브리드가 명시적 의도인 도시형 개발 유형. 맞을까요?", "filters": {"location_country": null, "program": "Mixed Use", "material": null, "style": null, "year_min": null, "year_max": null, "min_area": null, "max_area": null}, "filter_priority": ["program"], "raw_query": "Mixed-use 단지. 공공 공간이 1층에 넓게 있고 위는 주거랑 오피스 섞여 있는 거.", "visual_description": "A multi-building mixed-use urban complex with an expansive, programmatically porous public ground plane that spans retail, lobby, and civic space. Above the ground level, residential and office functions stack and interleave — towers, slabs, or podium-plus-tower typologies hosting hybrid programs. The building defines new street fronts and plazas at ground level and maintains a legible urban-block presence at the top; the architecture embraces programmatic hybridity and civic porosity as explicit intent."}

USER: Koolhaas 스타일로 도서관 하나. OMA 초기 작업 느낌.
ASSISTANT: {"probe_needed": false, "probe_question": null, "reply": "이해했어요: 쿨하스·초기 OMA 계열의 도서관 — 프로그램 하이브리드가 강하고 자율적 오브제로 읽히는, 다방향 순환과 실험적 형태 언어의 공공 시설. 이 방향으로 찾아볼게요.", "filters": {"location_country": null, "program": "Public", "material": null, "style": "Avant-Garde", "year_min": 1990, "year_max": null, "min_area": null, "max_area": null}, "filter_priority": ["program", "style"], "raw_query": "Koolhaas 스타일로 도서관 하나. OMA 초기 작업 느낌.", "visual_description": "A library in the OMA/Rem Koolhaas-early-period tradition — a singular, autonomous architectural object whose form expresses programmatic hybridity and experimental spatial strategies. The building reads as a stacked, faceted, or wedge-shaped volume with sharp geometries, hovering masses, or a distinctively authored silhouette that reads as conceptual rather than contextual. Interior circulation favours omnidirectional spatial flat-plans over linear sequences; programmes like reading rooms, event spaces, and public lobbies are layered rather than zoned. Materiality tends toward cool industrial (metal mesh, glass, concrete) with unexpected colour accents."}
"""

# Labels used in few-shot examples that must exist in the architecture_vectors.style corpus.
# Used by pre-deploy gate test.
_CHAT_PHASE_FEW_SHOT_STYLE_LABELS = frozenset(['Vernacular', 'Contemporary', 'Parametric', 'Modernist', 'Avant-Garde'])

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


def embed_visual_description(text, session=None, user=None):
    """
    Topic 03 HyDE V_initial: embed `text` via HuggingFace Inference API.

    Model: paraphrase-multilingual-MiniLM-L12-v2 (384-dim).
    Uses stdlib urllib.request — no new dependencies.

    Returns list[float] of length 384 on success, None on any failure.
    Failures are always silent (logged + event emitted) and never raise.

    Flag guard is the caller's responsibility (hyde_vinitial_enabled).
    """
    hf_token = getattr(settings, 'HF_TOKEN', '')
    if not hf_token:
        event_log.emit_event(
            'failure',
            session=session,
            user=user,
            failure_type='hyde',
            recovery_path='no_hyde',
            reason='missing_token',
        )
        return None

    if not text or not text.strip():
        logger.debug('embed_visual_description: empty text, skipping HF call')
        return None

    rc = settings.RECOMMENDATION
    model = rc.get('hyde_hf_model', 'sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2')
    timeout = rc.get('hyde_hf_timeout_seconds', 5)
    url = f'https://api-inference.huggingface.co/models/{model}'

    payload = json.dumps({'inputs': text}).encode('utf-8')
    req = urllib.request.Request(
        url,
        data=payload,
        headers={
            'Authorization': f'Bearer {hf_token}',
            'Content-Type': 'application/json',
            'X-Wait-For-Model': 'true',
        },
        method='POST',
    )

    t0 = time.perf_counter()
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read()
        elapsed_ms = round((time.perf_counter() - t0) * 1000, 2)

        data = json.loads(raw)

        # Handle both 1-D [float*384] and 2-D (batched) [[float*384]] shapes
        if isinstance(data, list) and data and isinstance(data[0], list):
            vec = data[0]
        elif isinstance(data, list) and data and isinstance(data[0], (int, float)):
            vec = data
        else:
            logger.warning('embed_visual_description: unexpected HF response shape: %s', type(data))
            event_log.emit_event(
                'failure',
                session=session,
                user=user,
                failure_type='hyde',
                recovery_path='no_hyde',
                reason='unexpected_shape',
                elapsed_ms=elapsed_ms,
            )
            return None

        if len(vec) != 384:
            logger.warning('embed_visual_description: expected 384-dim, got %d', len(vec))
            event_log.emit_event(
                'failure',
                session=session,
                user=user,
                failure_type='hyde',
                recovery_path='no_hyde',
                reason=f'wrong_dim_{len(vec)}',
                elapsed_ms=elapsed_ms,
            )
            return None

        # Emit timing event on success
        event_log.emit_event(
            'hyde_call_timing',
            session=session,
            user=user,
            elapsed_ms=elapsed_ms,
            model=model,
        )
        return [float(v) for v in vec]

    except urllib.error.HTTPError as e:
        elapsed_ms = round((time.perf_counter() - t0) * 1000, 2)
        try:
            body = e.read().decode('utf-8', errors='replace')[:200]
        except Exception:
            body = ''
        logger.warning(
            'embed_visual_description: HF API returned HTTP %d',
            e.code,
        )
        event_log.emit_event(
            'failure',
            session=session,
            user=user,
            failure_type='hyde',
            recovery_path='no_v_initial',
            http_status=e.code,
            error_message=body,
            elapsed_ms=elapsed_ms,
        )
        return None
    except Exception as e:
        elapsed_ms = round((time.perf_counter() - t0) * 1000, 2)
        logger.warning(
            'embed_visual_description: HF call failed (%s: %s)',
            type(e).__name__, str(e),
        )
        event_log.emit_event(
            'failure',
            session=session,
            user=user,
            failure_type='hyde',
            recovery_path='no_hyde',
            error_class=type(e).__name__,
            error_message=str(e)[:200],
            elapsed_ms=elapsed_ms,
        )
        return None


def parse_query(conversation_history):
    """
    Chat phase Gemini call (Sprint 1 rewrite per Investigation 06).

    Input:
        conversation_history: list of {role: 'user'|'model', text: str} dicts,
            representing the full chat so far. Oldest turn first.
        Backward compat: if a bare string is passed (legacy caller), it is wrapped
            as [{'role': 'user', 'text': conversation_history}].

    Returns one of:

    Interim probe (probe_needed=True):
        {
            'probe_needed': True,
            'probe_question': str,      # verbal A-vs-B question in user's locale
            'reply': str,               # short ack in user's locale
            'filters': dict,            # partial filters inferred so far
            'filter_priority': list,
            'raw_query': str,           # first user turn verbatim
            'visual_description': None, # not yet finalised
        }

    Terminal response (probe_needed=False):
        {
            'probe_needed': False,
            'probe_question': None,
            'reply': str,               # rich paraphrase confirm in user's locale
            'filters': dict,            # all inferable SQL-WHERE predicates
            'filter_priority': list,    # ordered by essentialness
            'raw_query': str,           # first user turn verbatim
            'visual_description': str,  # English, 2-4 sentences, HyDE V_initial seed
        }

    Failure path (spec §5.4 graceful degradation):
        {
            'probe_needed': False,
            'probe_question': None,
            'reply': '이해를 잘 못 했어요. 일단 이 쪽으로 찾아볼게요.',
            'filters': {...all null},
            'filter_priority': [],
            'raw_query': <first user message verbatim>,
            'visual_description': None,
        }
        Also emits a 'failure' session event (spec §6).
    """
    # Backward compat: accept bare string (legacy callers pass query_text directly)
    if isinstance(conversation_history, str):
        conversation_history = [{'role': 'user', 'text': conversation_history}]

    # Extract first user message verbatim (BM25 raw_query channel)
    first_user_text = ''
    for turn in conversation_history:
        if turn.get('role') == 'user':
            first_user_text = turn.get('text', '')
            break

    _empty_filters = {
        'location_country': None, 'program': None, 'material': None, 'style': None,
        'year_min': None, 'year_max': None, 'min_area': None, 'max_area': None,
    }
    _fallback = {
        'probe_needed': False,
        'probe_question': None,
        'reply': '이해를 잘 못 했어요. 일단 이 쪽으로 찾아볼게요.',
        'filters': dict(_empty_filters),
        'filter_priority': [],
        'raw_query': first_user_text,
        'visual_description': None,
    }

    try:
        client = _get_client()
        rc = settings.RECOMMENDATION

        # Build Gemini contents list from conversation_history
        contents = []
        for turn in conversation_history:
            role = turn.get('role', 'user')
            text = turn.get('text', '')
            contents.append(
                types.Content(role=role, parts=[types.Part.from_text(text=text)])
            )

        # IMP-5: explicit context caching branch (flag-gated, default OFF)
        caching_enabled = rc.get('context_caching_enabled', False)
        cache_resource_name = None
        if caching_enabled:
            cache_resource_name = _ensure_chat_cache(client)

        if cache_resource_name:
            # Cached path: supply cached_content= instead of system_instruction=
            def _call():
                return client.models.generate_content(
                    model='gemini-2.5-flash',
                    contents=contents,
                    config=types.GenerateContentConfig(
                        cached_content=cache_resource_name,
                        response_mime_type='application/json',
                        temperature=0.2,
                        thinking_config=types.ThinkingConfig(thinking_budget=0),
                    ),
                )
        else:
            # Uncached path: original behaviour, backward-compatible
            def _call():  # noqa: F811
                return client.models.generate_content(
                    model='gemini-2.5-flash',
                    contents=contents,
                    config=types.GenerateContentConfig(
                        system_instruction=_CHAT_PHASE_SYSTEM_PROMPT,
                        response_mime_type='application/json',
                        temperature=0.2,
                        thinking_config=types.ThinkingConfig(thinking_budget=0),
                    ),
                )

        t_call_start = time.perf_counter()
        try:
            response = _retry_gemini_call(_call)
        except Exception as _cache_exc:
            # IMP-5: if call failed with 404/NOT_FOUND it means the Gemini cache
            # has expired but the Django cache entry is still live (TTL skew).
            # Evict Django entry, clear cache_resource_name, and retry uncached.
            exc_str = str(_cache_exc)
            if cache_resource_name and ('404' in exc_str or 'NOT_FOUND' in exc_str):
                logger.warning(
                    'IMP-5: Gemini cache 404 for %s -- evicting Django entry and retrying uncached',
                    cache_resource_name,
                )
                django_cache.delete(_get_django_cache_key())
                cache_resource_name = None

                def _call_uncached():
                    return client.models.generate_content(
                        model='gemini-2.5-flash',
                        contents=contents,
                        config=types.GenerateContentConfig(
                            system_instruction=_CHAT_PHASE_SYSTEM_PROMPT,
                            response_mime_type='application/json',
                            temperature=0.2,
                            thinking_config=types.ThinkingConfig(thinking_budget=0),
                        ),
                    )
                response = _retry_gemini_call(_call_uncached)
            else:
                raise
        t_call_end = time.perf_counter()

        # Emit parse_query.timing event (spec §6 + §11.1 IMP-4 mandatory companion).
        # Must be emitted before json.loads so parse failures still produce a timing record.
        # IMP-5: extend with 4 new fields (additive -- existing field names unchanged).
        _usage = getattr(response, 'usage_metadata', None)
        _raw_cached = getattr(_usage, 'cached_content_token_count', None) if _usage else None
        # Guard: only accept int/float to avoid MagicMock or other non-serialisable types
        _cached_token_count = int(_raw_cached) if isinstance(_raw_cached, (int, float)) else None
        _cache_hit = (_cached_token_count > 0) if _cached_token_count is not None else None
        event_log.emit_event(
            'parse_query_timing',
            session=None,
            user=None,
            gemini_total_ms=round((t_call_end - t_call_start) * 1000, 2),
            ttft_ms=None,   # not available without streaming
            gen_ms=round((t_call_end - t_call_start) * 1000, 2),
            input_tokens=getattr(_usage, 'prompt_token_count', None) if _usage else None,
            output_tokens=getattr(_usage, 'candidates_token_count', None) if _usage else None,
            thinking_tokens=getattr(_usage, 'thoughts_token_count', None) if _usage else None,
            # IMP-5 fields (additive)
            cache_hit=_cache_hit,
            cached_input_tokens=_cached_token_count,
            cache_name_hash=_get_prompt_hash() if cache_resource_name else None,
            caching_mode='explicit' if cache_resource_name else 'none',
        )

        data = json.loads(response.text)

        probe_needed = bool(data.get('probe_needed', False))

        # Sanitize program value (case-insensitive -> canonical form)
        filters = data.get('filters') or dict(_empty_filters)
        if filters.get('program'):
            program = filters['program']
            if program not in PROGRAM_VALUES:
                titled = program.title()
                filters['program'] = titled if titled in PROGRAM_VALUES else None

        # Sanitize filter_priority: keep only non-null filter keys
        raw_priority = data.get('filter_priority') or []
        filter_priority = [k for k in raw_priority if filters.get(k) is not None]

        # raw_query: spec §3 says always verbatim first user message
        raw_query = data.get('raw_query') or first_user_text

        result = {
            'probe_needed': probe_needed,
            'probe_question': data.get('probe_question') if probe_needed else None,
            'reply': data.get('reply', ''),
            'filters': filters,
            'filter_priority': filter_priority,
            'raw_query': raw_query,
            'visual_description': data.get('visual_description'),
        }
        return result

    except json.JSONDecodeError as e:
        logger.error('parse_query JSON decode error: %s', e)
        event_log.emit_event(
            'failure',
            session=None,
            user=None,
            failure_type='gemini_parse',
            recovery_path='fallback_diverse_random',
            error_class='JSONDecodeError',
            error_message=str(e)[:200],
        )
        return _fallback
    except Exception as e:
        logger.error('parse_query failed after retries: %s: %s', type(e).__name__, e)
        event_log.emit_event(
            'failure',
            session=None,
            user=None,
            failure_type='gemini_parse',
            recovery_path='fallback_diverse_random',
            error_class=type(e).__name__,
            error_message=str(e)[:200],
        )
        return _fallback


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
                    thinking_config=types.ThinkingConfig(thinking_budget=0),
                ),
            )

        response = _retry_gemini_call(_call)
        return json.loads(response.text)
    except json.JSONDecodeError as e:
        logger.error('generate_persona_report JSON decode error: %s', e)
        event_log.emit_event(
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
        event_log.emit_event(
            'failure',
            session=None,
            user=None,
            failure_type='gemini_parse',
            recovery_path='none',
            error_class=type(e).__name__,
            error_message=str(e)[:200],
        )
        raise RuntimeError(f'Persona report generation failed: {type(e).__name__}. Please try again later.')


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
        with connection.cursor() as cur:
            cur.execute(
                f'SELECT building_id, name_en, style, atmosphere, material '
                f'FROM architecture_vectors WHERE building_id IN ({placeholders})',
                building_ids,
            )
            rows = _dictfetchall(cur)
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
        client = _get_client()

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

        response = _retry_gemini_call(_call)
        raw_text = response.text

    except Exception as e:
        logger.warning(
            'rerank_candidates Gemini call failed (exception): %s: %s',
            type(e).__name__, str(e),
        )
        event_log.emit_event(
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
    input_id_set = set(input_ids)

    # Step 1: JSON parse
    try:
        obj = json.loads(raw_text)
    except (json.JSONDecodeError, ValueError) as e:
        logger.warning(
            'rerank_candidates validation failed [parse_fail]: %s', e,
        )
        event_log.emit_event(
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
        event_log.emit_event(
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
        event_log.emit_event(
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
        event_log.emit_event(
            'failure',
            session=None,
            user=None,
            failure_type='gemini_rerank',
            recovery_path='cosine_fallback',
            rerank_status=tag,
        )
        return list(input_ids)

    return ranking


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
