"""axis_scores.py — 건축물 ID 리스트 → 5축 점수 계산."""
from django.db import connections
from ..models import TagAxisWeight

AXES = ['form', 'materiality', 'scale', 'energy', 'tradition']


def compute_axis_scores(building_ids: list) -> dict:
    """
    building_ids: canonical_bld_id 리스트
    반환: {"form": float, "materiality": float, "scale": float, "energy": float, "tradition": float}
    각 축별 weight 평균. 매핑 데이터 없으면 0.0.
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

    # 태그 수집
    tags = []
    for style, atmosphere, material_visual in rows:
        if style:
            tags.append(style)
        if atmosphere:
            tags.append(atmosphere)
        if isinstance(material_visual, list):
            tags.extend(material_visual)

    if not tags:
        return {axis: 0.0 for axis in AXES}

    # TagAxisWeight 일괄 조회
    weights_qs = TagAxisWeight.objects.filter(tag__in=tags).values('tag', 'axis', 'weight')
    weight_map = {}  # (tag, axis) → weight
    for row in weights_qs:
        weight_map[(row['tag'], row['axis'])] = row['weight']

    # 축별 합산
    axis_sums = {axis: 0.0 for axis in AXES}
    axis_counts = {axis: 0 for axis in AXES}

    for tag in tags:
        for axis in AXES:
            w = weight_map.get((tag, axis))
            if w is not None:
                axis_sums[axis] += w
                axis_counts[axis] += 1

    return {
        axis: round(axis_sums[axis] / axis_counts[axis], 4) if axis_counts[axis] > 0 else 0.0
        for axis in AXES
    }
