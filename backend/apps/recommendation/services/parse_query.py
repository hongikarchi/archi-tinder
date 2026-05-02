"""
parse_query.py -- Query parsing via Gemini chat phase.

Sprint 1 rewrite (Investigation 06): chat-phase + stage-decoupled (IMP-6).
M4 (Investigation 22): query complexity heuristic classifier + telemetry.

Cross-module symbol access uses the late-bound package reference (_svc) so that
mock.patch('apps.recommendation.services.X') continues to work in tests.
"""
import json
import logging
import re as _re
import time

from django.conf import settings
from django.core.cache import cache as django_cache
from google.genai import types

logger = logging.getLogger('apps.recommendation')

# ---------------------------------------------------------------------------
# Public constant: PROGRAM_VALUES
# Used by views and tests directly. Must be accessible at import time.
# ---------------------------------------------------------------------------
PROGRAM_VALUES = [
    'Housing', 'Office', 'Museum', 'Education', 'Religion', 'Sports',
    'Transport', 'Hospitality', 'Healthcare', 'Public', 'Mixed Use',
    'Landscape', 'Infrastructure', 'Other',
]

# ---------------------------------------------------------------------------
# Large prompt constants (module-level so _CHAT_PHASE_SYSTEM_PROMPT can be
# imported directly and hashed by _caches._get_prompt_hash at call time).
# ---------------------------------------------------------------------------
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

**HARD CAP: Maximum 2 clarification turns per session.**
- If the conversation history shows 3 or more user messages (the user has already answered 2 clarifying questions), you MUST set `probe_needed=false` and return terminal output immediately with whatever filters can be extracted from the accumulated conversation.
- This rule overrides ALL other heuristics. Even if the conversation is still ambiguous after 2 probe turns, do NOT ask a 3rd clarifying question — use best-effort filters from everything said so far, or return broad defaults.
- Rationale: cumulative user fatigue + pre-registered design intent (Investigation 06). The 2-turn budget is already generous; a 3rd probe turn is always a UX regression.

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

# ---------------------------------------------------------------------------
# M4 (Investigation 22 §M4): Query complexity heuristic classifier
# ---------------------------------------------------------------------------
_STYLE_TOKENS = frozenset([
    # English style labels (from few-shot + corpus)
    'brutalist', 'brutalism', 'contemporary', 'modernist', 'modernism', 'modern',
    'vernacular', 'parametric', 'avant-garde', 'avantgarde', 'minimalist', 'minimalism',
    'classical', 'baroque', 'gothic', 'deconstructivist', 'deconstructivism',
    'high-tech', 'critical regionalist', 'regionalist', 'industrial',
    # Korean style tokens
    '브루탈리스트', '브루탈리즘', '미니멀', '파라메트릭', '현대', '근대', '전통',
])

_PROGRAM_TOKENS = frozenset([
    # English program labels (PROGRAM_VALUES lowercased + aliases)
    'housing', 'office', 'museum', 'education', 'school', 'university', 'library',
    'religion', 'chapel', 'church', 'mosque', 'temple', 'sports', 'stadium',
    'transport', 'station', 'airport', 'hospitality', 'hotel', 'resort',
    'healthcare', 'hospital', 'clinic', 'public', 'civic', 'mixed use', 'landscape',
    'infrastructure', 'pavilion', 'gallery',
    # Korean program tokens
    '주택', '오피스', '미술관', '박물관', '학교', '도서관', '교회', '사원',
    '공공', '호텔', '병원', '역사', '공항', '스타디움', '갤러리',
])

_MATERIAL_TOKENS = frozenset([
    # English material tokens
    'concrete', 'timber', 'brick', 'stone', 'glass', 'steel', 'wood', 'metal',
    'copper', 'ceramic', 'bamboo', 'rammed earth', 'basalt', 'marble', 'zinc',
    'aluminum', 'aluminium',
    # Korean material tokens
    '콘크리트', '목재', '벽돌', '돌', '유리', '철', '금속', '구리',
])

# Architectural adjective / atmosphere tokens (adds 1 specificity signal)
_ADJECTIVE_TOKENS = frozenset([
    'minimalist', 'monumental', 'transparent', 'tectonic', 'stereotomic',
    'tactile', 'contemplative', 'fluid', 'orthogonal', 'curvilinear',
    'austere', 'raw', 'heavy', 'light', 'earthy',
])

_ALL_SPECIFICITY_TOKENS = _STYLE_TOKENS | _PROGRAM_TOKENS | _MATERIAL_TOKENS | _ADJECTIVE_TOKENS

