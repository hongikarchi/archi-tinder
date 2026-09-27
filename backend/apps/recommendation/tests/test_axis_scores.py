"""
test_axis_scores.py — persona-report taste spectrum retune (2026-09-27).

Coverage:
  - _classify_material: natural / man-made / glass-excluded / mixed-skipped /
    non-material-skipped / case-insensitive, incl. 'larch wood' -> natural,
    'metal cladding' -> man-made, 'rammed earth' -> natural.
  - _mean_materiality: mean of classified ±1.0 over all liked buildings'
    material_visual strings; None when none classify (no evidence).
  - _mean_categorical_axes: pure weight-averaging helper (form/scale/energy/
    tradition), None when no match (no evidence).
  - compute_axis_scores: style/atmosphere feed the TagAxisWeight lookup,
    material_visual does NOT (even when a material string happens to match a
    seeded tag name) -- materiality comes only from the word-rule classifier.
  - Empty building_ids / no rows / no tags -> every axis None (JSON null),
    distinguishing "no evidence" from a real computed 0.0 (evidence exists,
    signs cancel out).

No real Postgres round-trip -- connections['buildings'].cursor() is mocked;
TagAxisWeight rows use the real (sqlite in-memory) ORM via the `db` fixture.
"""
from unittest.mock import MagicMock, patch

import pytest

from apps.recommendation.services.axis_scores import (
    AXES,
    _classify_material,
    _mean_categorical_axes,
    _mean_materiality,
    compute_axis_scores,
)
from apps.recommendation.models import TagAxisWeight


# ── _classify_material ──────────────────────────────────────────────────────

class TestClassifyMaterial:

    @pytest.mark.parametrize('material_str', [
        'Wood', 'wood', 'Timber', 'Oak', 'Pine', 'Cedar', 'Larch', 'Walnut',
        'Birch', 'Bamboo', 'Cork', 'Plywood', 'Stone', 'Marble', 'Granite',
        'Limestone', 'Sandstone', 'Travertine', 'Slate', 'Rock', 'Brick',
        'Terracotta', 'Clay', 'Earth', 'Adobe', 'Thatch', 'Straw', 'Masonry',
    ])
    def test_natural_materials(self, material_str):
        assert _classify_material(material_str) == -1.0

    @pytest.mark.parametrize('material_str', [
        'Concrete', 'Cement', 'Steel', 'Iron', 'Aluminum', 'Aluminium',
        'Polycarbonate', 'Zinc', 'Copper', 'Brass', 'Bronze', 'Composite',
        'Resin', 'Plastic', 'Acrylic', 'Fiberglass', 'Corten', 'Cor-Ten',
        'Mirror', 'Mirrors',
    ])
    def test_manmade_materials(self, material_str):
        assert _classify_material(material_str) == 1.0

    def test_glass_always_excluded(self):
        assert _classify_material('Glass') is None
        assert _classify_material('glass') is None
        assert _classify_material('Structural glass facade') is None

    @pytest.mark.parametrize('material_str', [
        'concrete brick',
        'wood-textured concrete',
        'steel and stone',
    ])
    def test_mixed_material_strings_skipped(self, material_str):
        assert _classify_material(material_str) is None

    @pytest.mark.parametrize('material_str', [
        'Water', 'Vegetation', 'Plaster', 'Tile', 'Paint', 'Fabric', '', None,
    ])
    def test_non_material_strings_skipped(self, material_str):
        assert _classify_material(material_str) is None

    def test_case_insensitive(self):
        assert _classify_material('WOOD') == -1.0
        assert _classify_material('sTeEl') == 1.0

    def test_larch_wood_is_natural(self):
        assert _classify_material('larch wood') == -1.0

    def test_metal_cladding_is_manmade(self):
        assert _classify_material('metal cladding') == 1.0

    def test_rammed_earth_is_natural(self):
        assert _classify_material('rammed earth') == -1.0

    def test_word_boundary_does_not_false_positive(self):
        # 'oakland' contains 'oak' but should not match as a whole-word hit
        # against unrelated compound words that aren't material vocabulary.
        assert _classify_material('oakland avenue') is None


# ── _mean_materiality ────────────────────────────────────────────────────────

class TestMeanMateriality:

    def test_empty_list_returns_none(self):
        assert _mean_materiality([]) is None

    def test_no_classifiable_strings_returns_none(self):
        assert _mean_materiality([['Water', 'Glass', 'Plaster'], None, []]) is None

    def test_mean_of_classified_values(self):
        # 2 natural (-1.0 each), 1 man-made (+1.0) -> mean = -1/3
        result = _mean_materiality([['Wood', 'Stone'], ['Steel'], ['Glass']])
        assert result == pytest.approx(-1.0 / 3.0)

    def test_non_list_entries_ignored(self):
        assert _mean_materiality([None, 'not-a-list', ['Wood']]) == -1.0

    def test_evidence_cancels_to_real_zero(self):
        # 1 natural (-1.0), 1 man-made (+1.0) -> real computed 0.0, NOT None,
        # since evidence exists (the signs just cancel out).
        result = _mean_materiality([['Wood'], ['Steel']])
        assert result == 0.0
        assert result is not None


# ── _mean_categorical_axes ──────────────────────────────────────────────────

