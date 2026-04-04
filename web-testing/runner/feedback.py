"""
feedback.py -- Generates structured feedback JSON for orchestrator consumption.
Maps errors to source files and provides actionable suggestions.
"""
import json
import os
from typing import List

# -- Endpoint -> source file mapping --

ENDPOINT_FILE_MAP = {
    '/api/v1/auth/': 'backend/apps/accounts/',
    '/api/v1/auth/social/': 'backend/apps/accounts/views.py',
    '/api/v1/auth/token/': 'backend/apps/accounts/views.py',
    '/api/v1/auth/dev-login/': 'backend/apps/accounts/views.py',
    '/api/v1/analysis/sessions/': 'backend/apps/recommendation/views.py',
    '/api/v1/analysis/sessions/swipes/': 'backend/apps/recommendation/views.py',
    '/api/v1/analysis/report/': 'backend/apps/recommendation/services.py',
    '/api/v1/projects/': 'backend/apps/recommendation/views.py',
    '/api/v1/projects/report/': 'backend/apps/recommendation/services.py',
    '/api/v1/images/': 'backend/apps/images/',
    '/api/v1/images/batch/': 'backend/apps/images/views.py',
    '/api/v1/images/diverse-random/': 'backend/apps/images/views.py',
    '/api/v1/parse-query/': 'backend/apps/recommendation/services.py',
}

# -- Performance cause hints --

PERFORMANCE_HINTS = {
    '/swipes/': 'algorithm_computation',
    '/images/': 'image_loading',
    '/report/': 'llm_api',
    '/sessions/': 'database_query',
    '/parse-query/': 'llm_api',
    '/batch/': 'database_query',
}


def _map_endpoint_to_file(url: str) -> str:
    """Map an API endpoint URL to a source file path."""
    # Try specific matches first (longest prefix wins)
    best_match = ''
    best_file = 'unknown'
    for pattern, filepath in ENDPOINT_FILE_MAP.items():
        if pattern in url and len(pattern) > len(best_match):
            best_match = pattern
            best_file = filepath
    return best_file


def _get_performance_hint(url: str) -> str:
    """Get a performance cause hint for an endpoint."""
    for pattern, hint in PERFORMANCE_HINTS.items():
        if pattern in url:
            return hint
    return 'unknown'


def _generate_suggestion(errors: list, perf_issues: list) -> str:
    """Generate a human-readable suggestion string."""
    parts = []

    # Error suggestions
    error_sources = set()
    for err in errors:
        error_sources.add(err.get('source_file', 'unknown'))

    if error_sources:
        files = ', '.join(sorted(error_sources))
        parts.append(f"Fix errors in: {files}")

    # Performance suggestions
    if perf_issues:
        slow_types = set(p.get('cause', '') for p in perf_issues)
        if 'algorithm_computation' in slow_types:
            parts.append("Swipe endpoint is slow -- check engine.py caching and KMeans computation")
        if 'image_loading' in slow_types:
            parts.append("Image loading is slow -- check R2 CDN and batch endpoint")
        if 'llm_api' in slow_types:
            parts.append("LLM API calls are slow -- expected for Gemini, consider timeout increase")
        if 'database_query' in slow_types:
            parts.append("Database queries are slow -- check indexes and connection pooling")

    if not parts:
        return "All tests passed. No issues detected."

    return '; '.join(parts)


def generate_feedback(report: dict, reports_dir: str) -> dict:
    """
    Generate structured feedback JSON from a test report.

    Args:
        report: The report dict from reporter.py.
        reports_dir: Base reports directory.

    Returns:
        Feedback dict (also written to disk).
    """
    run_id = report.get('run_id', 'unknown')
    summary = report.get('summary', {})
    steps = report.get('steps', [])

    # Collect all errors with source mapping
    errors = []
    for step in steps:
        for err in step.get('errors', []):
            error_entry = {
                'step': step['step_name'],
                'message': err['message'],
                'source': err['source'],
                'source_file': 'unknown',
                'severity': 'error',
            }

            # Try to map to source file from API call context
            if err['source'] == 'network':
                # Extract URL from error message
                for api_call in step.get('api_calls', []):
                    if api_call.get('status', 0) >= 400:
                        error_entry['source_file'] = _map_endpoint_to_file(api_call['url'])
                        error_entry['endpoint'] = api_call['url']
                        break
            elif err['source'] == 'console':
                error_entry['severity'] = 'warning'
                error_entry['source_file'] = 'frontend/'
            elif err['source'] == 'exception':
                error_entry['severity'] = 'critical'

            errors.append(error_entry)

    # Collect performance issues
    performance_issues = []
    for step in steps:
        if step.get('duration_ms', 0) > 3000:
            severity = 'critical'
        elif step.get('duration_ms', 0) > 1000:
            severity = 'warning'
        else:
            continue

        # Find the slowest API call in this step
        slowest_api = None
        for api_call in step.get('api_calls', []):
            if not slowest_api or api_call.get('latency_ms', 0) > slowest_api.get('latency_ms', 0):
                slowest_api = api_call

        cause = 'rendering'
        source_file = 'frontend/'
        if slowest_api:
            cause = _get_performance_hint(slowest_api.get('url', ''))
            source_file = _map_endpoint_to_file(slowest_api.get('url', ''))

        performance_issues.append({
            'step': step['step_name'],
            'duration_ms': round(step['duration_ms'], 1),
            'severity': severity,
            'cause': cause,
            'source_file': source_file,
            'slowest_api': slowest_api,
        })

    # Determine overall status
    has_critical = any(
        e.get('severity') == 'critical' for e in errors
    ) or any(
        p.get('severity') == 'critical' for p in performance_issues
    )
    has_errors = len(errors) > 0

    if has_critical:
        status = 'fail'
    elif has_errors:
        status = 'warn'
    else:
        status = 'pass'

    suggestion = _generate_suggestion(errors, performance_issues)

    feedback = {
        'run_id': run_id,
        'status': status,
        'errors': errors,
        'performance_issues': performance_issues,
        'summary': {
            'total_errors': len(errors),
            'total_performance_issues': len(performance_issues),
            'total_swipes': summary.get('total_swipes', 0),
            'session_completed': summary.get('session_completed', False),
        },
        'suggestion': suggestion,
    }

    # Write to disk
    run_dir = os.path.join(reports_dir, run_id)
    feedback_path = os.path.join(run_dir, 'feedback.json')
    with open(feedback_path, 'w') as f:
        json.dump(feedback, f, indent=2)

    return feedback
