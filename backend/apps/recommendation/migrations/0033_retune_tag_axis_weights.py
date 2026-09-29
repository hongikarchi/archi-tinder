"""0033_retune_tag_axis_weights — persona-report taste spectrum retune.

Decided 2026-09-27. Replaces the 38-row TagAxisWeight seed (migration 0021,
from `backend/fixtures/tag_axis_weights.json`) with 16 rows across the same
5 axes MINUS materiality: `form`, `scale`, `energy`, `tradition`. Materiality
is no longer looked up via TagAxisWeight -- `services/axis_scores.py` now
computes it directly from `material_visual` word rules, so no materiality
rows are seeded here.

Rationale / methodology:
  - Definitional mapping: a tag maps to an axis only if the word itself
    implies the trait (e.g. "Parametric" definitionally implies computational/
    curvilinear form and a break from tradition; it does NOT definitionally
    imply a material, hence no materiality row).
  - Magnitudes: derived from description-keyword evidence density within the
    same side of the axis (how strongly/consistently the tag's descriptions
    use language for that pole), not from cross-axis correlation.
  - Evidence <=3pp (percentage points) was treated as noise and dropped:
    High-Tech on `tradition` and Deconstructivist on `tradition` both had
    <=3pp keyword evidence over the opposing pole and were cut rather than
    seeded with a token weight.
  - The fixture (`backend/fixtures/tag_axis_weights.json`) was updated to
    match these 16 rows so migration 0021 (fresh DB) and 0033 (existing DB)
    converge on the same seed state.

Reverse (unapply) restores the previous 38-row seed exactly, embedded below
as a constant (read once from the fixture's pre-retune contents at authoring
time -- NOT read from the fixture file at migration runtime, since the
fixture file itself was rewritten to the new 16 rows in this same change).
"""
from django.db import migrations

NEW_ROWS = [
    {'tag': 'Parametric', 'axis': 'form', 'weight': -1.0},
    {'tag': 'Organic', 'axis': 'form', 'weight': -1.0},
    {'tag': 'Deconstructivist', 'axis': 'form', 'weight': -0.9},
    {'tag': 'Modernist', 'axis': 'form', 'weight': 1.0},
    {'tag': 'Minimalist', 'axis': 'form', 'weight': 0.9},
    {'tag': 'Brutalist', 'axis': 'form', 'weight': 0.5},
    {'tag': 'Intimate', 'axis': 'scale', 'weight': -1.0},
    {'tag': 'Monumental', 'axis': 'scale', 'weight': 1.0},
    {'tag': 'Serene', 'axis': 'energy', 'weight': -1.0},
    {'tag': 'Contemplative', 'axis': 'energy', 'weight': -1.0},
    {'tag': 'Playful', 'axis': 'energy', 'weight': 1.0},
    {'tag': 'Dynamic', 'axis': 'energy', 'weight': 0.8},
    {'tag': 'Neo-Classical', 'axis': 'tradition', 'weight': -1.0},
    {'tag': 'Vernacular', 'axis': 'tradition', 'weight': -0.5},
    {'tag': 'Parametric', 'axis': 'tradition', 'weight': 1.0},
    {'tag': 'Futuristic', 'axis': 'tradition', 'weight': 0.8},
]

# The exact 38 rows seeded by migration 0021 (pre-retune contents of
# backend/fixtures/tag_axis_weights.json), embedded here so the reverse
# migration does not depend on the fixture file's current (post-retune)
# contents.
OLD_ROWS = [
    {'tag': 'Brutalist', 'axis': 'form', 'weight': 0.8},
    {'tag': 'Brutalist', 'axis': 'materiality', 'weight': 0.9},
    {'tag': 'High-Tech', 'axis': 'form', 'weight': 0.9},
    {'tag': 'High-Tech', 'axis': 'materiality', 'weight': 1.0},
    {'tag': 'High-Tech', 'axis': 'tradition', 'weight': 0.7},
    {'tag': 'Industrial', 'axis': 'form', 'weight': 0.7},
    {'tag': 'Industrial', 'axis': 'materiality', 'weight': 1.0},
    {'tag': 'Minimalist', 'axis': 'form', 'weight': 0.8},
    {'tag': 'Modernist', 'axis': 'form', 'weight': 0.6},
    {'tag': 'Deconstructivist', 'axis': 'form', 'weight': 0.3},
    {'tag': 'Deconstructivist', 'axis': 'tradition', 'weight': 1.0},
    {'tag': 'Parametric', 'axis': 'form', 'weight': -0.5},
    {'tag': 'Parametric', 'axis': 'materiality', 'weight': 0.3},
    {'tag': 'Parametric', 'axis': 'tradition', 'weight': 0.9},
    {'tag': 'Organic', 'axis': 'form', 'weight': -1.0},
    {'tag': 'Organic', 'axis': 'materiality', 'weight': -0.9},
    {'tag': 'Vernacular', 'axis': 'form', 'weight': -0.3},
    {'tag': 'Vernacular', 'axis': 'materiality', 'weight': -1.0},
    {'tag': 'Vernacular', 'axis': 'tradition', 'weight': -0.9},
    {'tag': 'Neo-Classical', 'axis': 'form', 'weight': 0.4},
    {'tag': 'Neo-Classical', 'axis': 'tradition', 'weight': -1.0},
    {'tag': 'Postmodern', 'axis': 'tradition', 'weight': 0.5},
    {'tag': 'Contemporary', 'axis': 'tradition', 'weight': 0.3},
    {'tag': 'Monumental', 'axis': 'scale', 'weight': 1.0},
    {'tag': 'Urban', 'axis': 'scale', 'weight': 0.5},
    {'tag': 'Urban', 'axis': 'energy', 'weight': 0.4},
    {'tag': 'Industrial', 'axis': 'scale', 'weight': 0.3},
    {'tag': 'Intimate', 'axis': 'scale', 'weight': -1.0},
    {'tag': 'Rustic', 'axis': 'scale', 'weight': -0.6},
    {'tag': 'Warm', 'axis': 'scale', 'weight': -0.4},
    {'tag': 'Dynamic', 'axis': 'energy', 'weight': 1.0},
    {'tag': 'Playful', 'axis': 'energy', 'weight': 0.8},
    {'tag': 'Futuristic', 'axis': 'energy', 'weight': 0.7},
    {'tag': 'Contemplative', 'axis': 'scale', 'weight': -0.3},
    {'tag': 'Contemplative', 'axis': 'energy', 'weight': -0.9},
    {'tag': 'Serene', 'axis': 'energy', 'weight': -1.0},
    {'tag': 'Raw', 'axis': 'scale', 'weight': 0.2},
    {'tag': 'Raw', 'axis': 'energy', 'weight': 0.3},
]


def _apply_retune(apps, schema_editor):
    TagAxisWeight = apps.get_model('recommendation', 'TagAxisWeight')
    TagAxisWeight.objects.all().delete()
    for row in NEW_ROWS:
        TagAxisWeight.objects.create(
            tag=row['tag'], axis=row['axis'], weight=row['weight'],
        )


def _revert_retune(apps, schema_editor):
    TagAxisWeight = apps.get_model('recommendation', 'TagAxisWeight')
    TagAxisWeight.objects.all().delete()
    for row in OLD_ROWS:
        TagAxisWeight.objects.create(
            tag=row['tag'], axis=row['axis'], weight=row['weight'],
        )


class Migration(migrations.Migration):

    dependencies = [
        ('recommendation', '0032_alter_sessionevent_event_type'),
    ]

    operations = [
        migrations.RunPython(_apply_retune, _revert_retune),
    ]
