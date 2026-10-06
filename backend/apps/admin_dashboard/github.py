"""GitHub REST lookups for the deploy/CI panel (public repo; token optional).

Two calls total (compare main...develop + latest workflow run per branch x2 = 3 HTTP
requests worst case; compare covers both head SHAs and ahead_by). The whole result is
cached 15 minutes by the caller. Any failure degrades to nulls + an ``error`` string.
"""
import logging

import requests
from django.conf import settings

logger = logging.getLogger('apps.admin_dashboard')

_API = 'https://api.github.com'
_TIMEOUT = 5


def _headers():
    h = {'Accept': 'application/vnd.github+json', 'X-GitHub-Api-Version': '2022-11-28'}
    token = getattr(settings, 'GITHUB_TOKEN', '')
    if token:
        h['Authorization'] = f'Bearer {token}'
    return h


def _get(path, params=None):
    resp = requests.get(f'{_API}{path}', headers=_headers(), params=params, timeout=_TIMEOUT)
    resp.raise_for_status()
    return resp.json()


def _latest_run(repo, branch):
    data = _get(f'/repos/{repo}/actions/runs', {'branch': branch, 'per_page': 1})
    runs = data.get('workflow_runs') or []
    if not runs:
        return None
    r = runs[0]
    return {
        'conclusion': r.get('conclusion'),
        'status': r.get('status'),
        'html_url': r.get('html_url'),
        'created_at': r.get('created_at'),
    }


def fetch_github_state():
    """Return {main_sha, develop_sha, develop_ahead_by, ci:{develop,main}, error}.

    Each independent sub-lookup fails on its own so a partial outage still yields
    whatever succeeded; ``error`` joins the failures (None when all succeeded).
    """
    repo = getattr(settings, 'GITHUB_REPO', 'hongikarchi/archi-tinder')
    out = {
        'main_sha': None, 'develop_sha': None, 'develop_ahead_by': None,
        'ci': {'develop': None, 'main': None}, 'error': None,
    }
    errors = []

    try:
        cmp_ = _get(f'/repos/{repo}/compare/main...develop')
        out['main_sha'] = (cmp_.get('base_commit') or {}).get('sha')
        commits = cmp_.get('commits') or []
        if commits:
            out['develop_sha'] = commits[-1].get('sha')  # oldest-first list -> last = develop head
        elif cmp_.get('status') == 'identical':
            out['develop_sha'] = out['main_sha']
        # else (develop behind main): head not derivable from this one call -> None
        out['develop_ahead_by'] = cmp_.get('ahead_by')
    except Exception as exc:  # network, HTTP status, JSON -- all degrade to null
        logger.warning('github compare failed: %s', exc)
        errors.append(f'compare: {type(exc).__name__}')

    for branch in ('develop', 'main'):
        try:
            out['ci'][branch] = _latest_run(repo, branch)
        except Exception as exc:
            logger.warning('github runs(%s) failed: %s', branch, exc)
            errors.append(f'runs({branch}): {type(exc).__name__}')

    if errors:
        out['error'] = '; '.join(errors)
    return out
