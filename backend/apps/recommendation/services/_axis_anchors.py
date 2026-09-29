"""_axis_anchors.py — sentence anchors for the persona-report taste axes.

FULL-PERSONA-SPECTRUM (2026-09-27): per-building axis scores are computed as
an embedding projection onto a direction defined by these anchor sentence
pairs (neg pole = -1 = left label, pos pole = +1 = right label), NOT by a
tag/word lookup. This module is the SOLE place axis definitions live — edit
the sentences here to retune an axis, then re-run
`python manage.py build_axis_directions` to regenerate
backend/fixtures/axis_directions.json.

The `form` axis is intentionally absent: building embeddings carry weak
geometric-form signal, so there is currently no reliable way to score it
without a new data source (image embeddings, LLM shape-scoring, or a
Make-DB-sourced form field). See the 2026-09-27 plan discussion — options
were: (1) drop it for now [chosen], (2) ship it anyway at ~0.75 AUC,
(3) CLIP image embeddings, (4) Gemini shape-scoring on a sample first,
(5) ask Make DB for a form field, (6) keep the old tag-weight scoring.
Re-add a `form` entry here (+ re-run build_axis_directions) once one of
those options is validated.
"""

AXIS_ANCHORS = {
    'materiality': {
        'neg': [
            'A building made of natural materials: timber, wood, stone, brick, '
            'rammed earth and bamboo.',
            'Warm natural wood and stone construction with handmade brick and '
            'earthen textures.',
        ],
        'pos': [
            'A building made of industrial man-made materials: exposed concrete, '
            'steel, metal cladding and aluminum.',
            'Concrete and steel construction with metal panels and a machine-made '
            'industrial finish.',
        ],
    },
    'scale': {
        'neg': [
            'An intimate, cozy, small building at human scale with sheltered, '
            'snug, domestic spaces.',
            'A modest, cozy little space that feels warm, enclosed and personal.',
        ],
        'pos': [
            'A monumental, massive, imposing building of overwhelming grand scale '
            'that dominates its surroundings.',
            'A towering, colossal structure with vast, awe-inspiring monumental '
            'spaces.',
        ],
    },
    'energy': {
        'neg': [
            'A serene, calm, quiet and contemplative building with a tranquil, '
            'peaceful, meditative atmosphere.',
            'A restrained, still and understated space that feels silent and '
            'peaceful.',
        ],
        'pos': [
            'A dynamic, vibrant, playful building full of energy, movement, bold '
            'colors and expressive gestures.',
            'A lively, energetic, animated and joyful architecture with dramatic, '
            'exciting forms.',
        ],
    },
    'tradition': {
        'neg': [
            'A traditional, classical, historic building following vernacular '
            'heritage and time-honored craft.',
            'A building with classical columns, ornament and traditional local '
            'construction methods.',
        ],
        'pos': [
            'An experimental, innovative, futuristic building with cutting-edge '
            'avant-garde technology and unconventional design.',
            'A radically new, high-tech, computational and pioneering '
            'architecture.',
        ],
    },
}
