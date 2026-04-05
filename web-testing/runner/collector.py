"""
collector.py -- Data collection during E2E test runs.
Captures screenshots, timing, API calls, errors.
"""
import os
import time
from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class ApiCallRecord:
    url: str
    method: str
    status: int
    latency_ms: float
    payload_size: int = 0


@dataclass
class ErrorRecord:
    message: str
    source: str  # 'console' | 'network' | 'exception'
    stack_trace: Optional[str] = None
    screenshot_path: Optional[str] = None


@dataclass
class StepRecord:
    step_name: str
    timestamp: float = 0.0
    duration_ms: float = 0.0
    screenshot_path: Optional[str] = None
    api_calls: List[ApiCallRecord] = field(default_factory=list)
    errors: List[ErrorRecord] = field(default_factory=list)
    page_url: str = ''
    metadata: dict = field(default_factory=dict)


class Collector:
    """
    Manages data collection during a Playwright test run.
    Captures screenshots, tracks API calls, and collects errors.
    """

    def __init__(self, run_id: str, base_dir: str):
        self.run_id = run_id
        self.base_dir = base_dir
        self.screenshots_dir = os.path.join(base_dir, 'screenshots')
        os.makedirs(self.screenshots_dir, exist_ok=True)

        self._pending_api_calls: List[ApiCallRecord] = []
        self._pending_errors: List[ErrorRecord] = []
        self._response_timings: dict = {}  # url -> start_time

    def start_tracking_responses(self, page):
        """Attach response listener to the page for API call tracking."""
        def on_response(response):
            url = response.url
            # Only track API calls to our backend
            if '/api/' not in url:
                return
            try:
                status = response.status
                # Compute latency from request timing if available
                timing = response.request.timing
                latency_ms = timing.get('responseEnd', 0) - timing.get('requestStart', 0)
                if latency_ms <= 0:
                    latency_ms = 0

                method = response.request.method
                try:
                    body = response.body()
                    payload_size = len(body)
                except Exception:
                    payload_size = 0

                record = ApiCallRecord(
                    url=url,
                    method=method,
                    status=status,
                    latency_ms=latency_ms,
                    payload_size=payload_size,
                )
                self._pending_api_calls.append(record)

                # Track network errors
                if status >= 400:
                    self._pending_errors.append(ErrorRecord(
                        message=f"HTTP {status} on {method} {url}",
                        source='network',
                    ))
            except Exception:
                pass

        page.on('response', on_response)

    def start_tracking_console(self, page):
        """Attach console listener to the page for error tracking."""
        def on_console(msg):
            if msg.type == 'error':
                self._pending_errors.append(ErrorRecord(
                    message=msg.text,
                    source='console',
                ))

        page.on('console', on_console)

    def start_tracking_exceptions(self, page):
        """Attach page error listener for uncaught exceptions."""
        def on_page_error(error):
            self._pending_errors.append(ErrorRecord(
                message=str(error),
                source='exception',
                stack_trace=str(error),
            ))

        page.on('pageerror', on_page_error)

    def capture_screenshot(self, page, step_name: str) -> str:
        """Take a screenshot and return the file path."""
        safe_name = step_name.replace(' ', '_').replace('/', '_')
        filename = f"{safe_name}.png"
        filepath = os.path.join(self.screenshots_dir, filename)
        page.screenshot(path=filepath, full_page=False)
        return filepath

    def capture_error_screenshot(self, page, error_msg: str) -> str:
        """Take a screenshot specifically for an error context."""
        safe_name = f"error_{int(time.time() * 1000)}"
        filename = f"{safe_name}.png"
        filepath = os.path.join(self.screenshots_dir, filename)
        try:
            page.screenshot(path=filepath, full_page=False)
        except Exception:
            return ''
        return filepath

    def collect_step(self, page, step_name: str, start_time: float,
                     metadata: Optional[dict] = None,
                     screenshot: bool = True) -> StepRecord:
        """
        Finalize data collection for a step.
        Takes screenshot (unless screenshot=False), gathers pending API calls and errors.
        """
        duration_ms = (time.time() - start_time) * 1000
        screenshot_path = self.capture_screenshot(page, step_name) if screenshot else ''

        # Drain pending data
        api_calls = list(self._pending_api_calls)
        errors = list(self._pending_errors)
        self._pending_api_calls.clear()
        self._pending_errors.clear()

        try:
            page_url = page.url
        except Exception:
            page_url = ''

        return StepRecord(
            step_name=step_name,
            timestamp=start_time,
            duration_ms=duration_ms,
            screenshot_path=screenshot_path,
            api_calls=api_calls,
            errors=errors,
            page_url=page_url,
            metadata=metadata or {},
        )

    def drain_errors(self) -> List[ErrorRecord]:
        """Return and clear any remaining pending errors."""
        errors = list(self._pending_errors)
        self._pending_errors.clear()
        return errors
