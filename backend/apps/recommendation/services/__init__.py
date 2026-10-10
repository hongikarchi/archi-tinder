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

Import order matters: _gemini has no sibling deps, so load first.
"""

# ---------------------------------------------------------------------------
# External module attributes that tests patch via services.X
# ---------------------------------------------------------------------------
# These are imported as module-level names so mock.patch('...services.X') works.
# Sub-modules access them via _svc.X (late-bound) so patches reach them.

import urllib.request  # noqa: F401  -- test_hyde patches services.urllib.request.urlopen
import urllib  # noqa: F401  -- needed so services.urllib attribute exists for patch resolution

from django.db import connections as _connections

# event_log is accessed as a module (tests patch services.event_log and
# services.event_log.emit_event), so import the module object directly.
from .. import event_log  # noqa: F401  -- patched in test_hyde, test_topic02, etc.

# _dictfetchall is called internally by generation.py and rerank.py via _svc._dictfetchall
from ..engine import _dictfetchall  # noqa: F401

# ---------------------------------------------------------------------------
# _gemini: low-level Gemini client + retry (no sibling deps)
# ---------------------------------------------------------------------------
from ._gemini import _get_client, _retry_gemini_call  # noqa: F401
from ._gemini import generate_content_with_fallback, _is_model_unavailable  # noqa: F401
from ._gemini import _GEMINI_MAX_RETRIES, _GEMINI_RETRY_DELAY  # noqa: F401
# BACK-LLM-PROVIDER-1: always-Gemini client for the image path (generation.py
# _gen_native) -- must stay accessible via the _svc facade for late-binding.
from ._gemini import _get_gemini_client  # noqa: F401
# BACK-LLM-PROVIDER-2: always-OpenAI client for the image path (generation.py
# _gen_native) when settings.LLM_IMAGE_PROVIDER='openai' -- same late-binding
# facade requirement as _get_gemini_client above.
from ._gemini import _get_openai_client  # noqa: F401

# ---------------------------------------------------------------------------
# vocab: BACK-PARSER-VOCAB-1 -- live DB vocabulary for the 5 grounded axes
# ---------------------------------------------------------------------------
from .vocab import get_axis_vocab, _VOCAB_SNAPSHOT  # noqa: F401

# ---------------------------------------------------------------------------
# embeddings: HF embedding for HyDE V_initial
# ---------------------------------------------------------------------------
from .embeddings import embed_visual_description  # noqa: F401

# ---------------------------------------------------------------------------
# generation: persona report + persona image + board name
# ---------------------------------------------------------------------------
from .generation import (  # noqa: F401
    _NAME_FILTER_PRIORITY,
    _sanitise_board_name,
    _deterministic_board_name,
    _dedup_board_name,
    _gemini_board_name_raw,
    generate_persona_report,
    generate_persona_image,
    build_image_report_from_facts,
    generate_taste_board_name,
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
# connection: thread-local-safe proxy for connections['buildings'].
# Must be defined AFTER all imports so no E402 is triggered for imports above.
# Tests patch via mock.patch('apps.recommendation.services.connection', X).
# ---------------------------------------------------------------------------


class _BuildingsConnectionProxy:
    """Route attribute access to connections['buildings'] at call time.

    Mirrors django.db.DefaultConnectionProxy: re-resolves the thread-local
    wrapper on every __getattr__ call so background threads (swipe.py prefetch) get their own connection, not the main thread's.
    """

    def __getattr__(self, name):
        return getattr(_connections['buildings'], name)


# patched in test_topic02
connection = _BuildingsConnectionProxy()


# ---------------------------------------------------------------------------
# __all__: public API surface (private names excluded)
# ---------------------------------------------------------------------------
__all__ = [
    # External module objects
    'connection',
    'event_log',
    # Public functions + constants
    'get_axis_vocab',
    'embed_visual_description',
    'generate_persona_report',
    'generate_persona_image',
    'build_image_report_from_facts',
    'generate_taste_board_name',
    'rerank_candidates',
]
