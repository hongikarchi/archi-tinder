"""axis_scores.py — 건축물 ID 리스트 → 5축 점수 계산.

form/scale/energy/tradition: style + atmosphere 태그를 TagAxisWeight 테이블에서
조회해 매칭된 weight의 평균을 낸다 (매칭 없으면 0.0).

materiality: TagAxisWeight을 쓰지 않고 material_visual 문자열을 단어 규칙으로
직접 분류한다 (natural=-1.0 / man-made=+1.0). glass는 두 목록에 없어 항상
제외되고, 양쪽 다 매치되는 혼합 자재 문구(예: "wood-textured concrete")는
스킵한다. 좋아요한 건물 전체의 분류된 자재 문자열 평균, 없으면 0.0.
(2026-09-27 리튠: materiality를 스타일/분위기 태그가 아닌 자재 자체로 계산.)
"""
import re

from django.db import connections

from ..models import TagAxisWeight

AXES = ['form', 'materiality', 'scale', 'energy', 'tradition']

# TagAxisWeight 기반으로 평균을 내는 축 (materiality는 제외 — 자재 단어 규칙으로 별도 계산)
CATEGORICAL_AXES = ['form', 'scale', 'energy', 'tradition']

# ── materiality 단어 규칙 (case-insensitive, word-boundary) ────────────────
# 자연 재료 (-1.0). 목록을 늘리거나 줄일 때는 여기만 수정하면 된다.
NATURAL_MATERIAL_WORDS = [
    r'wood\w*', r'timber', r'oak', r'pine', r'cedar', r'larch', r'walnut',
    r'birch', r'bamboo', r'cork', r'plywood', r'stone', r'marble', r'granite',
    r'limestone', r'sandstone', r'travertine', r'slate', r'rock', r'brick\w*',
    r'terracotta', r'clay', r'earth', r'adobe', r'thatch', r'straw', r'masonry',
]

# 인공 재료 (+1.0). glass는 의도적으로 제외되어 있다 (절대 집계하지 않음).
MANMADE_MATERIAL_WORDS = [
    r'concrete', r'cement', r'steel', r'metal\w*', r'iron', r'aluminum',
    r'aluminium', r'polycarbonate', r'zinc', r'copper', r'brass', r'bronze',
    r'composite', r'resin', r'plastic', r'acrylic', r'fiberglass', r'corten',
    r'cor-ten', r'mirrors?',
]

_NATURAL_MATERIAL_RE = re.compile(
    r'\b(?:' + '|'.join(NATURAL_MATERIAL_WORDS) + r')\b', re.IGNORECASE
)
_MANMADE_MATERIAL_RE = re.compile(
    r'\b(?:' + '|'.join(MANMADE_MATERIAL_WORDS) + r')\b', re.IGNORECASE
)


def _classify_material(material_str):
    """단일 material_visual 문자열 -> -1.0(natural) / +1.0(man-made) / None(skip).

    - glass는 두 목록에 없으므로 항상 skip.
    - 양쪽 다 매치되면(혼합 자재 문구) skip.
    - 둘 중 하나만 매치되면 해당 극성을 반환.
    - 둘 다 매치 안 되면(water, vegetation, plaster, tile, paint, fabric...) skip.
    """
    if not material_str:
        return None
    is_natural = bool(_NATURAL_MATERIAL_RE.search(material_str))
    is_manmade = bool(_MANMADE_MATERIAL_RE.search(material_str))
    if is_natural and is_manmade:
        return None
    if is_natural:
        return -1.0
    if is_manmade:
        return 1.0
    return None


def _mean_categorical_axes(tags, weight_map):
    """tags: style/atmosphere 문자열 리스트. weight_map: {(tag, axis): weight}.
    반환: CATEGORICAL_AXES 각각의 매칭된 weight 평균 (매칭 없으면 0.0)."""
    sums = {axis: 0.0 for axis in CATEGORICAL_AXES}
    counts = {axis: 0 for axis in CATEGORICAL_AXES}
    for tag in tags:
        for axis in CATEGORICAL_AXES:
            w = weight_map.get((tag, axis))
            if w is not None:
                sums[axis] += w
                counts[axis] += 1
    return {
        axis: (sums[axis] / counts[axis]) if counts[axis] > 0 else 0.0
        for axis in CATEGORICAL_AXES
    }


def _mean_materiality(material_visual_lists):
    """material_visual_lists: 건물별 material_visual 리스트의 리스트.
    반환: 분류된 ±1.0 값들의 평균 (하나도 없으면 0.0)."""
    scores = []
    for materials in material_visual_lists:
        if not isinstance(materials, list):
            continue
        for material_str in materials:
            classified = _classify_material(material_str)
            if classified is not None:
                scores.append(classified)
    return sum(scores) / len(scores) if scores else 0.0


def compute_axis_scores(building_ids: list) -> dict:
    """
    building_ids: canonical_bld_id 리스트
    반환: {"form": float, "materiality": float, "scale": float, "energy": float, "tradition": float}
    form/scale/energy/tradition = style+atmosphere 태그의 TagAxisWeight 평균.
    materiality = material_visual 단어 규칙 분류 평균.
    매핑/분류 데이터 없으면 해당 축은 0.0.
    """
    if not building_ids:
        return {axis: 0.0 for axis in AXES}

    # buildings DB에서 style, atmosphere, material_visual 배치 조회
    with connections['buildings'].cursor() as cur:
        cur.execute(
            """
            SELECT style, atmosphere, material_visual
            FROM canonical_v2_buildings
            WHERE canonical_bld_id = ANY(%s)
              AND is_publishable = true
            """,
            [building_ids],
        )
        rows = cur.fetchall()

    # 태그 수집 (style/atmosphere만 -- material_visual은 TagAxisWeight 조회에 쓰지 않음)
    tags = []
    material_visual_lists = []
    for style, atmosphere, material_visual in rows:
        if style:
            tags.append(style)
        if atmosphere:
            tags.append(atmosphere)
        material_visual_lists.append(material_visual)

    # TagAxisWeight 일괄 조회 (CATEGORICAL_AXES만)
    weight_map = {}  # (tag, axis) -> weight
    if tags:
        weights_qs = TagAxisWeight.objects.filter(
            tag__in=tags, axis__in=CATEGORICAL_AXES,
        ).values('tag', 'axis', 'weight')
        for row in weights_qs:
            weight_map[(row['tag'], row['axis'])] = row['weight']

    categorical = _mean_categorical_axes(tags, weight_map)
    materiality = _mean_materiality(material_visual_lists)

    scores = dict(categorical)
    scores['materiality'] = materiality

    return {axis: round(scores[axis], 4) for axis in AXES}
