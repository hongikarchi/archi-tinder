"""
test_axis_scores.py — FULL-PERSONA-SPECTRUM (2026-09-27) embedding-projection
axis scoring.

Coverage:
  - compute_axis_scores: clipped-normalized-projection math, dots (n<=3 =
    all scores sorted, n>3 = 25/50/75 percentiles), iqr/confidence formula,
    n==0 (no parseable embeddings) -> every axis None, empty building_ids ->
    every axis None, missing axis_directions.json -> every axis None.

2026-09-28: recompute-on-read (ensure_axis_scores / _is_current_axis_shape)
was removed -- stored axis_scores (legacy or current shape) is now shown
as-is on read; only report generate/regenerate calls compute_axis_scores.
See test_report_cache.py / test_phase13_board.py for the read-path
regression coverage.

Pure/unit style throughout: connections['buildings'].cursor() and
_load_directions()/_parse_embedding_text are mocked -- no real Postgres
round-trip, no Django DB needed.
"""
from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from apps.recommendation.services.axis_scores import AXES, compute_axis_scores


# ── shared fixtures/helpers ──────────────────────────────────────────────────

def _cursor_mock(fetchall_rows):
    cur = MagicMock()
    cur.__enter__ = lambda s: s
    cur.__exit__ = MagicMock(return_value=False)
    cur.fetchall.return_value = fetchall_rows
    return cur


def _connections_mock(cursor):
    conn = MagicMock()
    conn.cursor.return_value = cursor
    connections = MagicMock()
    connections.__getitem__.return_value = conn
    return connections


# Identity-ish directions: lo=-1, hi=1 -> normalized = dot itself (before
# clipping), which keeps the expected numbers trivial to hand-compute.
FAKE_DIRECTIONS = {
    axis: {'direction': np.array([1.0] + [0.0] * 383), 'lo': -1.0, 'hi': 1.0}
    for axis in AXES
}


def _rows_for(dot_values):
    """Fake (canonical_bld_id, embedding_text) rows -- the text payload just
    encodes the desired first-coordinate value; _fake_parse below decodes it."""
    return [(f'bld_{i:06d}', f'raw:{v}') for i, v in enumerate(dot_values)]


def _fake_parse(raw):
    """'raw:0.6' -> np.array([0.6, 0, 0, ..., 0]) (384-dim). Paired with the
    FAKE_DIRECTIONS e0 direction, dot(vec, direction) == the encoded value
    exactly -- no normalization surprises to account for in expected values."""
    v = float(raw.split(':')[1])
    vec = np.zeros(384)
    vec[0] = v
    return vec


def _patched(rows, directions=FAKE_DIRECTIONS, parse=_fake_parse):
    mock_conn = _connections_mock(_cursor_mock(rows))
    return (
        patch('apps.recommendation.services.axis_scores._load_directions', return_value=directions),
        patch('apps.recommendation.services.axis_scores.connections', mock_conn),
        patch('apps.recommendation.services.axis_scores._parse_embedding_text', side_effect=parse),
    )


# ── compute_axis_scores: edge cases ─────────────────────────────────────────

class TestComputeAxisScoresEdgeCases:

    def test_empty_building_ids_returns_all_none(self):
        assert compute_axis_scores([]) == {axis: None for axis in AXES}

    def test_missing_directions_file_returns_all_none(self):
        mock_conn = _connections_mock(_cursor_mock([]))
        with patch('apps.recommendation.services.axis_scores._load_directions', return_value=None), \
             patch('apps.recommendation.services.axis_scores.connections', mock_conn):
            result = compute_axis_scores(['bld_000001'])
        assert result == {axis: None for axis in AXES}

    def test_no_rows_returns_all_none(self):
        p1, p2, p3 = _patched(rows=[])
        with p1, p2, p3:
            result = compute_axis_scores(['bld_missing'])
        assert result == {axis: None for axis in AXES}

    def test_unparseable_embeddings_return_all_none(self):
        """Rows come back, but every embedding fails to parse -- n stays 0."""
        rows = [('bld_000001', 'not-a-vector'), ('bld_000002', 'also-garbage')]
        mock_conn = _connections_mock(_cursor_mock(rows))
        with patch('apps.recommendation.services.axis_scores._load_directions', return_value=FAKE_DIRECTIONS), \
             patch('apps.recommendation.services.axis_scores.connections', mock_conn):
            # real _parse_embedding_text (not mocked) -- garbage text has no
            # numeric content, so np.fromstring yields a non-384 shaped array.
            result = compute_axis_scores(['bld_000001', 'bld_000002'])
        assert result == {axis: None for axis in AXES}


