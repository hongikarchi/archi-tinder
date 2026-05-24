"""
test_gemini_timeout.py -- Unit tests for _retry_gemini_call hard timeout.

Verifies that:
1. A hung/slow Gemini call is hard-capped at the configured timeout.
2. PermissionDenied (FATAL) still fast-fails without retry under timeout.
3. Generic Exception with one retry succeeds on second attempt under timeout.
4. A fast successful call returns normally under the default timeout.

No Django DB required — pure unit tests over the retry helper.
No real Gemini API calls are made.
"""
import threading
import time

import pytest
from google.api_core import exceptions as gax_exceptions
from unittest.mock import MagicMock

from apps.recommendation.services._gemini import _retry_gemini_call


# ---------------------------------------------------------------------------
# Test 1: slow func triggers deadline, eventually raises TimeoutError
# ---------------------------------------------------------------------------

def test_timeout_raises_after_deadline(monkeypatch):
    """
    A func that blocks must be cut off by a 0.5s deadline. With
    _GEMINI_MAX_RETRIES=1 (two attempts), we expect TimeoutError.

    `_gemini.py` captures `threading.Thread` at module-load time as
    `_Thread`, so this test is immune to any global threading.Thread mock
    a previous test (e.g. `_DiscThread` in test_imp8) may have left in
    place — the wrapper always spawns a real OS thread.
    """
    monkeypatch.setattr(
        'apps.recommendation.services._gemini.time.sleep',
        lambda _: None,
    )

    event = threading.Event()

    def hung_func():
        # blocks until event is set; released in the finally to free the
        # daemon worker after the wrapper has already raised.
        event.wait(timeout=30.0)
        return 'never reached'

    try:
        with pytest.raises(TimeoutError, match='Gemini call exceeded'):
            _retry_gemini_call(hung_func, timeout=0.5)
    finally:
        event.set()


# ---------------------------------------------------------------------------
# Test 2: PermissionDenied (FATAL) fast-fails even under a generous timeout
# ---------------------------------------------------------------------------

def test_fatal_exc_fast_fail_under_timeout():
    """
    PermissionDenied must propagate immediately without retry.
    The timeout is large (10s) so the deadline is not the cause.
    fn must be called exactly once.
    """
    fn = MagicMock(side_effect=gax_exceptions.PermissionDenied('forbidden'))
    with pytest.raises(gax_exceptions.PermissionDenied):
        _retry_gemini_call(fn, timeout=10.0)
    fn.assert_called_once()


# ---------------------------------------------------------------------------
# Test 3: generic Exception on first attempt, success on retry
# ---------------------------------------------------------------------------

def test_transient_exc_retries_and_succeeds(monkeypatch):
    """
    A func that raises a generic Exception on attempt 1 then returns on
    attempt 2 must succeed overall. Patch sleep so no real delay occurs.
    """
    monkeypatch.setattr(
        'apps.recommendation.services._gemini.time.sleep',
        lambda _: None,
    )

    call_count = {'n': 0}

    def flaky_func():
        call_count['n'] += 1
        if call_count['n'] == 1:
            raise Exception('transient network blip')
        return 'success'

    result = _retry_gemini_call(flaky_func, timeout=10.0)
    assert result == 'success'
    assert call_count['n'] == 2


# ---------------------------------------------------------------------------
# Test 4: fast successful call returns normally
# ---------------------------------------------------------------------------

def test_fast_success_returns_result():
    """
    A func that returns in 0.1s must succeed with the default 15s timeout.
    """
    def fast_func():
        time.sleep(0.1)
        return 'done'

    result = _retry_gemini_call(fast_func)
    assert result == 'done'
