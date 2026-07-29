"""Throttle configuration tests for recommendation app.

HIGH-THROTTLE-1 (audit 2026-07-17): verify throttle classes are wired to
the three Gemini-calling views and scopes are registered in settings.
"""
import pytest


@pytest.mark.django_db
class TestRecommendationThrottles:

    def test_llm_search_throttle_configured(self):
        """ParseQueryView has LLMSearchThrottle; scope registered in settings."""
        from django.conf import settings
        from apps.recommendation.views.search import ParseQueryView
        from apps.recommendation.throttles import LLMSearchThrottle
        from rest_framework.throttling import UserRateThrottle

        assert issubclass(LLMSearchThrottle, UserRateThrottle)
        assert LLMSearchThrottle.scope == 'llm_search'
        assert LLMSearchThrottle in ParseQueryView.throttle_classes

        rates = settings.REST_FRAMEWORK.get('DEFAULT_THROTTLE_RATES', {})
        assert 'llm_search' in rates, "'llm_search' scope missing from DEFAULT_THROTTLE_RATES"

    def test_report_generate_throttle_configured(self):
        """ProjectReportGenerateView has ReportGenerateThrottle; scope registered."""
        from django.conf import settings
        from apps.recommendation.views.reports import ProjectReportGenerateView
        from apps.recommendation.throttles import ReportGenerateThrottle
        from rest_framework.throttling import UserRateThrottle

        assert issubclass(ReportGenerateThrottle, UserRateThrottle)
        assert ReportGenerateThrottle.scope == 'report_generate'
        assert ReportGenerateThrottle in ProjectReportGenerateView.throttle_classes

        rates = settings.REST_FRAMEWORK.get('DEFAULT_THROTTLE_RATES', {})
        assert 'report_generate' in rates, "'report_generate' scope missing from DEFAULT_THROTTLE_RATES"

    def test_report_image_throttle_configured(self):
        """ProjectReportImageView has ReportImageThrottle; scope registered."""
        from django.conf import settings
        from apps.recommendation.views.reports import ProjectReportImageView
        from apps.recommendation.throttles import ReportImageThrottle
        from rest_framework.throttling import UserRateThrottle

        assert issubclass(ReportImageThrottle, UserRateThrottle)
        assert ReportImageThrottle.scope == 'report_image'
        assert ReportImageThrottle in ProjectReportImageView.throttle_classes

        rates = settings.REST_FRAMEWORK.get('DEFAULT_THROTTLE_RATES', {})
        assert 'report_image' in rates, "'report_image' scope missing from DEFAULT_THROTTLE_RATES"

    def test_throttle_scopes_are_unique(self):
        """Three throttle scopes are distinct — no shared DRF cache key collisions."""
        from apps.recommendation.throttles import (
            LLMSearchThrottle, ReportGenerateThrottle, ReportImageThrottle,
        )
        scopes = [LLMSearchThrottle.scope, ReportGenerateThrottle.scope, ReportImageThrottle.scope]
        assert len(scopes) == len(set(scopes)), f"Duplicate scopes: {scopes}"
