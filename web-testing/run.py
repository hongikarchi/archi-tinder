#!/usr/bin/env python3
"""
run.py -- CLI entry point for the web-testing E2E visual test runner.

Usage:
    python web-testing/run.py                          # Single persona, template mode
    python web-testing/run.py --personas 3             # 3 personas
    python web-testing/run.py --mode llm               # Use Gemini for persona generation
    python web-testing/run.py --dashboard-only          # Serve dashboard without running tests
    python web-testing/run.py --auto-fix               # Print structured feedback for orchestrator
    python web-testing/run.py --loop 3                 # Run 3 iterations
"""
import argparse
import http.server
import json
import os
import shutil
import socketserver
import sys
import time
from datetime import datetime

# Ensure web-testing/ is importable
_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
if _SCRIPT_DIR not in sys.path:
    sys.path.insert(0, _SCRIPT_DIR)

from research.persona import generate_persona
from research.scenarios import build_scenario
from runner.runner import run_test
from runner.reporter import generate_report
from runner.feedback import generate_feedback

# -- Constants --

REPORTS_DIR = os.path.join(_SCRIPT_DIR, 'reports')
DASHBOARD_DIR = os.path.join(_SCRIPT_DIR, 'dashboard')
DASHBOARD_DATA_DIR = os.path.join(DASHBOARD_DIR, 'data', 'latest')


def _generate_run_id() -> str:
    """Generate a unique run ID based on timestamp."""
    return datetime.now().strftime('run_%Y%m%d_%H%M%S')


def _copy_run_to_dashboard(run_id: str):
    """Copy a single run's data to dashboard/data/{run_id}/ for multi-persona viewing."""
    data_dir = os.path.join(DASHBOARD_DIR, 'data')
    dst_dir = os.path.join(data_dir, run_id)
    os.makedirs(dst_dir, exist_ok=True)

    run_dir = os.path.join(REPORTS_DIR, run_id)

    for filename in ('report.json', 'feedback.json'):
        src = os.path.join(run_dir, filename)
        dst = os.path.join(dst_dir, filename)
        if os.path.exists(src):
            shutil.copy2(src, dst)

    screenshots_src = os.path.join(run_dir, 'screenshots')
    screenshots_dst = os.path.join(dst_dir, 'screenshots')
    if os.path.exists(screenshots_src):
        if os.path.exists(screenshots_dst):
            shutil.rmtree(screenshots_dst)
        shutil.copytree(screenshots_src, screenshots_dst)


def _publish_dashboard(run_ids: list):
    """Write runs manifest and update data/latest/ for the dashboard."""
    data_dir = os.path.join(DASHBOARD_DIR, 'data')
    os.makedirs(data_dir, exist_ok=True)

    # Clean up stale run dirs from previous batches
    for entry in os.listdir(data_dir):
        if entry.startswith('run_') and entry not in run_ids:
            stale = os.path.join(data_dir, entry)
            if os.path.isdir(stale):
                shutil.rmtree(stale)

    # Build runs manifest from each run's report + feedback
    runs = []
    for rid in run_ids:
        report_path = os.path.join(REPORTS_DIR, rid, 'report.json')
        feedback_path = os.path.join(REPORTS_DIR, rid, 'feedback.json')
        persona_name = 'Unknown'
        occupation = ''
        status = 'unknown'
        if os.path.exists(report_path):
            with open(report_path) as f:
                r = json.load(f)
                persona_name = r.get('persona', {}).get('name', 'Unknown')
                occupation = r.get('persona', {}).get('occupation', '')
        if os.path.exists(feedback_path):
            with open(feedback_path) as f:
                fb = json.load(f)
                status = fb.get('status', 'unknown')
        runs.append({
            'run_id': rid,
            'persona_name': persona_name,
            'occupation': occupation,
            'status': status,
        })

    with open(os.path.join(data_dir, 'runs.json'), 'w') as f:
        json.dump({'runs': runs}, f, indent=2)

    # Also maintain data/latest/ as copy of last run (backwards compat)
    if run_ids:
        last_id = run_ids[-1]
        latest_dir = os.path.join(data_dir, 'latest')
        os.makedirs(latest_dir, exist_ok=True)
        last_run_dir = os.path.join(REPORTS_DIR, last_id)
        for filename in ('report.json', 'feedback.json'):
            src = os.path.join(last_run_dir, filename)
            dst = os.path.join(latest_dir, filename)
            if os.path.exists(src):
                shutil.copy2(src, dst)
        screenshots_src = os.path.join(last_run_dir, 'screenshots')
        screenshots_dst = os.path.join(latest_dir, 'screenshots')
        if os.path.exists(screenshots_src):
            if os.path.exists(screenshots_dst):
                shutil.rmtree(screenshots_dst)
            shutil.copytree(screenshots_src, screenshots_dst)


def _serve_dashboard(port: int = 8080):
    """Serve the dashboard via Python's http.server."""
    os.chdir(DASHBOARD_DIR)
    handler = http.server.SimpleHTTPRequestHandler
    with socketserver.TCPServer(('', port), handler) as httpd:
        print(f"\n  Dashboard: http://localhost:{port}")
        print("  Press Ctrl+C to stop.\n")
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\nDashboard stopped.")


