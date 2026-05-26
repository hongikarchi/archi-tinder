"""Per-stage performance timing instrumentation for PERF-1/2/3.

Opt-in via settings.PERF_TIMING_ENABLED (default False — zero overhead
when off). When enabled, each `stage(name)` block logs:

    perf_timing INFO endpoint=<endpoint> stage=<name> ms=<float> [extra=...]

Designed to be lightweight (single time.perf_counter() pair) and tolerant
of nested usage (stages compose via the `endpoint` context var).
"""
from __future__ import annotations

import contextvars
import logging
import time
from contextlib import contextmanager
from typing import Any, Iterator

from django.conf import settings

logger = logging.getLogger('perf_timing')

_endpoint_ctx: contextvars.ContextVar[str] = contextvars.ContextVar(
    'perf_timing_endpoint', default='unknown'
)


@contextmanager
def endpoint(name: str) -> Iterator[None]:
    """Set the endpoint label that subsequent stage() calls inherit."""
    token = _endpoint_ctx.set(name)
    try:
        yield
    finally:
        _endpoint_ctx.reset(token)


@contextmanager
def stage(name: str, **extra: Any) -> Iterator[None]:
    """Time a named stage. No-op when PERF_TIMING_ENABLED is False."""
    if not getattr(settings, 'PERF_TIMING_ENABLED', False):
        yield
        return
    t0 = time.perf_counter()
    try:
        yield
    finally:
        elapsed_ms = (time.perf_counter() - t0) * 1000.0
        extra_str = ' '.join(f'{k}={v}' for k, v in extra.items())
        logger.info(
            'endpoint=%s stage=%s ms=%.2f %s',
            _endpoint_ctx.get(), name, elapsed_ms, extra_str,
        )
