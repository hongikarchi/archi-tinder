"""Custom DRF throttle classes for ArchiTinder recommendation app.

HIGH-THROTTLE-1 (audit 2026-07-17): TasteRecognizeView, ProjectReportGenerateView,
and ProjectReportImageView had no throttle_classes, exposing unbounded LLM
API spend per authenticated user.

Throttles are endpoint-level, provider-agnostic — they cap requests per user
regardless of which LLM serves the view. Current provider per seam (#290):
taste tag recognition (LLMSearchThrottle) = settings.LLM_PROVIDER / JEV, persona
report text = Gemini (code-pinned), persona image = settings.LLM_IMAGE_PROVIDER
(default gemini). The class-level `rate` attr below is the EFFECTIVE value —
DRF's SimpleRateThrottle ignores DEFAULT_THROTTLE_RATES when the class sets
`rate` (see settings.py note + Task.md BACK-THROTTLE-2).
"""

from rest_framework.throttling import UserRateThrottle


class LLMSearchThrottle(UserRateThrottle):
    """10 LLM search queries per minute per authenticated user.

    IsAuthenticated endpoint — UserRateThrottle keys on authenticated user.
    LLM text call on every request (provider = settings.LLM_PROVIDER; openai
    in prod since #290); 10/min prevents runaway spend while allowing normal
    interactive use (1 query every 6 s).
    """
    scope = 'llm_search'
    rate  = '10/min'


class TasteRecognizeDailyThrottle(UserRateThrottle):
    """200 taste recognitions per day per authenticated user (paid JEV call cost cap).

    Stacked with LLMSearchThrottle (10/min) on TasteRecognizeView.
    """
    scope = 'taste_recognize_day'
    rate  = '200/day'


class ProjectRecommendationsThrottle(UserRateThrottle):
    """30 board-recommendation reads per minute per authenticated user.

    The endpoint runs the recommendation engine on a cache miss (responses are
    cached per project for 10 min), so the cap guards DB/embedding cost. There
    is no LLM spend while RECOMMENDATION['gemini_rerank_enabled'] is False
    (build_predicted_cards would call the Gemini rerank if it were enabled).
    """
    scope = 'project_recommendations'
    rate  = '30/min'


class ReportGenerateThrottle(UserRateThrottle):
    """10 persona report generations per hour per authenticated user.

    IsAuthenticated endpoint — UserRateThrottle keys on authenticated user.
    Frontend auto-calls report generation on session completion (up to 2x
    per session: App.jsx goToResults + resume path), so 3/hour caused 429
    on the 2nd session within an hour. 10/hour accommodates ~5 sessions/hr
    while still preventing runaway Gemini spend.
    """
    scope = 'report_generate'
    rate  = '10/hour'


class ReportImageThrottle(UserRateThrottle):
    """5 persona image generations per hour per authenticated user.

    IsAuthenticated endpoint — UserRateThrottle keys on authenticated user.
    Raised from 2/hour to match the report_generate headroom increase —
    image gen follows report gen in the same user flow.
    """
    scope = 'report_image'
    rate  = '5/hour'