class TestMeanCategoricalAxes:

    def test_no_match_returns_all_none(self):
        result = _mean_categorical_axes(['Unknown Tag'], {})
        assert result == {'form': None, 'scale': None, 'energy': None, 'tradition': None}

    def test_mean_of_matched_weights(self):
        weight_map = {
            ('Modernist', 'form'): 1.0,
            ('Minimalist', 'form'): 0.9,
            ('Intimate', 'scale'): -1.0,
        }
        result = _mean_categorical_axes(['Modernist', 'Minimalist', 'Intimate'], weight_map)
        assert result['form'] == pytest.approx(0.95)
        assert result['scale'] == pytest.approx(-1.0)
        # energy/tradition: no matching tag -> no evidence -> None, not 0.0.
        assert result['energy'] is None
        assert result['tradition'] is None

    def test_evidence_cancels_to_real_zero(self):
        # form: 'Modernist' (+1.0) and 'Anti-Modernist' (-1.0) cancel out to a
        # real computed 0.0 -- evidence exists, so this must NOT be None.
        weight_map = {
            ('Modernist', 'form'): 1.0,
            ('Anti-Modernist', 'form'): -1.0,
        }
        result = _mean_categorical_axes(['Modernist', 'Anti-Modernist'], weight_map)
        assert result['form'] == 0.0
        assert result['form'] is not None


# ── compute_axis_scores ──────────────────────────────────────────────────────

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


@pytest.mark.django_db
class TestComputeAxisScores:

    def test_empty_building_ids_returns_all_none(self):
        result = compute_axis_scores([])
        assert result == {axis: None for axis in AXES}

    def test_style_atmosphere_feed_lookup_material_visual_does_not(self):
        """A material_visual string that happens to equal a seeded tag name
        must NOT be picked up by the TagAxisWeight lookup -- only style /
        atmosphere feed that lookup now."""
        TagAxisWeight.objects.create(tag='Modernist', axis='form', weight=1.0)
        # Seed a decoy row keyed on a material-looking tag name + a
        # non-materiality axis, to prove material_visual strings never
        # reach the TagAxisWeight lookup at all.
        TagAxisWeight.objects.create(tag='Concrete', axis='form', weight=-1.0)

        rows = [
            ('Modernist', None, ['Concrete', 'Wood']),
        ]
        mock_connections = _connections_mock(_cursor_mock(rows))
        with patch('apps.recommendation.services.axis_scores.connections', mock_connections):
            result = compute_axis_scores(['bld_000001'])

        # form: only 'Modernist' (style) matched -> 1.0, NOT averaged with
        # the 'Concrete' decoy row that would drag it toward -1.0/0.0.
        assert result['form'] == 1.0
        # materiality: word-rule classification of material_visual only
        # ('Concrete' -> +1.0, 'Wood' -> -1.0) -> real computed mean 0.0
        # (evidence exists, signs cancel -- must be 0.0, not None).
        assert result['materiality'] == 0.0
        assert result['materiality'] is not None
        # scale/energy/tradition: no style/atmosphere tag touched these axes
        # at all -> no evidence -> None.
        assert result['scale'] is None
        assert result['energy'] is None
        assert result['tradition'] is None

    def test_full_row_all_axes(self):
        TagAxisWeight.objects.create(tag='Minimalist', axis='form', weight=0.9)
        TagAxisWeight.objects.create(tag='Serene', axis='energy', weight=-1.0)
        TagAxisWeight.objects.create(tag='Monumental', axis='scale', weight=1.0)
        TagAxisWeight.objects.create(tag='Futuristic', axis='tradition', weight=0.8)

        rows = [
            ('Minimalist', 'Serene', ['Steel', 'Glass']),
            (None, 'Monumental', ['Larch wood']),
        ]
        mock_connections = _connections_mock(_cursor_mock(rows))
        with patch('apps.recommendation.services.axis_scores.connections', mock_connections):
            result = compute_axis_scores(['bld_000001', 'bld_000002'])

        assert result['form'] == 0.9
        assert result['energy'] == -1.0
        assert result['scale'] == 1.0
        # tradition: no style/atmosphere tag in these rows matched a
        # 'tradition' weight -> no evidence -> None (Futuristic was seeded
        # but never appears in the rows).
        assert result['tradition'] is None
        # materiality: Steel (+1.0), Glass (excluded), Larch wood (-1.0) ->
        # real computed mean 0.0 (evidence exists, signs cancel).
        assert result['materiality'] == 0.0
        assert result['materiality'] is not None

    def test_no_rows_returns_all_none(self):
        mock_connections = _connections_mock(_cursor_mock([]))
        with patch('apps.recommendation.services.axis_scores.connections', mock_connections):
            result = compute_axis_scores(['bld_missing'])
        assert result == {axis: None for axis in AXES}

    def test_evidence_on_one_axis_none_on_others(self):
        """style/atmosphere give evidence for 'form' only; material_visual
        gives no classifiable evidence -> form is a real value, every other
        axis (including materiality) is None."""
        TagAxisWeight.objects.create(tag='Brutalist', axis='form', weight=1.0)

        rows = [
            ('Brutalist', None, ['Water', 'Glass', 'Plaster']),
        ]
        mock_connections = _connections_mock(_cursor_mock(rows))
        with patch('apps.recommendation.services.axis_scores.connections', mock_connections):
            result = compute_axis_scores(['bld_000003'])

        assert result['form'] == 1.0
        assert result['scale'] is None
        assert result['energy'] is None
        assert result['tradition'] is None
        assert result['materiality'] is None
