"""axis_scores.py — 건축물 ID 리스트 → 4축 taste-spectrum 점수 계산.

FULL-PERSONA-SPECTRUM (2026-09-27): materiality/scale/energy/tradition은 이제
태그 가중치 평균이 아니라, 건물 임베딩을 anchor-sentence 방향(direction)에
투영(projection)해 계산한다. direction + 정규화 범위(lo/hi)는
services/_axis_anchors.py의 문장들로부터 `build_axis_directions` 커맨드가
한 번(빌드타임)에 만들어 backend/fixtures/axis_directions.json에 저장한 값을
그대로 읽어 쓴다 -- 요청마다 HuggingFace를 부르지 않는다.

`form` 축은 임베딩에 형태(geometry) 정보가 약해 당분간 제외한다
(services/_axis_anchors.py 상단 docstring 참고).

건물이 하나도 임베딩을 가지고 있지 않으면(n == 0) 모든 축이 None(JSON null)
-- "근거 없음"과 실제로 계산된 값을 구분한다.
"""
import hashlib
import json
import logging

import numpy as np
from django.conf import settings
from django.db import connections

from ..engine_vecmath import _parse_embedding_text
from ._axis_anchors import AXIS_ANCHORS

logger = logging.getLogger('apps.recommendation')

# 'form' 축은 제외 -- _axis_anchors.py 참고.
AXES = ['materiality', 'scale', 'energy', 'tradition']

_DIRECTIONS_PATH = settings.BASE_DIR / 'fixtures' / 'axis_directions.json'

# 모듈 레벨 캐시 -- 프로세스당 파일을 한 번만 읽는다. import 시점이 아니라
# 최초 호출 시점에 지연 로드한다(파일이 없어도 Django 기동 자체는 실패하지
# 않도록).
_directions_cache = None


def _anchors_sha256():
    """AXIS_ANCHORS의 안정적인 해시 -- axis_directions.json이 지금 코드의
    anchor 문장과 어긋났는지(재빌드가 필요한지) 감지하는 데 쓴다."""
    payload = json.dumps(AXIS_ANCHORS, sort_keys=True).encode('utf-8')
    return hashlib.sha256(payload).hexdigest()


def _load_directions():
    """backend/fixtures/axis_directions.json을 읽어 캐시한다.

    반환: {axis: {'direction': np.ndarray(384,), 'lo': float, 'hi': float}}.
    파일이 없거나 읽기/파싱에 실패하면 None -- 호출자는 "근거 없음"(모든 축
    None)으로 처리한다.
    """
    global _directions_cache
    if _directions_cache is not None:
        return _directions_cache

    try:
        with open(_DIRECTIONS_PATH, 'r', encoding='utf-8') as f:
            raw = json.load(f)
    except (OSError, ValueError) as exc:
        logger.error('axis_scores: failed to load %s: %s', _DIRECTIONS_PATH, exc)
        return None

    stored_sha = raw.get('anchors_sha256')
    current_sha = _anchors_sha256()
    if stored_sha != current_sha:
        logger.warning(
            'axis_scores: %s anchors_sha256=%s does not match current '
            'AXIS_ANCHORS=%s -- directions are stale. Re-run '
            '`python manage.py build_axis_directions`. Using the file as-is for now.',
            _DIRECTIONS_PATH, stored_sha, current_sha,
        )

    directions = {}
    for axis, payload in (raw.get('axes') or {}).items():
        directions[axis] = {
            'direction': np.asarray(payload['direction'], dtype=np.float64),
            'lo': float(payload['lo']),
            'hi': float(payload['hi']),
        }
    _directions_cache = directions
    return _directions_cache


