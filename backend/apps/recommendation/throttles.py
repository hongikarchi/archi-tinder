"""Custom DRF throttle classes for ArchiTinder recommendation app.

HIGH-THROTTLE-1 (audit 2026-07-17): ParseQueryView, ProjectReportGenerateView,
and ProjectReportImageView had no throttle_classes, exposing unbounded Gemini
API spend per authenticated user.
"""

from rest_framework.throttling import UserRateThrottle


class LLMSearchThrottle(UserRateThrottle):
    """10 LLM search queries per minute per authenticated user.

    IsAuthenticated endpoint — UserRateThrottle keys on authenticated user.
    Gemini text model call on every request; 10/min prevents runaway spend
    while allowing normal interactive use (1 query every 6 s).
    """
    scope = 'llm_search'
    rate  = '10/min'


class ReportGenerateThrottle(UserRateThrottle):
    """3 persona report generations per hour per authenticated user.

    IsAuthenticated endpoint — UserRateThrottle keys on authenticated user.
    Gemini text model + axis_scores computation; low cap because result is
    cached on the Project row and regenerating rarely makes sense.
    """
    scope = 'report_generate'
    rate  = '3/hour'


class ReportImageThrottle(UserRateThrottle):
    """2 persona image generations per hour per authenticated user.

    IsAuthenticated endpoint — UserRateThrottle keys on authenticated user.
    Gemini image generation is the highest-cost call in the app; tight cap
    prevents accidental or abusive billing.
    """
    scope = 'report_image'
    rate  = '2/hour'
