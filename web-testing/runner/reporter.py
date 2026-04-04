"""
reporter.py -- Generates report.json from collected test data.
"""
import json
import os
from dataclasses import asdict
from typing import List

from .collector import StepRecord


def _classify_bottleneck(step: StepRecord) -> str:
    """
    Classify the bottleneck type for a slow step.
    Returns: 'image_loading', 'api_call', 'rendering', or 'unknown'.
    """
    if not step.api_calls:
        return 'rendering'

    # Check if image-related APIs dominated
    image_calls = [c for c in step.api_calls if '/images/' in c.url]
    api_calls = [c for c in step.api_calls if '/api/' in c.url]

    if image_calls:
        total_image_latency = sum(c.latency_ms for c in image_calls)
        total_api_latency = sum(c.latency_ms for c in api_calls)
        if total_image_latency > total_api_latency * 0.5:
            return 'image_loading'

    # Check for slow API calls
    slow_api = [c for c in api_calls if c.latency_ms > 500]
    if slow_api:
        # Determine which type of API call
        for call in slow_api:
            if '/report/' in call.url:
                return 'llm_api'
            if '/sessions/' in call.url and '/swipes/' in call.url:
                return 'algorithm_computation'
            if '/sessions/' in call.url:
                return 'database_query'
        return 'api_call'

    return 'rendering'


def generate_report(
    run_id: str,
    persona_dict: dict,
    steps: List[StepRecord],
    reports_dir: str,
) -> dict:
    """
    Generate a structured report.json from test run data.

    Args:
        run_id: Unique run identifier.
        persona_dict: Serialized persona profile.
        steps: List of StepRecord from the test run.
        reports_dir: Base reports directory.

    Returns:
        The report dict (also written to disk).
    """
    # Compute summary
    total_duration = sum(s.duration_ms for s in steps)
    total_errors = sum(len(s.errors) for s in steps)

    # Extract swipe stats from metadata
    swipe_steps = [s for s in steps if s.step_name.startswith('05_swipe_')]
    total_swipes = len(swipe_steps)
    likes = sum(1 for s in swipe_steps if s.metadata.get('decision') == 'like')
    dislikes = sum(1 for s in swipe_steps if s.metadata.get('decision') == 'dislike')
    buildings_liked = [
        s.metadata.get('building_id', '')
        for s in swipe_steps
        if s.metadata.get('decision') == 'like' and s.metadata.get('building_id')
    ]

    # Identify slow pages (> 1000ms)
    slow_pages = []
    for s in steps:
        if s.duration_ms > 1000:
            slow_pages.append({
                'step_name': s.step_name,
                'duration_ms': round(s.duration_ms, 1),
                'bottleneck': _classify_bottleneck(s),
                'api_calls_count': len(s.api_calls),
            })

    # Extract report content if available
    report_step = next((s for s in steps if s.step_name == '07_persona_report'), None)
    report_content = report_step.metadata if report_step else None

    # Build step details
    step_details = []
    for s in steps:
        # Make screenshot paths relative for dashboard portability
        screenshot_rel = ''
        if s.screenshot_path:
            screenshot_rel = os.path.relpath(
                s.screenshot_path,
                os.path.join(reports_dir, run_id),
            )

        step_detail = {
            'step_name': s.step_name,
            'timestamp': s.timestamp,
            'duration_ms': round(s.duration_ms, 1),
            'screenshot': screenshot_rel,
            'page_url': s.page_url,
            'metadata': s.metadata,
            'api_calls': [
                {
                    'url': c.url,
                    'method': c.method,
                    'status': c.status,
                    'latency_ms': round(c.latency_ms, 1),
                    'payload_size': c.payload_size,
                }
                for c in s.api_calls
            ],
            'errors': [
                {
                    'message': e.message,
                    'source': e.source,
                    'stack_trace': e.stack_trace,
                }
                for e in s.errors
            ],
        }
        step_details.append(step_detail)

    report = {
        'run_id': run_id,
        'persona': persona_dict,
        'steps': step_details,
        'summary': {
            'total_duration_ms': round(total_duration, 1),
            'total_steps': len(steps),
            'total_swipes': total_swipes,
            'likes': likes,
            'dislikes': dislikes,
            'error_count': total_errors,
            'slow_pages': slow_pages,
            'buildings_liked': buildings_liked,
            'session_completed': any(
                s.metadata.get('session_completed') or s.metadata.get('action') == 'view_results'
                for s in steps
            ),
        },
        'report_content': report_content,
    }

    # Write to disk
    run_dir = os.path.join(reports_dir, run_id)
    report_path = os.path.join(run_dir, 'report.json')
    with open(report_path, 'w') as f:
        json.dump(report, f, indent=2, default=str)

    return report