def compute_axis_scores(building_ids: list) -> dict:
    """
    building_ids: canonical_bld_id 리스트.

    반환: {axis: None | {'score': float, 'dots': list[float], 'n': int,
                         'iqr': float, 'confidence': float}}
    axis는 materiality/scale/energy/tradition.

    - building_ids가 비었거나, axis_directions.json을 읽을 수 없거나,
      임베딩이 하나도 파싱되지 않으면(n == 0) 모든 축이 None.
    - 건물별 점수 = clip((e·direction - lo) / (hi - lo) * 2 - 1, -1, 1).
    - score = 건물별 점수의 평균.
    - dots = n <= 3이면 건물별 점수를 정렬한 전체 리스트, 아니면
      [25, 50, 75] 백분위수(numpy linear 보간).
    - iqr = n >= 2일 때 p75 - p25, 그 외 1.0(불확실성 최대로 취급).
    - confidence = min(n / RECOMMENDATION['axis_confidence_full_n'], 1) *
      max(0, 1 - iqr).
    - 모든 float은 소수 4자리로 round.
    """
    if not building_ids:
        return {axis: None for axis in AXES}

    directions = _load_directions()
    if not directions:
        return {axis: None for axis in AXES}

    with connections['buildings'].cursor() as cur:
        cur.execute(
            """
            SELECT canonical_bld_id, embedding::text
            FROM canonical_v2_buildings
            WHERE canonical_bld_id = ANY(%s)
              AND is_publishable = true
            """,
            [building_ids],
        )
        rows = cur.fetchall()

    vectors = []
    for _bld_id, emb_text in rows:
        vec = _parse_embedding_text(emb_text)
        if vec is not None:
            vectors.append(vec)

    n = len(vectors)
    if n == 0:
        return {axis: None for axis in AXES}

    rc = settings.RECOMMENDATION
    full_n = rc.get('axis_confidence_full_n', 5)

    result = {}
    for axis in AXES:
        axis_dir = directions.get(axis)
        if axis_dir is None:
            result[axis] = None
            continue

        direction = axis_dir['direction']
        lo, hi = axis_dir['lo'], axis_dir['hi']
        span = hi - lo

        raw_scores = []
        for vec in vectors:
            dot = float(np.dot(vec, direction))
            normalized = ((dot - lo) / span * 2 - 1) if span else 0.0
            raw_scores.append(max(-1.0, min(1.0, normalized)))

        scores_arr = np.asarray(raw_scores, dtype=np.float64)
        mean_score = float(np.mean(scores_arr))

        if n <= 3:
            dots = sorted(round(float(s), 4) for s in raw_scores)
        else:
            p25, p50, p75 = np.percentile(scores_arr, [25, 50, 75])
            dots = [round(float(p25), 4), round(float(p50), 4), round(float(p75), 4)]

        if n >= 2:
            p25_full, p75_full = np.percentile(scores_arr, [25, 75])
            iqr = float(p75_full - p25_full)
        else:
            iqr = 1.0

        confidence = min(n / full_n, 1.0) * max(0.0, 1.0 - iqr)

        result[axis] = {
            'score': round(mean_score, 4),
            'dots': dots,
            'n': n,
            'iqr': round(iqr, 4),
            'confidence': round(confidence, 4),
        }

    return result


def _is_current_axis_shape(axis_scores):
    """axis_scores가 현재(embedding-projection) 포맷인지 확인.

    현재 포맷: {axis: None | dict-with-'dots'} 인 4축(AXES) 딱 그 키셋.
    레거시 포맷(태그 가중치 시절): {axis: float|None}인 5축(form 포함) --
    값이 dict가 아니라 flat float/None이므로 걸러진다.
    """
    if not axis_scores or not isinstance(axis_scores, dict):
        return False
    if set(axis_scores.keys()) != set(AXES):
        return False
    for value in axis_scores.values():
        if value is not None and not (isinstance(value, dict) and 'dots' in value):
            return False
    return True


def ensure_axis_scores(project):
    """project.axis_scores가 없거나 레거시 포맷이면 재계산 + 저장한다.

    레거시 포맷(pre FULL-PERSONA-SPECTRUM, 2026-09-27): flat
    {axis: float|None}, 5축(form 포함). 현재 포맷과 다르면(축 없음/축 5개/
    값이 dict가 아님 등) project.liked_ids로부터 다시 계산해
    update_fields=['axis_scores']로 저장하고, reports.py와 동일한 방식으로
    projects list/detail 캐시를 무효화한다. 이미 현재 포맷이면 아무 것도
    하지 않는다(no-op).

    호출부(views/reports.py, views/projects.py)와의 순환 임포트를 피하기
    위해 캐시/liked_ids 헬퍼는 함수 내부에서 지연 임포트한다.
    """
    if _is_current_axis_shape(project.axis_scores):
        return

    from ..views._shared import _liked_id_only
    from ..caches import evict_projects_list, evict_project_detail

    liked_id_strings = _liked_id_only(project.liked_ids)
    project.axis_scores = compute_axis_scores(liked_id_strings)
    project.save(update_fields=['axis_scores'])
    evict_projects_list(project.user_id)
    evict_project_detail(str(project.project_id))


