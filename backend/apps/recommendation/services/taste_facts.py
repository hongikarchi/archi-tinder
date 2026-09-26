"""
taste_facts.py -- BACK-LLM-5: deterministic swipe-fact extraction for persona reports.

PURE module: no Django imports, no DB access, no Gemini/LLM calls. Every
threshold is passed in via `rc` (callers pass settings.RECOMMENDATION) so this
module never reads settings directly -- keeps it trivially unit-testable with
plain dicts.

compute_taste_facts(rows_by_id, liked_ids, disliked_ids, rc) answers: "which
building features did the user's swipes actually favour or avoid, among the
cards they were SHOWN?" -- as opposed to a corpus-wide baseline. All facts are
computed relative to the shown set (liked ∪ disliked), never against the full
corpus, so wording downstream (_report_prompts.py) can honestly say "more
often than the OTHER BUILDINGS SHOWN" and never "than other users".

Terminology used throughout this module:
  - "shown set"  = liked_ids ∪ disliked_ids, with any id present in BOTH
    counted as liked only (an id can't be both -- see _partition_ids).
  - "universe"   = the subset of the shown set for which we actually have a
    DB row in `rows_by_id` (a shown id with no row contributes to summary
    counts but not to any axis/value tally -- we simply don't know its tags).
  - axis "A"     = a single (axis, value) feature, e.g. (style, brutalist).
  - "not A"      = universe ids that do NOT carry that axis value.
"""
import functools
import math

# Axis order is the base (pre-sort) candidate order, and therefore the
# deterministic tie-break order when a comparator returns 0 (equal ratio AND
# equal support) -- Python's sort is stable, so ties keep this ordering.
AXES = (
    'style',
    'atmosphere',
    'color_tone',
    'program',
    'typology_primary',
    'material_visual',
    'typology_tags',
    'architectural_elements',
    'architect_names',
    'decade',
    'location_country',
)

# Axes whose row value is a single scalar (TEXT column).
_SCALAR_AXES = frozenset({
    'style', 'atmosphere', 'color_tone', 'program', 'typology_primary', 'location_country',
})

# Axes whose row value is an array (TEXT[] column) -- a card "has" every
# distinct normalised element.
_ARRAY_AXES = frozenset({
    'material_visual', 'typology_tags', 'architectural_elements', 'architect_names',
})

# 'decade' is derived from project_year (INTEGER) -- handled specially in
# extract_axis_values, not a DB column name.
_DERIVED_AXES = frozenset({'decade'})


def _normalise(value):
    """lowercase + strip a single tag value; '' for null/empty/non-string-able input."""
    if value is None:
        return ''
    text = str(value).strip().lower()
    return text


