#!/usr/bin/env python3
"""Measure backend endpoint p50/p95 latency against local dev server.

Usage:
    python tools/perf_measure.py --endpoint projects --runs 3
    python tools/perf_measure.py --endpoint sessions --runs 3 \
        --query "modern concrete museum"
    python tools/perf_measure.py --endpoint discovery --runs 5

Hits http://127.0.0.1:8001 (local Django runserver). Auth token is
fetched from the dev-login endpoint automatically using DEV_LOGIN_SECRET
env var (or pass --token to override).

Dev-login: POST /api/v1/auth/dev-login/ with {"secret": <DEV_LOGIN_SECRET>}
returns {"access", "refresh", "user"}.
"""
from __future__ import annotations

import argparse
import json
import os
import statistics
import sys
import time
from typing import Any

import urllib.request
import urllib.error

BASE = 'http://127.0.0.1:8001'


def _http(method: str, path: str, *, body: dict | None = None,
          token: str | None = None) -> tuple[int, dict, float]:
    url = f'{BASE}{path}'
    data = json.dumps(body).encode() if body is not None else None
    headers = {'Content-Type': 'application/json'}
    if token:
        headers['Authorization'] = f'Bearer {token}'
    req = urllib.request.Request(
        url, data=data, method=method, headers=headers
    )
    t0 = time.perf_counter()
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            payload = json.loads(resp.read() or b'{}')
            elapsed = (time.perf_counter() - t0) * 1000.0
            return resp.status, payload, elapsed
    except urllib.error.HTTPError as e:
        elapsed = (time.perf_counter() - t0) * 1000.0
        try:
            payload = json.loads(e.read() or b'{}')
        except Exception:
            payload = {}
        return e.code, payload, elapsed


def _get_token() -> str:
    secret = os.environ.get('DEV_LOGIN_SECRET', '')
    if not secret:
        raise SystemExit(
            'DEV_LOGIN_SECRET env var not set. '
            'Export it or pass --token with a valid JWT.'
        )
    status, payload, _ = _http(
        'POST', '/api/v1/auth/dev-login/', body={'secret': secret}
    )
    if status != 200 or 'access' not in payload:
        raise SystemExit(
            f'dev-login failed: status={status} payload={payload}'
        )
    return payload['access']


def measure_projects(token: str, runs: int) -> list[float]:
    times = []
    for _ in range(runs):
        _, _, ms = _http('GET', '/api/v1/projects/', token=token)
        times.append(ms)
    return times


def measure_sessions(token: str, runs: int, query: str) -> list[float]:
    times = []
    for i in range(runs):
        body = {'raw_query': f'{query} run-{i}'}
        _, _, ms = _http(
            'POST', '/api/v1/analysis/sessions/', body=body, token=token
        )
        times.append(ms)
    return times


def measure_discovery(token: str, runs: int) -> list[float]:
    # Prime once (cache warm), then measure
    _http('GET', '/api/v1/discovery/', token=token)
    times = []
    for _ in range(runs):
        _, _, ms = _http('GET', '/api/v1/discovery/', token=token)
        times.append(ms)
    return times


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument(
        '--endpoint', required=True,
        choices=['projects', 'sessions', 'discovery'],
    )
    p.add_argument('--runs', type=int, default=3)
    p.add_argument(
        '--query', default='modern concrete museum',
        help='search query for --endpoint sessions',
    )
    p.add_argument(
        '--token', default=None,
        help='override JWT (otherwise dev-login via DEV_LOGIN_SECRET)',
    )
    args = p.parse_args()

    token = args.token or _get_token()

    if args.endpoint == 'projects':
        times = measure_projects(token, args.runs)
    elif args.endpoint == 'sessions':
        times = measure_sessions(token, args.runs, args.query)
    else:
        times = measure_discovery(token, args.runs)

    summary: dict[str, Any] = {
        'endpoint': args.endpoint,
        'runs': [round(t, 1) for t in times],
        'p50_ms': round(statistics.median(times), 1),
        'p95_ms': round(
            sorted(times)[max(0, int(len(times) * 0.95) - 1)], 1
        ) if times else None,
        'min_ms': round(min(times), 1) if times else None,
        'max_ms': round(max(times), 1) if times else None,
    }
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == '__main__':
    sys.exit(main())