# ── compute_axis_scores: scoring / clipping math ────────────────────────────

class TestComputeAxisScoresMath:

    def test_score_is_mean_of_clipped_normalized_projections(self):
        # lo=-1, hi=1 -> normalized == dot exactly; 2.0/-2.0 exceed the
        # [-1, 1] range and must clip before averaging.
        rows = _rows_for([0.5, 2.0, -2.0])
        p1, p2, p3 = _patched(rows)
        with p1, p2, p3:
            result = compute_axis_scores(['bld_000000', 'bld_000001', 'bld_000002'])

        expected_mean = round((0.5 + 1.0 - 1.0) / 3, 4)
        for axis in AXES:
            assert result[axis]['n'] == 3
            assert result[axis]['score'] == pytest.approx(expected_mean)

    def test_dots_are_all_scores_sorted_when_n_le_3(self):
        rows = _rows_for([0.5, -1.0, 2.0])  # clips to [0.5, -1.0, 1.0]
        p1, p2, p3 = _patched(rows)
        with p1, p2, p3:
            result = compute_axis_scores(['bld_000000', 'bld_000001', 'bld_000002'])

        for axis in AXES:
            assert result[axis]['n'] == 3
            assert result[axis]['dots'] == [-1.0, 0.5, 1.0]

    def test_dots_are_quartiles_when_n_gt_3(self):
        rows = _rows_for([-1.0, -0.5, 0.5, 1.0])
        p1, p2, p3 = _patched(rows)
        with p1, p2, p3:
            result = compute_axis_scores([f'bld_{i:06d}' for i in range(4)])

        for axis in AXES:
            assert result[axis]['n'] == 4
            # numpy linear-interpolation percentiles of [-1.0, -0.5, 0.5, 1.0]
            expected = list(np.percentile([-1.0, -0.5, 0.5, 1.0], [25, 50, 75]))
            assert result[axis]['dots'] == [round(float(v), 4) for v in expected]

    def test_iqr_zero_and_confidence_one_when_scores_uniform_and_n_at_full(self):
        rows = _rows_for([0.2] * 5)  # RECOMMENDATION['axis_confidence_full_n'] default = 5
        p1, p2, p3 = _patched(rows)
        with p1, p2, p3:
            result = compute_axis_scores([f'bld_{i:06d}' for i in range(5)])

        for axis in AXES:
            assert result[axis]['n'] == 5
            assert result[axis]['iqr'] == 0.0
            assert result[axis]['confidence'] == 1.0
            assert result[axis]['score'] == pytest.approx(0.2)

    def test_confidence_scales_down_with_n_below_full_n(self):
        # n=2 (below default full_n=5), identical scores -> iqr=0, confidence = 2/5.
        rows = _rows_for([0.3, 0.3])
        p1, p2, p3 = _patched(rows)
        with p1, p2, p3:
            result = compute_axis_scores(['bld_000000', 'bld_000001'])

        for axis in AXES:
            assert result[axis]['n'] == 2
            assert result[axis]['iqr'] == 0.0
            assert result[axis]['confidence'] == pytest.approx(0.4)

    def test_iqr_defaults_to_one_and_confidence_zero_when_n_is_one(self):
        rows = _rows_for([0.7])
        p1, p2, p3 = _patched(rows)
        with p1, p2, p3:
            result = compute_axis_scores(['bld_000000'])

        for axis in AXES:
            assert result[axis]['n'] == 1
            assert result[axis]['iqr'] == 1.0
            assert result[axis]['confidence'] == 0.0

    def test_high_iqr_suppresses_confidence_even_at_full_n(self):
        # n=5 (at full_n), but scores are maximally spread -> large iqr drags
        # confidence toward 0 even though the n-ratio term is at its max (1).
        rows = _rows_for([-1.0, -1.0, 0.0, 1.0, 1.0])
        p1, p2, p3 = _patched(rows)
        with p1, p2, p3:
            result = compute_axis_scores([f'bld_{i:06d}' for i in range(5)])

        for axis in AXES:
            assert result[axis]['n'] == 5
            assert result[axis]['iqr'] > 0
            assert result[axis]['confidence'] < 1.0
            assert result[axis]['confidence'] == pytest.approx(
                min(5 / 5, 1) * max(0, 1 - result[axis]['iqr'])
            )