def extract_axis_values(row, axis):
    """Return the set of normalised values `row` carries for `axis`.

    Public (no leading underscore) so generation.py can reuse the exact same
    extraction logic when building liked-only tag frequencies for the
    `description` paragraph's interpretive summary -- keeps that count
    axis-for-axis consistent with the fact math here.

    Skips null/empty values. Returns an empty set for an axis the row has
    no usable data for.
    """
    if axis in _DERIVED_AXES:
        year = row.get('project_year')
        if year is None:
            return set()
        try:
            year_int = int(year)
        except (TypeError, ValueError):
            return set()
        decade = (year_int // 10) * 10
        return {f'{decade}s'}

    if axis in _ARRAY_AXES:
        raw = row.get(axis) or []
        out = set()
        for item in raw:
            norm = _normalise(item)
            if norm:
                out.add(norm)
        return out

    if axis in _SCALAR_AXES:
        norm = _normalise(row.get(axis))
        return {norm} if norm else set()

    return set()


def _partition_ids(liked_ids, disliked_ids):
    """liked ∪ disliked with an id present in both resolved to liked-only."""
    liked_set = set(liked_ids or [])
    disliked_set = set(disliked_ids or []) - liked_set
    shown_set = liked_set | disliked_set
    return liked_set, disliked_set, shown_set


def _safe_div(numerator, denominator):
    if denominator <= 0:
        return float('inf') if numerator > 0 else 0.0
    return numerator / denominator


def _ratio_display(ratio):
    """Floor `ratio` to the nearest 0.5 step (1.7 -> 1.5, 2.3 -> 2.0, 3.8 -> 3.5).

    Q40 (2026-09-26 decision, applied): 0.5-step floor keeps the displayed
    multiplier from implying more precision than the smoothed estimate has.
    """
    if not math.isfinite(ratio):
        return ratio
    stepped = math.floor(ratio / 0.5) * 0.5
    # Whole steps as int so the prompt JSON says 2 (not 2.0) and the LLM writes "약 2배".
    return int(stepped) if stepped.is_integer() else stepped


def _overlap_ratio(ids_a, ids_b):
    """|intersection| / min(|a|, |b|); 0.0 when either set is empty."""
    set_a, set_b = set(ids_a), set(ids_b)
    if not set_a or not set_b:
        return 0.0
    inter = len(set_a & set_b)
    return inter / min(len(set_a), len(set_b))


def _tie_aware_cmp(a, b, tie_ratio, support_key, ascending):
    """Stable comparator for candidate ordering within one polarity.

    Primary key: `ratio` (ascending for dislike -- strongest avoidance i.e.
    lowest ratio first; descending for like -- strongest preference i.e.
    highest ratio first).

    Q37/spec tie-break: when |a.ratio - b.ratio| <= tie_ratio, the two
    candidates are treated as "about as strong" and the tie is broken by
    which one has MORE supporting buildings (`support_key`: 'liked' for like
    candidates, 'disliked' for dislike candidates) -- more evidence wins.
    Equal-on-both -> 0 (stable sort keeps AXES-then-alphabetical base order).
    """
    ratio_a, ratio_b = a['ratio'], b['ratio']
    if abs(ratio_a - ratio_b) <= tie_ratio:
        support_a, support_b = a[support_key], b[support_key]
        if support_a != support_b:
            return -1 if support_a > support_b else 1
        return 0
    if ascending:
        return -1 if ratio_a < ratio_b else 1
    return -1 if ratio_a > ratio_b else 1


def _select(candidates, cap, overlap_max, used_axes, already_selected):
    """Greedily pick up to `cap` candidates (already sorted best-first).

    - Skips a candidate whose axis is already used (one fact per axis,
      scoped to THIS polarity's own `used_axes` set -- a like fact and a
      dislike fact may legitimately share an axis, e.g. style=brutalist
      liked + style=kitsch disliked; a cap of 1 dislike makes this mostly
      moot for the dislike side anyway).
    - Skips a candidate whose supporting building_ids overlap >= overlap_max
      with ANY already-selected fact (checked against `already_selected` +
      facts chosen earlier in this same call) -- Q38 dedupe. In practice this
      only ever fires within the same polarity: a like fact's building_ids
      come from the liked set and a dislike fact's from the disliked set,
      which are disjoint by construction (_partition_ids), so cross-polarity
      overlap is always 0.
    """
    chosen = []
    for cand in candidates:
        if len(chosen) >= cap:
            break
        if cand['axis'] in used_axes:
            continue
        conflict = False
        for sel in already_selected + chosen:
            if _overlap_ratio(cand['building_ids'], sel['building_ids']) >= overlap_max:
                conflict = True
                break
        if conflict:
            continue
        chosen.append(cand)
        used_axes.add(cand['axis'])
    return chosen


def compute_taste_facts(rows_by_id, liked_ids, disliked_ids, rc):
    """Deterministically extract grounded like/dislike facts from swipe history.

    Args:
        rows_by_id: dict[canonical_bld_id, dict] -- building row per shown id
            (missing ids are tolerated; they only affect summary counts).
        liked_ids:  list[str] canonical_bld_id.
        disliked_ids: list[str] canonical_bld_id.
        rc: dict (callers pass settings.RECOMMENDATION) -- must supply
            report_fact_min_shown, report_fact_min_liked, report_fact_min_ratio,
            report_fact_tie_ratio, report_fact_max_likes, report_fact_max_dislikes,
            report_dislike_often, report_dislike_mostly, report_fact_overlap_max,
            report_fact_smoothing (all have sane defaults below if absent).

    Returns:
        {'facts': [fact, ...], 'summary': {'shown': int, 'liked': int, 'disliked': int}}

        Each fact: {polarity, axis, value, ratio, ratio_display, shown, liked,
        disliked, others_rarely_liked, building_ids, [dislike_word]}.
    """
    rows_by_id = rows_by_id or {}
    rc = rc or {}

    s = rc.get('report_fact_smoothing', 1)
    min_shown = rc.get('report_fact_min_shown', 3)
    min_liked = rc.get('report_fact_min_liked', 2)
    min_ratio = rc.get('report_fact_min_ratio', 1.5)
    tie_ratio = rc.get('report_fact_tie_ratio', 0.3)
    max_likes = rc.get('report_fact_max_likes', 3)
    max_dislikes = rc.get('report_fact_max_dislikes', 1)
    dislike_often = rc.get('report_dislike_often', 0.4)
    dislike_mostly = rc.get('report_dislike_mostly', 0.8)
    overlap_max = rc.get('report_fact_overlap_max', 0.8)

    liked_set, disliked_set, shown_set = _partition_ids(liked_ids, disliked_ids)
    summary = {'shown': len(shown_set), 'liked': len(liked_set), 'disliked': len(disliked_set)}

    universe_ids = [bid for bid in shown_set if bid in rows_by_id]
    n_universe = len(universe_ids)
    if n_universe == 0:
        return {'facts': [], 'summary': summary}

    n_universe_liked = sum(1 for bid in universe_ids if bid in liked_set)

    # axis -> value -> {'shown': set(ids), 'liked': set(ids), 'disliked': set(ids)}
    buckets = {axis: {} for axis in AXES}

    for bid in universe_ids:
        row = rows_by_id[bid]
        is_liked = bid in liked_set
        for axis in AXES:
            for value in extract_axis_values(row, axis):
                bucket = buckets[axis].setdefault(
                    value, {'shown': set(), 'liked': set(), 'disliked': set()},
                )
                bucket['shown'].add(bid)
                if is_liked:
                    bucket['liked'].add(bid)
                else:
                    bucket['disliked'].add(bid)

    like_candidates = []
    dislike_candidates = []

    for axis in AXES:
        for value in sorted(buckets[axis].keys()):
            bucket = buckets[axis][value]
            shown_A = len(bucket['shown'])
            liked_A = len(bucket['liked'])
            disliked_A = len(bucket['disliked'])
            shown_notA = n_universe - shown_A
            liked_notA = n_universe_liked - liked_A

            r_A = _safe_div(liked_A + s, shown_A + 2 * s)
            r_notA = _safe_div(liked_notA + s, shown_notA + 2 * s)
            ratio = _safe_div(r_A, r_notA)

            others_rarely_liked = liked_notA == 0 and shown_notA >= min_shown

            base_fact = {
                'axis': axis,
                'value': value,
                'ratio': round(ratio, 2) if math.isfinite(ratio) else ratio,
                'ratio_display': _ratio_display(ratio),
                'shown': shown_A,
                'liked': liked_A,
                'disliked': disliked_A,
                'others_rarely_liked': others_rarely_liked,
            }

            if shown_A >= min_shown and liked_A >= min_liked and ratio >= min_ratio:
                like_candidates.append({
                    **base_fact,
                    'polarity': 'like',
                    'building_ids': sorted(bucket['liked']),
                })

            if shown_A >= min_shown and shown_A > 0:
                dislike_rate = disliked_A / shown_A
                if dislike_rate >= dislike_often and ratio <= (1.0 / min_ratio):
                    dislike_word = 'mostly' if dislike_rate >= dislike_mostly else 'often'
                    dislike_candidates.append({
                        **base_fact,
                        'polarity': 'dislike',
                        'dislike_word': dislike_word,
                        'building_ids': sorted(bucket['disliked']),
                    })

    like_key = functools.cmp_to_key(
        lambda a, b: _tie_aware_cmp(a, b, tie_ratio, 'liked', ascending=False)
    )
    dislike_key = functools.cmp_to_key(
        lambda a, b: _tie_aware_cmp(a, b, tie_ratio, 'disliked', ascending=True)
    )
    like_candidates.sort(key=like_key)
    dislike_candidates.sort(key=dislike_key)

    like_selected = _select(like_candidates, max_likes, overlap_max, used_axes=set(), already_selected=[])
    dislike_selected = _select(
        dislike_candidates, max_dislikes, overlap_max, used_axes=set(), already_selected=like_selected,
    )

    return {'facts': like_selected + dislike_selected, 'summary': summary}