def _print_summary(report: dict, feedback: dict):
    """Print a human-readable summary to stdout."""
    summary = report.get('summary', {})
    persona = report.get('persona', {})

    print("\n" + "=" * 60)
    print(f"  Test Run: {report.get('run_id', 'unknown')}")
    print(f"  Persona:  {persona.get('name', 'Unknown')} ({persona.get('occupation', '')})")
    print(f"  Query:    {persona.get('search_query', '')}")
    print("=" * 60)
    print(f"  Total Duration: {summary.get('total_duration_ms', 0):.0f}ms")
    print(f"  Steps:          {summary.get('total_steps', 0)}")
    print(f"  Swipes:         {summary.get('total_swipes', 0)} (L:{summary.get('likes', 0)} D:{summary.get('dislikes', 0)})")
    print(f"  Errors:         {summary.get('error_count', 0)}")
    print(f"  Completed:      {'Yes' if summary.get('session_completed') else 'No'}")

    if summary.get('slow_pages'):
        print(f"\n  Slow Pages:")
        for sp in summary['slow_pages']:
            print(f"    - {sp['step_name']}: {sp['duration_ms']:.0f}ms ({sp['bottleneck']})")

    status = feedback.get('status', 'unknown')
    status_icon = {'pass': '[PASS]', 'warn': '[WARN]', 'fail': '[FAIL]'}.get(status, '[????]')
    print(f"\n  Status: {status_icon}")
    print(f"  Suggestion: {feedback.get('suggestion', 'N/A')}")
    print("=" * 60 + "\n")


def run_single(mode: str = 'template', max_swipes: int = 15) -> tuple:
    """
    Run a single persona test.
    Returns (run_id, report, feedback) tuple.
    """
    run_id = _generate_run_id()
    os.makedirs(os.path.join(REPORTS_DIR, run_id), exist_ok=True)

    print(f"  Generating persona (mode={mode})...")
    persona = generate_persona(mode=mode)
    print(f"  Persona: {persona.name} -- {persona.occupation}")
    print(f"  Query: {persona.search_query}")

    scenario = build_scenario(persona, max_swipes=max_swipes)

    print(f"  Running E2E test (run_id={run_id})...")
    steps = run_test(scenario, run_id, REPORTS_DIR)
    print(f"  Collected {len(steps)} steps.")

    report = generate_report(run_id, persona.to_dict(), steps, REPORTS_DIR)
    feedback = generate_feedback(report, REPORTS_DIR)

    _copy_run_to_dashboard(run_id)

    return run_id, report, feedback


def main():
    parser = argparse.ArgumentParser(
        description='ArchiTinder E2E Visual Test Runner',
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        '--personas', type=int, default=1,
        help='Number of personas to test (default: 1)',
    )
    parser.add_argument(
        '--mode', choices=['template', 'llm'], default='template',
        help='Persona generation mode (default: template)',
    )
    parser.add_argument(
        '--max-swipes', type=int, default=15,
        help='Maximum swipes per persona (default: 15)',
    )
    parser.add_argument(
        '--auto-fix', action='store_true',
        help='Print structured feedback JSON to stdout for orchestrator',
    )
    parser.add_argument(
        '--loop', type=int, default=1,
        help='Number of test iterations (default: 1)',
    )
    parser.add_argument(
        '--dashboard-only', action='store_true',
        help='Serve the dashboard without running tests',
    )
    parser.add_argument(
        '--dashboard-port', type=int, default=8080,
        help='Port for dashboard server (default: 8080)',
    )

    args = parser.parse_args()

    if args.dashboard_only:
        _serve_dashboard(args.dashboard_port)
        return

    all_feedbacks = []
    all_run_ids = []

    for iteration in range(args.loop):
        if args.loop > 1:
            print(f"\n--- Iteration {iteration + 1}/{args.loop} ---")

        for persona_num in range(args.personas):
            if args.personas > 1:
                print(f"\n--- Persona {persona_num + 1}/{args.personas} ---")

            run_id, report, feedback = run_single(
                mode=args.mode,
                max_swipes=args.max_swipes,
            )
            _print_summary(report, feedback)
            all_feedbacks.append(feedback)
            all_run_ids.append(run_id)

    # Publish all runs to dashboard (manifest + data/latest/)
    _publish_dashboard(all_run_ids)

    if args.auto_fix:
        # Output structured feedback for orchestrator consumption
        print("\n--- AUTO-FIX FEEDBACK ---")
        print(json.dumps(all_feedbacks, indent=2))

    # Summary across all runs
    if len(all_feedbacks) > 1:
        total_errors = sum(len(f.get('errors', [])) for f in all_feedbacks)
        total_perf = sum(len(f.get('performance_issues', [])) for f in all_feedbacks)
        passes = sum(1 for f in all_feedbacks if f.get('status') == 'pass')
        print(f"\n  Overall: {passes}/{len(all_feedbacks)} passed, {total_errors} errors, {total_perf} perf issues")


if __name__ == '__main__':
    main()