# =============================================================================
# Disabled 2026-09-27 (tag-weight scoring replaced by embedding projection) —
# kept per user request; delete once confirmed.
#
# The block below is the PREVIOUS implementation: form/scale/energy/tradition
# averaged TagAxisWeight rows matched against style+atmosphere tags;
# materiality classified material_visual strings by a natural/man-made word
# regex. TagAxisWeight the model, migration 0033, and fixtures/
# tag_axis_weights.json are all left untouched — only this scoring code path
# is disabled.
# =============================================================================
#
# import re
#
# from ..models import TagAxisWeight
#
# _OLD_AXES = ['form', 'materiality', 'scale', 'energy', 'tradition']
#
# # TagAxisWeight 기반으로 평균을 내는 축 (materiality는 제외 — 자재 단어 규칙으로 별도 계산)
# _OLD_CATEGORICAL_AXES = ['form', 'scale', 'energy', 'tradition']
#
# # ── materiality 단어 규칙 (case-insensitive, word-boundary) ────────────────
# # 자연 재료 (-1.0). 목록을 늘리거나 줄일 때는 여기만 수정하면 된다.
# _OLD_NATURAL_MATERIAL_WORDS = [
#     r'wood\w*', r'timber', r'oak', r'pine', r'cedar', r'larch', r'walnut',
#     r'birch', r'bamboo', r'cork', r'plywood', r'stone', r'marble', r'granite',
#     r'limestone', r'sandstone', r'travertine', r'slate', r'rock', r'brick\w*',
#     r'terracotta', r'clay', r'earth', r'adobe', r'thatch', r'straw', r'masonry',
# ]
#
# # 인공 재료 (+1.0). glass는 의도적으로 제외되어 있다 (절대 집계하지 않음).
# _OLD_MANMADE_MATERIAL_WORDS = [
#     r'concrete', r'cement', r'steel', r'metal\w*', r'iron', r'aluminum',
#     r'aluminium', r'polycarbonate', r'zinc', r'copper', r'brass', r'bronze',
#     r'composite', r'resin', r'plastic', r'acrylic', r'fiberglass', r'corten',
#     r'cor-ten', r'mirrors?',
# ]
#
# _OLD_NATURAL_MATERIAL_RE = re.compile(
#     r'\b(?:' + '|'.join(_OLD_NATURAL_MATERIAL_WORDS) + r')\b', re.IGNORECASE
# )
# _OLD_MANMADE_MATERIAL_RE = re.compile(
#     r'\b(?:' + '|'.join(_OLD_MANMADE_MATERIAL_WORDS) + r')\b', re.IGNORECASE
# )
#
#
# def _classify_material(material_str):
#     """단일 material_visual 문자열 -> -1.0(natural) / +1.0(man-made) / None(skip).
#
#     - glass는 두 목록에 없으므로 항상 skip.
#     - 양쪽 다 매치되면(혼합 자재 문구) skip.
#     - 둘 중 하나만 매치되면 해당 극성을 반환.
#     - 둘 다 매치 안 되면(water, vegetation, plaster, tile, paint, fabric...) skip.
#     """
#     if not material_str:
#         return None
#     is_natural = bool(_OLD_NATURAL_MATERIAL_RE.search(material_str))
#     is_manmade = bool(_OLD_MANMADE_MATERIAL_RE.search(material_str))
#     if is_natural and is_manmade:
#         return None
#     if is_natural:
#         return -1.0
#     if is_manmade:
#         return 1.0
#     return None
#
#
# def _mean_categorical_axes(tags, weight_map):
#     """tags: style/atmosphere 문자열 리스트. weight_map: {(tag, axis): weight}.
#     반환: _OLD_CATEGORICAL_AXES 각각의 매칭된 weight 평균. 해당 축에 매칭된
#     태그가 하나도 없으면 None(근거 없음) -- 실제로 계산되어 상쇄된 0.0과
#     구분한다."""
#     sums = {axis: 0.0 for axis in _OLD_CATEGORICAL_AXES}
#     counts = {axis: 0 for axis in _OLD_CATEGORICAL_AXES}
#     for tag in tags:
#         for axis in _OLD_CATEGORICAL_AXES:
#             w = weight_map.get((tag, axis))
#             if w is not None:
#                 sums[axis] += w
#                 counts[axis] += 1
#     return {
#         axis: (sums[axis] / counts[axis]) if counts[axis] > 0 else None
#         for axis in _OLD_CATEGORICAL_AXES
#     }
#
#
# def _mean_materiality(material_visual_lists):
#     """material_visual_lists: 건물별 material_visual 리스트의 리스트.
#     반환: 분류된 ±1.0 값들의 평균. 분류된 값이 하나도 없으면 None(근거 없음) --
#     실제로 계산되어 상쇄된 0.0과 구분한다."""
#     scores = []
#     for materials in material_visual_lists:
#         if not isinstance(materials, list):
#             continue
#         for material_str in materials:
#             classified = _classify_material(material_str)
#             if classified is not None:
#                 scores.append(classified)
#     return sum(scores) / len(scores) if scores else None
#
#
# def _old_compute_axis_scores(building_ids: list) -> dict:
#     """
#     building_ids: canonical_bld_id 리스트
#     반환: {"form": float|None, "materiality": float|None, "scale": float|None,
#            "energy": float|None, "tradition": float|None}
#     form/scale/energy/tradition = style+atmosphere 태그의 TagAxisWeight 평균.
#     materiality = material_visual 단어 규칙 분류 평균.
#     해당 축에 근거(매칭된 태그 / 분류된 자재)가 하나도 없으면 None(JSON null) --
#     UI가 "근거 없음"과 실제로 계산되어 상쇄된 0.0(중립)을 구분할 수 있게 한다.
#     building_ids가 비어 있거나, 조회된 행이 없거나, 태그/자재가 전혀 없으면
#     모든 축이 None이다.
#     """
#     if not building_ids:
#         return {axis: None for axis in _OLD_AXES}
#
#     # buildings DB에서 style, atmosphere, material_visual 배치 조회
#     with connections['buildings'].cursor() as cur:
#         cur.execute(
#             """
#             SELECT style, atmosphere, material_visual
#             FROM canonical_v2_buildings
#             WHERE canonical_bld_id = ANY(%s)
#               AND is_publishable = true
#             """,
#             [building_ids],
#         )
#         rows = cur.fetchall()
#
#     # 태그 수집 (style/atmosphere만 -- material_visual은 TagAxisWeight 조회에 쓰지 않음)
#     tags = []
#     material_visual_lists = []
#     for style, atmosphere, material_visual in rows:
#         if style:
#             tags.append(style)
#         if atmosphere:
#             tags.append(atmosphere)
#         material_visual_lists.append(material_visual)
#
#     # TagAxisWeight 일괄 조회 (_OLD_CATEGORICAL_AXES만)
#     weight_map = {}  # (tag, axis) -> weight
#     if tags:
#         weights_qs = TagAxisWeight.objects.filter(
#             tag__in=tags, axis__in=_OLD_CATEGORICAL_AXES,
#         ).values('tag', 'axis', 'weight')
#         for row in weights_qs:
#             weight_map[(row['tag'], row['axis'])] = row['weight']
#
#     categorical = _mean_categorical_axes(tags, weight_map)
#     materiality = _mean_materiality(material_visual_lists)
#
#     scores = dict(categorical)
#     scores['materiality'] = materiality
#
#     return {
#         axis: (round(scores[axis], 4) if scores[axis] is not None else None)
#         for axis in _OLD_AXES
#     }