# ---------------------------------------------------------------------------
# IMP-6 Commit 2: Stage 1 response schema (excludes visual_description)
# ---------------------------------------------------------------------------
_STAGE1_RESPONSE_SCHEMA = {
    'type': 'object',
    'properties': {
        'probe_needed': {'type': 'boolean'},
        'probe_question': {'type': 'string'},
        'reply': {'type': 'string'},
        'filters': {
            'type': 'object',
            'properties': {
                'location_country': {'type': 'string'},
                'program': {'type': 'string'},
                'material': {'type': 'string'},
                'style': {'type': 'string'},
                'year_min': {'type': 'integer'},
                'year_max': {'type': 'integer'},
                'min_area': {'type': 'number'},
                'max_area': {'type': 'number'},
            },
        },
        'filter_priority': {'type': 'array', 'items': {'type': 'string'}},
        'raw_query': {'type': 'string'},
    },
    'required': ['probe_needed', 'reply'],
}


def _classify_query_complexity(text: str) -> str:
    """
    M4 heuristic: classify a query string into one of four complexity classes.

    Returns:
        'brutalist'  -- >=3 specific architectural entities detected
        'narrow'     -- 1-2 specific entities (some signal but not fully determined)
        'barequery'  -- 0 specific entities (vague / generic)
        'unknown'    -- empty/None input or heuristic cannot decide

    Accuracy target: ~80% -- good enough for stratified analytics (Investigation 22
    Phase 1 Brutalist-vs-BareQuery cohort split). Not a hard classifier.

    Implementation: splits on whitespace + common delimiters; checks against
    pre-compiled vocabulary sets (style, program, material, adjective). Korean
    tokens included for bilingual corpus coverage.
    """
    if not text or not isinstance(text, str):
        return 'unknown'

    lowered = text.lower()

    # Tokenise: split on whitespace and common punctuation
    tokens = set(_re.split(r'[\s,·.!?;:\-/]+', lowered))
    tokens.discard('')

    # Count hits across all specificity token sets
    hits = sum(1 for tok in tokens if tok in _ALL_SPECIFICITY_TOKENS)

    # Also check for multi-word tokens (e.g., 'mixed use', 'rammed earth', 'critical regionalist')
    for multi_tok in ('mixed use', 'rammed earth', 'critical regionalist'):
        if multi_tok in lowered:
            hits += 1

    if hits >= 3:
        return 'brutalist'
    elif hits >= 1:
        return 'narrow'
    elif not tokens or len(tokens) <= 3:
        return 'barequery'
    else:
        return 'barequery'


