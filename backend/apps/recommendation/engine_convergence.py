"""
engine_convergence.py -- Convergence / confidence / recency math.

Extracted from engine.py (FULL-REFACTOR-1). All threshold / window values are
taken as function arguments — no RC reads, no DB, no engine imports.
Depends only on engine_vecmath for _finite_unit_vector.
"""
import math

import numpy as np

from .engine_vecmath import _finite_unit_vector


def _apply_recency_weights(like_vectors, round_num, gamma):
    """
    Apply recency weights to like vectors.
    Returns list of (np.array(embedding), weight)
    """
    weighted_vecs = []
    for entry in like_vectors:
        embedding = _finite_unit_vector(entry['embedding'])
        if embedding is None:
            continue
        entry_round = entry['round']
        weight = math.exp(-gamma * max(0, round_num - entry_round))
        weighted_vecs.append((embedding, weight))
    return weighted_vecs


def _weighted_centroid(weighted_vecs):
    """
    Compute weighted centroid and L2-normalize the result.
    weighted_vecs is list of (np.array, weight)
    Returns np.ndarray
    """
    if not weighted_vecs:
        return np.zeros(384)  # Default embedding dimension

    total_weight = sum(weight for _, weight in weighted_vecs)
    if total_weight == 0:
        total_weight = 1

    weighted_sum = np.zeros_like(weighted_vecs[0][0])
    for vec, weight in weighted_vecs:
        weighted_sum += weight * vec

    centroid = weighted_sum / total_weight

    # L2 normalize
    norm = np.linalg.norm(centroid)
    if norm > 0:
        centroid = centroid / norm

    return centroid


def compute_convergence(current_pref, previous_pref):
    """
    Compute delta-V between current and previous preference vectors.
    Returns float or None if either vector is empty.
    """
    if not current_pref or not previous_pref:
        return None

    current = np.array(current_pref)
    previous = np.array(previous_pref)
    delta_v = float(np.linalg.norm(current - previous))
    return delta_v


def _recent_like_count(recent_actions, window):
    if recent_actions is None:
        return None
    return sum(1 for action in list(recent_actions)[-window:] if action == 'like')


def check_convergence(history, threshold, window=3, recent_actions=None, min_recent_likes=0):
    """
    Check if convergence has been reached based on moving average.
    Returns bool
    """
    if len(history) < window:
        return False
    if min_recent_likes > 0:
        recent_likes = _recent_like_count(recent_actions, window)
        if recent_likes is not None and recent_likes < min_recent_likes:
            return False

    moving_avg = np.mean(history[-window:])
    return bool(moving_avg < threshold)


def compute_confidence(history, threshold, window=3, recent_actions=None, min_recent_likes=0):
    """
    Compute the user-facing confidence value (Spec C-1 통합안 1).

    Formula (Investigation 13): confidence = max(0, 1 - avg(last `window` Δv) / threshold).
    Returns float in [0, 1] when len(history) >= window. Returns None otherwise
    (Investigation 13 recommendation: skeleton/hide-bar semantic for the user-facing UI;
    frontend treats null as "not enough data yet").

    Spec rename note: spec text calls `threshold` ε_init or ε_threshold (Investigation
    13 §Naming drift recommended ε_threshold). Code uses settings.RECOMMENDATION
    'convergence_threshold' (the same value, 0.08 in production); pass that to this
    function. The threshold is shared with check_convergence; informational vs decisional
    signals at different thresholds is intentional (bar reaches 1.0 at Δv=0; phase
    transition fires at avg<threshold mid-bar).

    Edge cases per Investigation 13:
    - n < window: return None (caller hides bar).
    - All Δv = 0: returns 1.0 (vanishingly rare in practice).
    - Single Δv spike: bar pins to 0 for `window` rounds until spike slides out
      (intentional -- centroid jump = real instability).
    - threshold = 0: defended via max(threshold, 1e-6) to avoid div-by-zero.
    """
    if len(history) < window:
        return None
    if min_recent_likes > 0:
        recent_likes = _recent_like_count(recent_actions, window)
        if recent_likes is not None and recent_likes < min_recent_likes:
            return None
    safe_threshold = max(float(threshold), 1e-6)
    avg = sum(history[-window:]) / window
    return max(0.0, 1.0 - avg / safe_threshold)
