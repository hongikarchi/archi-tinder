"""
engine_vecmath.py -- Pure vector / numpy math helpers.

Extracted from engine.py (FULL-REFACTOR-1). No DB access, no Django cache,
no RC reads, no engine imports. Safe to import from any sibling or test.
"""
import math

import numpy as np


def _finite_unit_vector(raw_vec):
    """Return a finite 384-dim vector, normalized when possible."""
    vec = np.asarray(raw_vec, dtype=np.float64)
    if vec.shape != (384,):
        return None
    if not np.isfinite(vec).all():
        return None
    norm = float(np.linalg.norm(vec))
    if not math.isfinite(norm) or norm <= 0:
        return vec
    return vec / norm


def _parse_embedding_text(raw):
    try:
        return _finite_unit_vector(np.fromstring(raw.strip('[]'), sep=',', dtype=np.float64))
    except (AttributeError, ValueError):
        return None


def _cosine_sim_matrix(left, right):
    """Small-matrix cosine similarity without noisy BLAS overflow warnings."""
    sim = np.einsum('ij,kj->ik', left, right, optimize=True)
    return np.nan_to_num(sim, nan=0.0, posinf=0.0, neginf=0.0)


def _silenced_kmeans_fit(kmeans, X, sample_weight=None):
    """Run kmeans.fit silencing sklearn's matmul divide-by-zero RuntimeWarning.

    The warning fires inside sklearn's KMeans centroid normalization
    (sklearn/utils/extmath.py matmul) on high-dim unit-norm vectors. It is
    sklearn-internal noise — does NOT affect cluster centroid correctness.
    BACK-RECOMMEND-2.
    """
    with np.errstate(divide='ignore', invalid='ignore', over='ignore'):
        kmeans.fit(X, sample_weight=sample_weight)


def _vec_to_pg(vec):
    """Convert Python list of floats to pgvector literal string '[1,2,3]'."""
    cleaned = [0.0 if (math.isnan(v) or math.isinf(v)) else v for v in vec]
    return '[' + ','.join(str(v) for v in cleaned) + ']'


def _normalize(vec):
    """L2-normalize a list of floats. Returns list."""
    mag = math.sqrt(sum(v * v for v in vec))
    if mag == 0:
        return vec
    return [v / mag for v in vec]