def parse_query(conversation_history):
    """
    Chat phase Gemini call (Sprint 1 rewrite per Investigation 06).

    IMP-6 Commit 2: when stage_decouple_enabled=True, routes to parse_query_stage1()
    which omits visual_description (Stage 2 generates it async). When flag is OFF,
    runs the original single-call full-output path.

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
                                        # (None when stage_decouple_enabled=True -- Stage 2)
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
    # Late-bound package reference for cross-module symbol access.
    # mock.patch('apps.recommendation.services.X') modifies this module object;
    # _svc.X reads from it at call time -- patches are visible here.
    from apps.recommendation import services as _svc  # noqa: PLC0415

    # IMP-6: when stage_decouple_enabled=True, delegate to Stage 1 (visual_description
    # is generated asynchronously by Stage 2 thread spawned in ParseQueryView).
    # Use _svc.parse_query_stage1 so mock.patch/patch.object on services.parse_query_stage1
    # is visible here at call time (late-bound via the module object).
    if settings.RECOMMENDATION.get('stage_decouple_enabled', False):
        return _svc.parse_query_stage1(conversation_history)
    # else: fall through to the original single-call path (default, backward compat)
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
        client = _svc._get_client()
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
            cache_resource_name = _svc._ensure_chat_cache(client)

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
            response = _svc._retry_gemini_call(_call)
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
                django_cache.delete(_svc._get_django_cache_key())
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
                response = _svc._retry_gemini_call(_call_uncached)
            else:
                raise
        t_call_end = time.perf_counter()

        # Emit parse_query.timing event (spec §6 + §11.1 IMP-4 mandatory companion).
        # Must be emitted before json.loads so parse failures still produce a timing record.
        # IMP-5: extend with 4 new fields (additive -- existing field names unchanged).
        # M4 (Investigation 22): pre-parse probe_needed to populate clarification_fired
        #     without changing the "timing always emits when Gemini responds" invariant.
        #     Pre-parse is best-effort: on decode failure it defaults to None.
        _usage = getattr(response, 'usage_metadata', None)
        _raw_cached = getattr(_usage, 'cached_content_token_count', None) if _usage else None
        # Guard: only accept int/float to avoid MagicMock or other non-serialisable types
        _cached_token_count = int(_raw_cached) if isinstance(_raw_cached, (int, float)) else None
        _cache_hit = (_cached_token_count > 0) if _cached_token_count is not None else None

        # M4: best-effort pre-parse for clarification_fired (does NOT replace the
        # main json.loads below -- that one raises and is caught by the outer except).
        _clarification_fired = None  # None = unknown (Gemini error or pre-parse failure)
        try:
            _pre_data = json.loads(response.text)
            _clarification_fired = bool(_pre_data.get('probe_needed', False))
        except Exception:
            pass  # main json.loads below will surface the error via the except handler

        # M4: classify the user's query text for stratified analytics
        _query_complexity_class = _classify_query_complexity(first_user_text)

        # M1 (Investigation 22 §M1 refined): compute user-turn count for cap telemetry.
        # Cap fires when user_turn_count >= 3 AND Gemini returned probe_needed=True.
        # Bare-string callers are wrapped to a 1-element list above, so count is always 1
        # there and the cap never fires -- backward compat is automatic.
        _user_turn_count = sum(1 for t in conversation_history if t.get('role') == 'user')
        _m1_cap_forced_terminal = bool(
            _user_turn_count >= 3 and _clarification_fired is True
        )

        _svc.event_log.emit_event(
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
            cache_name_hash=_svc._get_prompt_hash() if cache_resource_name else None,
            caching_mode='explicit' if cache_resource_name else 'none',
            # M4 fields (additive, Investigation 22 §M4 + IMP-10 sub-task A continuation)
            clarification_fired=_clarification_fired,
            query_complexity_class=_query_complexity_class,
            # M1 field (Investigation 22 §M1 refined): True iff Python-level cap overrode
            # Gemini's probe_needed=True on user turn 3+. Observable cap-fire-rate metric.
            m1_cap_forced_terminal=_m1_cap_forced_terminal,
        )

        data = json.loads(response.text)

        probe_needed = bool(data.get('probe_needed', False))

        # M1 (Investigation 22 §M1 refined): Python-level runaway-clarification cap.
        # If user_turn_count >= 3 AND Gemini still returned probe_needed=True, force
        # terminal mode. This is defense-in-depth: the prompt HARD CAP clause should
        # prevent Gemini from firing a 3rd probe, but Python enforces it regardless.
        # Cap fires ONLY at turn 3+ -- turns 1 and 2 are legitimate 0/1-turn flows per
        # Investigation 06's design intent. Always-on; no flag gate.
        if _user_turn_count >= 3 and probe_needed:
            logger.warning(
                'parse_query: Gemini returned probe_needed=True on user turn %d (>=3); '
                'forcing probe_needed=False per Investigation 22 M1 cap',
                _user_turn_count,
            )
            probe_needed = False

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
        _svc.event_log.emit_event(
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
        _svc.event_log.emit_event(
            'failure',
            session=None,
            user=None,
            failure_type='gemini_parse',
            recovery_path='fallback_diverse_random',
            error_class=type(e).__name__,
            error_message=str(e)[:200],
        )
        return _fallback


def parse_query_stage1(conversation_history):
    """IMP-6 Commit 2: Stage 1 Gemini call -- USER-BLOCKING portion of the split.

    Same as parse_query() but uses response_schema to exclude visual_description,
    reducing output tokens from ~290-400 to ~150-220. Returns same dict shape as
    parse_query() but with visual_description=None always.

    When stage_decouple_enabled=False, this function is not called directly;
    parse_query() (the legacy wrapper) handles routing.

    Emits parse_query_timing with stage='1' field added (additive -- all existing
    fields preserved per spec v1.7).

    Args:
        conversation_history: list of {role, text} dicts or bare string (backward compat).

    Returns:
        Same dict shape as parse_query(), with visual_description always None.
        On failure: graceful degradation fallback dict (same as parse_query).
    """
    # Late-bound package reference (same rationale as parse_query above)
    from apps.recommendation import services as _svc  # noqa: PLC0415

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
        client = _svc._get_client()
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
            cache_resource_name = _svc._ensure_chat_cache(client)

        if cache_resource_name:
            # Cached path: supply cached_content= instead of system_instruction=
            # response_schema excludes visual_description -> reduced output tokens
            def _call():
                return client.models.generate_content(
                    model='gemini-2.5-flash',
                    contents=contents,
                    config=types.GenerateContentConfig(
                        cached_content=cache_resource_name,
                        response_mime_type='application/json',
                        response_schema=_STAGE1_RESPONSE_SCHEMA,
                        temperature=0.2,
                        thinking_config=types.ThinkingConfig(thinking_budget=0),
                    ),
                )
        else:
            # Uncached path: original system_instruction + Stage 1 schema
            def _call():  # noqa: F811
                return client.models.generate_content(
                    model='gemini-2.5-flash',
                    contents=contents,
                    config=types.GenerateContentConfig(
                        system_instruction=_CHAT_PHASE_SYSTEM_PROMPT,
                        response_mime_type='application/json',
                        response_schema=_STAGE1_RESPONSE_SCHEMA,
                        temperature=0.2,
                        thinking_config=types.ThinkingConfig(thinking_budget=0),
                    ),
                )

        t_call_start = time.perf_counter()
        try:
            response = _svc._retry_gemini_call(_call)
        except Exception as _cache_exc:
            # IMP-5: if call failed with 404/NOT_FOUND (Gemini cache expired but Django
            # cache still live), evict Django entry and retry uncached.
            exc_str = str(_cache_exc)
            if cache_resource_name and ('404' in exc_str or 'NOT_FOUND' in exc_str):
                logger.warning(
                    'IMP-5: Gemini cache 404 for %s -- evicting Django entry and retrying uncached',
                    cache_resource_name,
                )
                django_cache.delete(_svc._get_django_cache_key())
                cache_resource_name = None

                def _call_uncached():
                    return client.models.generate_content(
                        model='gemini-2.5-flash',
                        contents=contents,
                        config=types.GenerateContentConfig(
                            system_instruction=_CHAT_PHASE_SYSTEM_PROMPT,
                            response_mime_type='application/json',
                            response_schema=_STAGE1_RESPONSE_SCHEMA,
                            temperature=0.2,
                            thinking_config=types.ThinkingConfig(thinking_budget=0),
                        ),
                    )
                response = _svc._retry_gemini_call(_call_uncached)
            else:
                raise
        t_call_end = time.perf_counter()

        # --- Telemetry (same as parse_query, additive stage='1' field per spec v1.7) ---
        _usage = getattr(response, 'usage_metadata', None)
        _raw_cached = getattr(_usage, 'cached_content_token_count', None) if _usage else None
        _cached_token_count = int(_raw_cached) if isinstance(_raw_cached, (int, float)) else None
        _cache_hit = (_cached_token_count > 0) if _cached_token_count is not None else None

        _clarification_fired = None
        try:
            _pre_data = json.loads(response.text)
            _clarification_fired = bool(_pre_data.get('probe_needed', False))
        except Exception:
            pass

        _query_complexity_class = _classify_query_complexity(first_user_text)
        _user_turn_count = sum(1 for t in conversation_history if t.get('role') == 'user')
        _m1_cap_forced_terminal = bool(_user_turn_count >= 3 and _clarification_fired is True)

        _svc.event_log.emit_event(
            'parse_query_timing',
            session=None,
            user=None,
            gemini_total_ms=round((t_call_end - t_call_start) * 1000, 2),
            ttft_ms=None,
            gen_ms=round((t_call_end - t_call_start) * 1000, 2),
            input_tokens=getattr(_usage, 'prompt_token_count', None) if _usage else None,
            output_tokens=getattr(_usage, 'candidates_token_count', None) if _usage else None,
            thinking_tokens=getattr(_usage, 'thoughts_token_count', None) if _usage else None,
            # IMP-5 fields
            cache_hit=_cache_hit,
            cached_input_tokens=_cached_token_count,
            cache_name_hash=_svc._get_prompt_hash() if cache_resource_name else None,
            caching_mode='explicit' if cache_resource_name else 'none',
            # M4 fields
            clarification_fired=_clarification_fired,
            query_complexity_class=_query_complexity_class,
            # M1 field
            m1_cap_forced_terminal=_m1_cap_forced_terminal,
            # IMP-6 Commit 2 additive field: stage identifier
            stage='1',
        )

        data = json.loads(response.text)
        probe_needed = bool(data.get('probe_needed', False))

        # M1 cap: Python-level runaway-clarification guard (same as parse_query)
        if _user_turn_count >= 3 and probe_needed:
            logger.warning(
                'parse_query_stage1: Gemini returned probe_needed=True on user turn %d (>=3); '
                'forcing probe_needed=False per Investigation 22 M1 cap',
                _user_turn_count,
            )
            probe_needed = False

        # Sanitize program value
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

        return {
            'probe_needed': probe_needed,
            'probe_question': data.get('probe_question') if probe_needed else None,
            'reply': data.get('reply', ''),
            'filters': filters,
            'filter_priority': filter_priority,
            'raw_query': raw_query,
            'visual_description': None,  # Stage 2 generates this asynchronously
        }

    except json.JSONDecodeError as e:
        logger.error('parse_query_stage1 JSON decode error: %s', e)
        _svc.event_log.emit_event(
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
        logger.error('parse_query_stage1 failed after retries: %s: %s', type(e).__name__, e)
        _svc.event_log.emit_event(
            'failure',
            session=None,
            user=None,
            failure_type='gemini_parse',
            recovery_path='fallback_diverse_random',
            error_class=type(e).__name__,
            error_message=str(e)[:200],
        )
        return _fallback
