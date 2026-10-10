"""
jev_client.py -- Thin HTTP client for the TypeSafe "System One" (JEV) API.

One POST per user message: `state` (context text) + `questions` (choice
questions, one per tag axis). Every failure mode collapses into JevUnavailable
so the recognizer can fall back to the local dictionary without caring why.

Never logs the API key; user text is logged only at DEBUG and truncated.
"""
import logging

import requests
from django.conf import settings

logger = logging.getLogger('apps.recommendation')


class JevUnavailable(Exception):
    """JEV could not produce a usable answer (no key, timeout, network, HTTP, bad JSON)."""


def call_jev(state, questions):
    """POST `state` + `questions` to JEV and return the `answers` dict.

    Returns {question_id: {'choice': str, 'confidence': float, 'probabilities': {...}}}.
    Raises JevUnavailable on any failure.
    """
    key = getattr(settings, 'TYPESAFE_API_KEY', '')
    if not key:
        raise JevUnavailable('TYPESAFE_API_KEY not configured')
    payload = {
        'state': state,
        'model': getattr(settings, 'JEV_MODEL', 'jev-latest'),
        'questions': questions,
    }
    logger.debug('JEV request state=%r (%d questions)', state[:80], len(questions))
    try:
        resp = requests.post(
            settings.JEV_API_URL,
            headers={'Authorization': f'Bearer {key}', 'Content-Type': 'application/json'},
            json=payload,
            timeout=settings.JEV_TIMEOUT_SECONDS,
        )
    except requests.Timeout as exc:
        raise JevUnavailable('JEV request timed out') from exc
    except requests.RequestException as exc:
        raise JevUnavailable(f'JEV network error: {type(exc).__name__}') from exc
    if resp.status_code != 200:
        raise JevUnavailable(f'JEV HTTP {resp.status_code}')
    try:
        data = resp.json()
    except ValueError as exc:
        raise JevUnavailable('JEV returned malformed JSON') from exc
    answers = data.get('answers') if isinstance(data, dict) else None
    if not isinstance(answers, dict):
        raise JevUnavailable('JEV response has no answers')
    return answers
