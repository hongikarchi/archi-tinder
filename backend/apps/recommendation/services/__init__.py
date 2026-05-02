"""
services/ package -- Gemini LLM integration for ArchiTinder recommendation.

This __init__.py re-exports all public AND private names from sub-modules so that:
  - from apps.recommendation.services import X  (direct import)
  - from apps.recommendation import services; services.X  (attribute access)
  - mock.patch('apps.recommendation.services.X', ...)  (patch by string path)
all continue to work exactly as they did against the monolithic services.py.

Sub-modules use `from apps.recommendation import services as _svc` and access
cross-module symbols via `_svc.X` at call time (late-bound), so mock.patch
modifications to this module object are visible to all sub-module functions.

Import order matters: _gemini has no sibling deps, so load first; _caches
lazily accesses _CHAT_PHASE_SYSTEM_PROMPT via _svc so ordering is safe.
"""

# ---------------------------------------------------------------------------
# External module attributes that tests patch via services.X
# ---------------------------------------------------------------------------
# These are imported as module-level names so mock.patch('...services.X') works.
# Sub-modules access them via _svc.X (late-bound) so patches reach them.

import urllib.request  # noqa: F401  -- test_hyde patches services.urllib.request.urlopen
import urllib  # noqa: F401  -- needed so services.urllib attribute exists for patch resolution

from django.db import connection  # noqa: F401  -- patched in test_topic02, test_chat_phase

# event_log is accessed as a module (tests patch services.event_log and
# services.event_log.emit_event), so import the module object directly.
from .. import event_log  # noqa: F401  -- patched in test_hyde, test_topic02, etc.

# _dictfetchall is called internally by generation.py and rerank.py via _svc._dictfetchall
from ..engine import _dictfetchall  # noqa: F401

# ---------------------------------------------------------------------------
# _gemini: low-level Gemini client + retry (no sibling deps)
# ---------------------------------------------------------------------------
from ._gemini import _get_client, _retry_gemini_call  # noqa: F401
from ._gemini import _GEMINI_MAX_RETRIES, _GEMINI_RETRY_DELAY  # noqa: F401

# ---------------------------------------------------------------------------
# _caches: IMP-5 chat cache + IMP-6 V_initial cache
# ---------------------------------------------------------------------------
from ._caches import (  # noqa: F401
    _get_prompt_hash,
    _get_cache_name,
    _get_django_cache_key,
    _ensure_chat_cache,
    _v_initial_cache_key,
    get_cached_v_initial,
    set_cached_v_initial,
)

# ---------------------------------------------------------------------------
# parse_query: query parsing + constants
# ---------------------------------------------------------------------------
from .parse_query import (  # noqa: F401
    PROGRAM_VALUES,
    _CHAT_PHASE_SYSTEM_PROMPT,
    _CHAT_PHASE_FEW_SHOT_STYLE_LABELS,
    _STAGE1_RESPONSE_SCHEMA,
    _STYLE_TOKENS,
    _PROGRAM_TOKENS,
    _MATERIAL_TOKENS,
    _ADJECTIVE_TOKENS,
    _ALL_SPECIFICITY_TOKENS,
    _classify_query_complexity,
    parse_query,
    parse_query_stage1,
)

# ---------------------------------------------------------------------------
# embeddings: HF embedding for HyDE V_initial
# ---------------------------------------------------------------------------
from .embeddings import embed_visual_description  # noqa: F401

# ---------------------------------------------------------------------------
# generation: Stage 2 visual description + persona report + persona image
# ---------------------------------------------------------------------------
from .generation import (  # noqa: F401
    _PERSONA_PROMPT,
    generate_visual_description,
    generate_persona_report,
    generate_persona_image,
)

# ---------------------------------------------------------------------------
# rerank: Topic 02 Gemini setwise rerank
# ---------------------------------------------------------------------------
from .rerank import (  # noqa: F401
    _RERANK_SYSTEM_PROMPT,
    _liked_summary_for_rerank,
    rerank_candidates,
    _validate_rerank_response,
)

# ---------------------------------------------------------------------------
# __all__: public API surface (private names excluded)
# ---------------------------------------------------------------------------
__all__ = [
    # External module objects
    'connection',
    'event_log',
    # Public functions + constants
    'PROGRAM_VALUES',
    'get_cached_v_initial',
    'set_cached_v_initial',
    'embed_visual_description',
    'parse_query',
    'parse_query_stage1',
    'generate_visual_description',
    'generate_persona_report',
    'generate_persona_image',
    'rerank_candidates',
]
