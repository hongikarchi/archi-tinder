"""
test_gemini_fail_fast.py -- Unit tests for _retry_gemini_call fast-fail behavior.

Verifies that permanent 4xx errors (PermissionDenied, Unauthenticated,
InvalidArgument) are NOT retried, while transient errors (ResourceExhausted,
generic Exception) do get the configured retry.

No Django DB required — pure unit tests over the retry helper.
No real Gemini API calls are made.
"""
import pytest
from unittest.mock import MagicMock
from google.api_core import exceptions as gax_exceptions

from apps.recommendation.services._gemini import _retry_gemini_call


# ---------------------------------------------------------------------------
# Fast-fail tests — permanent errors must not be retried
# ---------------------------------------------------------------------------

def test_permission_denied_no_retry():
    """403 PermissionDenied must propagate immediately; fn called exactly once."""
    fn = MagicMock(side_effect=gax_exceptions.PermissionDenied('forbidden'))
    with pytest.raises(gax_exceptions.PermissionDenied):
        _retry_gemini_call(fn)
    fn.assert_called_once()


def test_unauthenticated_no_retry():
    """401 Unauthenticated must propagate immediately; fn called exactly once."""
    fn = MagicMock(side_effect=gax_exceptions.Unauthenticated('bad credentials'))
    with pytest.raises(gax_exceptions.Unauthenticated):
        _retry_gemini_call(fn)
    fn.assert_called_once()


def test_invalid_argument_no_retry():
    """400 InvalidArgument must propagate immediately; fn called exactly once."""
    fn = MagicMock(side_effect=gax_exceptions.InvalidArgument('bad request'))
    with pytest.raises(gax_exceptions.InvalidArgument):
        _retry_gemini_call(fn)
    fn.assert_called_once()


# ---------------------------------------------------------------------------
# Retry tests — transient errors must get the one retry
# ---------------------------------------------------------------------------

def test_resource_exhausted_retries(monkeypatch):
    """ResourceExhausted is transient; fn must be called twice before raising."""
    monkeypatch.setattr(
        'apps.recommendation.services._gemini.time.sleep',
        lambda _: None,
    )
    fn = MagicMock(side_effect=gax_exceptions.ResourceExhausted('quota'))
    with pytest.raises(gax_exceptions.ResourceExhausted):
        _retry_gemini_call(fn)
    assert fn.call_count == 2


def test_generic_exception_retries(monkeypatch):
    """A plain Exception is transient; fn must be called twice before raising."""
    monkeypatch.setattr(
        'apps.recommendation.services._gemini.time.sleep',
        lambda _: None,
    )
    fn = MagicMock(side_effect=Exception('network blip'))
    with pytest.raises(Exception, match='network blip'):
        _retry_gemini_call(fn)
    assert fn.call_count == 2
