"""
engine.py — Recommendation algorithm using pgvector.
All DB access is raw SQL against architecture_vectors (owned by Make DB).
"""
import math
import random
import logging
import numpy as np
from django.conf import settings
from django.db import connection

logger = logging.getLogger('apps.recommendation')

RC = settings.RECOMMENDATION  # shorthand for constants

_pool_embedding_cache = {}
_centroid_cache = {}


# ── Helpers ───────────────────────────────────────────────────────────────────

def _dictfetchall(cursor):
    """Return all rows from cursor as list of dicts."""
    cols = [c[0] for c in cursor.description]
    return [dict(zip(cols, row)) for row in cursor.fetchall()]


def _row_to_card(row):
    """Convert a DB row dict to ImageCard format."""
    from django.conf import settings as _s
    building_id  = row['building_id']
    photos       = row.get('image_photos') or []
    drawings     = row.get('image_drawings') or []
    base         = _s.IMAGE_BASE_URL.rstrip('/')
    cover        = photos[0] if photos else ''
    image_url    = f'{base}/{building_id}/{cover}' if cover else ''
    extra_photos = [f'{base}/{building_id}/{f}' for f in photos[1:] if f]
    drawing_urls = [f'{base}/{building_id}/{f}' for f in drawings if f]
    gallery      = extra_photos + drawing_urls
    return {
        'building_id':          building_id,
        'name_en':              row.get('name_en') or '',
        'project_name':         row.get('project_name') or '',
        'image_url':            image_url,
        'url':                  row.get('url'),
        'gallery':              gallery,
        'gallery_drawing_start': len(extra_photos),
        'metadata': {
            'axis_typology':   row.get('program'),
            'axis_architects': row.get('architect'),
            'axis_country':    row.get('location_country'),
            'axis_area_m2':    float(row['area_sqm']) if row.get('area_sqm') else None,
            'axis_year':       row.get('year'),
            'axis_style':          row.get('style'),
            'axis_atmosphere':     row.get('atmosphere'),
            'axis_color_tone':     row.get('color_tone'),
            'axis_material':       row.get('material'),
            'axis_material_visual': list(row.get('material_visual') or []),
            'axis_tags':       list(row.get('tags') or []),
        },
    }


def _build_filter_sql(filters):
    """Build WHERE clauses from a filters dict. Returns (clauses_str, params_list)."""
    clauses, params = [], []
    if not filters:
        return '', []
    if filters.get('program'):
        clauses.append('program = %s')
        params.append(filters['program'])
    if filters.get('location_country'):
        clauses.append('location_country ILIKE %s')
        params.append(f"%{filters['location_country']}%")
    if filters.get('min_area') is not None:
        clauses.append('area_sqm >= %s')
        params.append(filters['min_area'])
    if filters.get('max_area') is not None:
        clauses.append('area_sqm <= %s')
        params.append(filters['max_area'])
    if filters.get('material'):
        clauses.append('material ILIKE %s')
        params.append(f"%{filters['material']}%")
    if filters.get('style'):
        clauses.append('style ILIKE %s')
        params.append(f"%{filters['style']}%")
    if filters.get('year_min') is not None:
        clauses.append('year >= %s')
        params.append(filters['year_min'])
    if filters.get('year_max') is not None:
        clauses.append('year <= %s')
        params.append(filters['year_max'])
    where = 'WHERE ' + ' AND '.join(clauses) if clauses else ''
    return where, params


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


# ── Public API ────────────────────────────────────────────────────────────────

def get_diverse_random(n=10, filters=None):
    """
    Select n maximally diverse buildings from candidates.
    Uses greedy farthest-point sampling on cosine distance.
    Returns list of ImageCard dicts.
    """
    where, params = _build_filter_sql(filters)
    with connection.cursor() as cur:
        cur.execute(
            f'SELECT building_id, name_en, project_name, architect, location_country, '
            f'city, year, area_sqm, program, style, atmosphere, color_tone, material, material_visual, url, tags, image_photos, image_drawings, '
            f'embedding::text FROM architecture_vectors {where} ORDER BY RANDOM() LIMIT %s',
            params + [min(n * 5, 100)],  # fetch a pool, then diversify
        )
        rows = _dictfetchall(cur)

    if not rows:
        return []

    # Parse embeddings
    for row in rows:
        raw = row['embedding']
        row['_vec'] = [float(x) for x in raw.strip('[]').split(',')]

    # Greedy farthest-point sampling
    selected = [rows[0]]
    remaining = rows[1:]
    while len(selected) < n and remaining:
        best_idx, best_dist = 0, -1
        for i, r in enumerate(remaining):
            min_sim = min(
                sum(a * b for a, b in zip(r['_vec'], s['_vec']))
                for s in selected
            )
            dist = 1 - min_sim  # cosine distance
            if dist > best_dist:
                best_idx, best_dist = i, dist
        selected.append(remaining.pop(best_idx))

    return [_row_to_card(r) for r in selected]


def get_building_embedding(building_id):
    """Fetch the embedding vector for a single building. Returns list of floats."""
    with connection.cursor() as cur:
        cur.execute(
            'SELECT embedding::text FROM architecture_vectors WHERE building_id = %s',
            [building_id],
        )
        row = cur.fetchone()
    if not row:
        return None
    return [float(x) for x in row[0].strip('[]').split(',')]


def get_building_card(building_id):
    """Fetch a single building as an ImageCard dict."""
    with connection.cursor() as cur:
        cur.execute(
            'SELECT building_id, name_en, project_name, architect, location_country, '
            'city, year, area_sqm, program, style, atmosphere, color_tone, material, material_visual, url, tags, image_photos, image_drawings '
            'FROM architecture_vectors WHERE building_id = %s',
            [building_id],
        )
        rows = _dictfetchall(cur)
    return _row_to_card(rows[0]) if rows else None


def update_preference_vector(pref_vector, embedding, action):
    """
    Update preference vector based on a swipe action.
    like: pref += 0.5 * emb
    dislike: pref -= 1.0 * emb
    Returns normalized vector.
    """
    like_w    = RC['like_weight']
    dislike_w = RC['dislike_weight']
    weight    = like_w if action == 'like' else dislike_w

    if not pref_vector:
        pref_vector = [0.0] * len(embedding)

    updated = [p + weight * e for p, e in zip(pref_vector, embedding)]
    return _normalize(updated)


def get_top_k_results(pref_vector, exposed_ids, k=None):
    """
    Query top-k buildings by cosine similarity to preference vector.
    Excludes exposed_ids. Returns list of ImageCard dicts.
    """
    if k is None:
        k = RC['top_k_results']

    exclude_sql = ''
    params = []
    if exposed_ids:
        placeholders = ','.join(['%s'] * len(exposed_ids))
        exclude_sql = f'WHERE building_id NOT IN ({placeholders})'
        params = list(exposed_ids)

    if not pref_vector:
        # No preference yet — return random
        with connection.cursor() as cur:
            cur.execute(
                f'SELECT building_id, name_en, project_name, architect, location_country, '
                f'city, year, area_sqm, program, style, atmosphere, color_tone, material, material_visual, url, tags, image_photos, image_drawings '
                f'FROM architecture_vectors {exclude_sql} ORDER BY RANDOM() LIMIT %s',
                params + [k],
            )
            rows = _dictfetchall(cur)
    else:
        vec_str = _vec_to_pg(pref_vector)
        with connection.cursor() as cur:
            cur.execute(
                f'SELECT building_id, name_en, project_name, architect, location_country, '
                f'city, year, area_sqm, program, style, atmosphere, color_tone, material, material_visual, url, tags, image_photos, image_drawings '
                f'FROM architecture_vectors {exclude_sql} '
                f'ORDER BY embedding <=> %s::vector LIMIT %s',
                params + [vec_str, k],
            )
            rows = _dictfetchall(cur)

    return [_row_to_card(r) for r in rows]


def get_buildings_by_ids(building_ids):
    """Fetch multiple buildings by ID list. Returns list of ImageCard dicts."""
    if not building_ids:
        return []
    placeholders = ','.join(['%s'] * len(building_ids))
    with connection.cursor() as cur:
        cur.execute(
            f'SELECT building_id, name_en, project_name, architect, location_country, '
            f'city, year, area_sqm, program, style, atmosphere, color_tone, material, material_visual, url, tags, image_photos, image_drawings '
            f'FROM architecture_vectors WHERE building_id IN ({placeholders})',
            list(building_ids),
        )
        rows = _dictfetchall(cur)
    # Preserve input order
    row_map = {r['building_id']: r for r in rows}
    return [_row_to_card(row_map[bid]) for bid in building_ids if bid in row_map]


def search_by_filters(filters, limit=20):
    """
    Return buildings matching the given filters dict.
    Used by ParseQueryView (Phase 3).
    """
    where, params = _build_filter_sql(filters)
    with connection.cursor() as cur:
        cur.execute(
            f'SELECT building_id, name_en, project_name, architect, location_country, '
            f'city, year, area_sqm, program, style, atmosphere, color_tone, material, material_visual, url, tags, image_photos, image_drawings '
            f'FROM architecture_vectors {where} ORDER BY RANDOM() LIMIT %s',
            params + [limit],
        )
        rows = _dictfetchall(cur)
    return [_row_to_card(r) for r in rows]


# ── Phase-Aware Algorithm (PRD v4.0) ──────────────────────────────────────────────


def _random_pool(target):
    """Fallback: random pool when no filters are provided."""
    with connection.cursor() as cur:
        cur.execute(
            'SELECT building_id FROM architecture_vectors ORDER BY RANDOM() LIMIT %s',
            [target],
        )
        rows = cur.fetchall()
    return [row[0] for row in rows]


def create_pool_with_relaxation(filters, filter_priority, seed_ids, exclude_ids=None, target=None, start_tier=1):
    """
    Run 3-tier pool creation with relaxation fallback.

    Tier 1: full filter (create_bounded_pool with filters as-is).
    Tier 2: drop geographic + numeric (location_country, year_min, year_max, min_area, max_area).
    Tier 3: random pool (_random_pool(target)).

    exclude_ids: building_ids to remove from the result (e.g., already-exposed). Default None.
    start_tier: starting tier (1, 2, or 3). Used by pool exhaustion guard to escalate from
                session's current tier.

    Returns (pool_ids, pool_scores, tier_used).
    Returns ([], {}, 0) if even tier 3 produces no candidates after exclude (unrecoverable).
    """
    if target is None:
        target = RC['bounded_pool_target']
    exclude_set = set(exclude_ids or [])

    # Tier 1
    if start_tier <= 1:
        pool_ids, pool_scores = create_bounded_pool(filters or {}, filter_priority, seed_ids, target=target)
        filtered_ids = [bid for bid in pool_ids if bid not in exclude_set]
        if filtered_ids:
            filtered_scores = {bid: s for bid, s in pool_scores.items() if bid not in exclude_set}
            return filtered_ids, filtered_scores, 1

    # Tier 2
    if start_tier <= 2:
        relaxed = {k: v for k, v in (filters or {}).items()
                   if k not in ('location_country', 'year_min', 'year_max', 'min_area', 'max_area')}
        if relaxed and relaxed != (filters or {}):
            relaxed_priority = [k for k in (filter_priority or []) if k in relaxed]
            pool_ids, pool_scores = create_bounded_pool(relaxed, relaxed_priority, seed_ids, target=target)
            filtered_ids = [bid for bid in pool_ids if bid not in exclude_set]
            if filtered_ids:
                filtered_scores = {bid: s for bid, s in pool_scores.items() if bid not in exclude_set}
                return filtered_ids, filtered_scores, 2

    # Tier 3 — random pool
    pool_ids = [bid for bid in _random_pool(target) if bid not in exclude_set]
    if pool_ids:
        return pool_ids, {}, 3
    return [], {}, 0


def refresh_pool_if_low(session, threshold=5):
    """
    If session's remaining pool (pool_ids - exposed_ids) is below threshold, escalate
    to the next tier and merge new pool_ids into the session.

    Side effect: when escalation fires, session.pool_ids, session.pool_scores, and
    session.current_pool_tier are mutated in-place. Caller MUST save the session with
    these fields in update_fields.

    Returns the session's pool_ids list (updated if escalation fired, unchanged otherwise).
    Per spec §5.6 + §6: triggered when remaining pool < threshold (default 5).
    """
    exposed_set = set(session.exposed_ids or [])
    remaining = [bid for bid in session.pool_ids if bid not in exposed_set]
    if len(remaining) >= threshold:
        return session.pool_ids  # No escalation needed
    if session.current_pool_tier >= 3:
        return session.pool_ids  # Already at tier 3 — nothing to escalate to

    next_tier = session.current_pool_tier + 1
    # exclude_ids: both current pool AND exposed (belt-and-suspenders; exposed already
    # excluded by pool construction but cheap defensive guard)
    exclude_ids = list(session.pool_ids or []) + list(session.exposed_ids or [])
    new_pool_ids, new_pool_scores, tier_used = create_pool_with_relaxation(
        session.original_filters,
        session.original_filter_priority,
        session.original_seed_ids,
        exclude_ids=exclude_ids,
        start_tier=next_tier,
    )
    if not new_pool_ids:
        # No new candidates available even at higher tier — degrade gracefully
        logger.info(
            'Session %s: pool exhaustion escalation to tier %d found no new candidates',
            session.session_id, next_tier,
        )
        return session.pool_ids

    # Merge: append new IDs (guaranteed disjoint by exclude_ids) and scores
    session.pool_ids = list(session.pool_ids) + new_pool_ids
    merged_scores = dict(session.pool_scores or {})
    merged_scores.update(new_pool_scores)
    session.pool_scores = merged_scores
    session.current_pool_tier = tier_used

    logger.info(
        'Session %s: pool exhaustion guard escalated to tier %d, added %d buildings (total pool=%d)',
        session.session_id, tier_used, len(new_pool_ids), len(session.pool_ids),
    )
    return session.pool_ids


def _build_score_cases(filters, weights):
    """Build CASE WHEN SQL for each active filter with priority weight."""
    cases, params = [], []
    total_weight = 0
    if filters.get('program') and 'program' in weights:
        w = weights['program']
        cases.append(f'CASE WHEN program = %s THEN {w} ELSE 0 END')
        params.append(filters['program'])
        total_weight += w
    if filters.get('location_country') and 'location_country' in weights:
        w = weights['location_country']
        cases.append(f'CASE WHEN location_country ILIKE %s THEN {w} ELSE 0 END')
        params.append(f"%{filters['location_country']}%")
        total_weight += w
    if filters.get('style') and 'style' in weights:
        w = weights['style']
        cases.append(f'CASE WHEN style ILIKE %s THEN {w} ELSE 0 END')
        params.append(f"%{filters['style']}%")
        total_weight += w
    if filters.get('material') and 'material' in weights:
        w = weights['material']
        cases.append(f'CASE WHEN material ILIKE %s THEN {w} ELSE 0 END')
        params.append(f"%{filters['material']}%")
        total_weight += w
    if filters.get('min_area') is not None and 'min_area' in weights:
        w = weights['min_area']
        cases.append(f'CASE WHEN area_sqm >= %s THEN {w} ELSE 0 END')
        params.append(filters['min_area'])
        total_weight += w
    if filters.get('max_area') is not None and 'max_area' in weights:
        w = weights['max_area']
        cases.append(f'CASE WHEN area_sqm <= %s THEN {w} ELSE 0 END')
        params.append(filters['max_area'])
        total_weight += w
    if filters.get('year_min') is not None and 'year_min' in weights:
        w = weights['year_min']
        cases.append(f'CASE WHEN year >= %s THEN {w} ELSE 0 END')
        params.append(filters['year_min'])
        total_weight += w
    if filters.get('year_max') is not None and 'year_max' in weights:
        w = weights['year_max']
        cases.append(f'CASE WHEN year <= %s THEN {w} ELSE 0 END')
        params.append(filters['year_max'])
        total_weight += w
    return cases, params, total_weight


def create_bounded_pool(filters, filter_priority=None, seed_ids=None, target=None):
    """
    Create a bounded pool of building IDs with weighted scoring.
    Each building matching at least one filter is included, ranked by score.
    Returns tuple: (pool_ids, pool_scores) where pool_scores is {building_id: score}.
    Scores are floats in [0, 1], normalized by sum of active-filter weights.
    Seeded building_ids (if provided) get score 1.1, placing them above max.
    """
    if target is None:
        target = RC['bounded_pool_target']
    if not filters:
        return _random_pool(target), {}

    priority = filter_priority or list(filters.keys())
    n = len(priority)
    weights = {key: n - i for i, key in enumerate(priority)}

    cases, params, total_weight = _build_score_cases(filters, weights)
    if not cases:
        return _random_pool(target), {}

    score_sql = '((' + ' + '.join(cases) + ')::float / ' + str(total_weight) + ')'
    sql = (
        'SELECT building_id, (' + score_sql + ') AS relevance_score'
        ' FROM architecture_vectors'
        ' WHERE (' + score_sql + ') > 0'
        ' ORDER BY relevance_score DESC, RANDOM()'
        ' LIMIT %s'
    )
    with connection.cursor() as cur:
        cur.execute(sql, params + params + [target])
        rows = cur.fetchall()

    pool_ids = [row[0] for row in rows]
    pool_scores = {row[0]: row[1] for row in rows}

    if seed_ids:
        for sid in seed_ids:
            if sid not in pool_scores:
                pool_ids.insert(0, sid)
            pool_scores[sid] = 1.1

    return pool_ids, pool_scores


def get_pool_embeddings(pool_ids):
    """
    Fetch embeddings for pool_ids.
    Returns dict mapping building_id -> np.ndarray (shape=(384,))
    """
    if not pool_ids:
        return {}

    cache_key = frozenset(pool_ids)
    if cache_key in _pool_embedding_cache:
        return _pool_embedding_cache[cache_key]

    placeholders = ','.join(['%s'] * len(pool_ids))
    with connection.cursor() as cur:
        cur.execute(
            f'SELECT building_id, embedding::text FROM architecture_vectors WHERE building_id IN ({placeholders})',
            list(pool_ids),
        )
        rows = _dictfetchall(cur)

    result = {}
    for row in rows:
        embedding_str = row['embedding']
        embedding = np.array([float(x) for x in embedding_str.strip('[]').split(',')])
        norm = np.linalg.norm(embedding)
        if norm > 0:
            embedding = embedding / norm
        result[row['building_id']] = embedding

    if len(_pool_embedding_cache) > 50:
        _pool_embedding_cache.clear()
    _pool_embedding_cache[cache_key] = result
    return result


def clear_pool_embedding_cache():
    """Clear the pool embedding cache (for testing)."""
    _pool_embedding_cache.clear()


def clear_centroid_cache():
    """Clear the centroid cache (for testing)."""
    _centroid_cache.clear()


def farthest_point_from_pool(pool_ids, exposed_ids, pool_embeddings):
    """
    Select the pool building farthest from all exposed buildings (Gonzalez
    greedy farthest-point sampling). For each candidate, computes its cosine
    similarity to every exposed item, takes the MAXIMUM similarity (= nearest
    exposed), then returns the candidate that MINIMIZES that -- i.e., the
    candidate whose nearest exposed is farthest away. Embeddings are
    L2-normalized in get_pool_embeddings(), so np.dot is cosine similarity.

    Vectorized via NumPy batch matmul (one BLAS call) -- ~20-50x faster than
    the prior nested-loop implementation.

    Returns None if no valid (in-pool, in-embeddings, not-yet-exposed) candidates.
    Returns a random unexposed candidate if exposed_ids is empty (no anchor
    to compute distance from).
    """
    exposed_set = set(exposed_ids)
    candidate_ids = [
        bid for bid in pool_ids
        if bid not in exposed_set and bid in pool_embeddings
    ]
    if not candidate_ids:
        return None

    exposed_valid = [e for e in exposed_ids if e in pool_embeddings]
    if not exposed_valid:
        return random.choice(candidate_ids)

    C = np.stack([pool_embeddings[bid] for bid in candidate_ids])   # (N, 384)
    E = np.stack([pool_embeddings[bid] for bid in exposed_valid])   # (M, 384)

    sim = C @ E.T                            # (N, M) -- single BLAS matmul
    max_sim_per_candidate = sim.max(axis=1)  # (N,) -- nearest-exposed similarity
    best_idx = int(np.argmin(max_sim_per_candidate))
    return candidate_ids[best_idx]


def compute_taste_centroids(like_vectors, round_num):
    """
    Compute taste cluster centroids with recency weighting.
    Returns (list_of_centroids, global_centroid) as numpy arrays.
    Called by views.py (convergence tracking) and algorithm_tester.py.
    """
    cache_key = (
        tuple(
            (lv['round'], round(lv['embedding'][0], 6), round(lv['embedding'][191], 6), round(lv['embedding'][-1], 6))
            for lv in like_vectors
        ),
        round_num,
    )
    if cache_key in _centroid_cache:
        return _centroid_cache[cache_key]

    weighted_likes = _apply_recency_weights(like_vectors, round_num, RC['decay_rate'])

    if len(weighted_likes) == 1:
        centroid = weighted_likes[0][0]
        result = ([centroid], centroid)
        if len(_centroid_cache) > 20:
            _centroid_cache.clear()
        _centroid_cache[cache_key] = result
        return result

    from sklearn.cluster import KMeans
    from sklearn.metrics import silhouette_samples
    like_embeddings = np.array([w[0] for w in weighted_likes])
    like_weights = np.array([w[1] for w in weighted_likes])
    global_centroid = _weighted_centroid(weighted_likes)

    # Topic 06: silhouette-based adaptive k selection (flag-gated, N>=4 required)
    if RC.get('adaptive_k_clustering_enabled', False) and len(weighted_likes) >= 4:
        kmeans2 = KMeans(n_clusters=2, random_state=42, n_init=3)
        kmeans2.fit(like_embeddings, sample_weight=like_weights)
        if len(set(kmeans2.labels_)) > 1:
            # Weighted silhouette: per-sample silhouette × recency weights, averaged.
            # sklearn 1.6.1's silhouette_score doesn't accept sample_weight, so we
            # compute per-sample scores and weight-average them ourselves. This honors
            # the recency weights that drove the KMeans clustering decision (which
            # would otherwise be ignored by the silhouette validation step).
            try:
                sample_sils = silhouette_samples(like_embeddings, kmeans2.labels_)
                sil2 = float(np.average(sample_sils, weights=like_weights))
            except ValueError:
                # KMeans degenerated (all points labeled identically) → no separation → k=1
                sil2 = -1.0
        else:
            sil2 = -1.0  # all points in one cluster; degenerate k=2
        if sil2 >= 0.15:
            centroids = list(kmeans2.cluster_centers_)
        else:
            centroids = [global_centroid]  # degrade to k=1
        result = (centroids, global_centroid)
        if len(_centroid_cache) > 20:
            _centroid_cache.clear()
        _centroid_cache[cache_key] = result
        return result

    # Default path: k=min(k_clusters, N) KMeans (flag off or N<4)
    k_clusters = min(RC['k_clusters'], len(weighted_likes))
    kmeans = KMeans(n_clusters=k_clusters, random_state=42, n_init=3)
    kmeans.fit(like_embeddings, sample_weight=like_weights)
    centroids = list(kmeans.cluster_centers_)
    result = (centroids, global_centroid)
    if len(_centroid_cache) > 20:
        _centroid_cache.clear()
    _centroid_cache[cache_key] = result
    return centroids, global_centroid


def compute_mmr_next(pool_ids, exposed_ids, pool_embeddings, like_vectors, round_num):
    """
    Select next building using MMR (Maximal Marginal Relevance).
    Returns building_id string or None if no candidates.
    """
    candidates = [bid for bid in pool_ids if bid not in set(exposed_ids)]
    if not candidates:
        return None

    if not like_vectors:
        return random.choice(candidates)

    centroids, _ = compute_taste_centroids(like_vectors, round_num)

    best_candidate = None
    best_score = -float('inf')

    for candidate in candidates:
        if candidate not in pool_embeddings:
            continue

        candidate_emb = pool_embeddings[candidate]

        # Relevance: max cosine similarity (default) or softmax-weighted avg (Topic 06)
        if RC.get('soft_relevance_enabled', False) and len(centroids) > 1:
            sims = np.array([np.dot(candidate_emb, c) for c in centroids])
            exp_sims = np.exp(sims - sims.max())  # numerically stable softmax
            weights = exp_sims / exp_sims.sum()
            relevance = float(np.sum(sims * weights))
        else:
            relevance = max(np.dot(candidate_emb, centroid) for centroid in centroids)

        # Redundancy: max cosine similarity to any exposed embedding
        redundancy = 0
        for exposed_id in exposed_ids:
            if exposed_id in pool_embeddings:
                exposed_emb = pool_embeddings[exposed_id]
                redundancy = max(redundancy, np.dot(candidate_emb, exposed_emb))

        # MMR score
        mmr_score = relevance - RC['mmr_penalty'] * redundancy

        if mmr_score > best_score:
            best_score = mmr_score
            best_candidate = candidate

    return best_candidate


def _apply_recency_weights(like_vectors, round_num, gamma):
    """
    Apply recency weights to like vectors.
    Returns list of (np.array(embedding), weight)
    """
    weighted_vecs = []
    for entry in like_vectors:
        embedding = np.array(entry['embedding'])
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


def check_convergence(history, threshold, window=3):
    """
    Check if convergence has been reached based on moving average.
    Returns bool
    """
    if len(history) < window:
        return False

    moving_avg = np.mean(history[-window:])
    return bool(moving_avg < threshold)


def compute_confidence(history, threshold, window=3):
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
    safe_threshold = max(float(threshold), 1e-6)
    avg = sum(history[-window:]) / window
    return max(0.0, 1.0 - avg / safe_threshold)


def get_dislike_fallback(pool_ids, exposed_ids, pool_embeddings, dislike_vectors):
    """
    Select building farthest from dislike centroid.
    Returns building_id string or None if no candidates.
    """
    candidates = [bid for bid in pool_ids if bid not in set(exposed_ids)]
    if not candidates:
        return None

    if not dislike_vectors:
        return random.choice(candidates)

    # Compute dislike centroid
    dislike_embeddings = [np.array(dv) for dv in dislike_vectors]
    dislike_centroid = np.mean(dislike_embeddings, axis=0)
    dislike_centroid = dislike_centroid / np.linalg.norm(dislike_centroid)  # normalize

    best_candidate = None
    best_distance = -1

    for candidate in candidates:
        if candidate not in pool_embeddings:
            continue

        candidate_emb = pool_embeddings[candidate]
        similarity = np.dot(candidate_emb, dislike_centroid)
        distance = 1 - similarity  # cosine distance

        if distance > best_distance:
            best_distance = distance
            best_candidate = candidate

    return best_candidate


def build_action_card():
    """
    Return action card dict for analysis completion.
    """
    return {
        'building_id': '__action_card__',
        'card_type': 'action',
        'name_en': 'Your Taste is Found!',
        'project_name': '',
        'image_url': '',
        'url': None,
        'gallery': [],
        'gallery_drawing_start': 0,
        'metadata': {},
        'action_card_message': (
            'We\'ve analyzed your preferences and found your architectural taste.'
        ),
        'action_card_subtitle': (
            'Swipe right to see your personalized results, '
            'or swipe left to keep exploring more buildings.'
        ),
    }


def get_top_k_mmr(like_vectors, exposed_ids, k=None, round_num=None):
    """
    Get top-k results using MMR for final recommendations.
    Uses recency-weighted K-Means centroids when round_num is provided.
    Returns list of ImageCard dicts.
    """
    if k is None:
        k = RC['top_k_results']

    if not like_vectors:
        return []

    # Use K-Means centroids with recency weighting when round_num available
    if round_num is not None:
        centroids, centroid = compute_taste_centroids(like_vectors, round_num)
        norm = np.linalg.norm(centroid)
        if norm > 0:
            centroid = centroid / norm
    else:
        like_embeddings = [np.array(lv['embedding']) for lv in like_vectors]
        centroid = np.mean(like_embeddings, axis=0)
        centroid = centroid / np.linalg.norm(centroid)
        centroids = [centroid]

    # Prepare exclusion clause
    exclude_sql = ''
    params = []
    if exposed_ids:
        placeholders = ','.join(['%s'] * len(exposed_ids))
        exclude_sql = f'WHERE building_id NOT IN ({placeholders})'
        params = list(exposed_ids)

    # Fetch 3*k candidates for re-ranking
    vec_str = _vec_to_pg(centroid.tolist())
    with connection.cursor() as cur:
        cur.execute(
            f'SELECT building_id, name_en, project_name, architect, location_country, '
            f'city, year, area_sqm, program, style, atmosphere, color_tone, material, material_visual, url, tags, image_photos, image_drawings, '
            f'embedding::text FROM architecture_vectors {exclude_sql} '
            f'ORDER BY embedding <=> %s::vector LIMIT %s',
            params + [vec_str, k * 3],
        )
        rows = _dictfetchall(cur)

    if not rows:
        return []

    # Parse embeddings
    for row in rows:
        embedding_str = row['embedding']
        row['_vec'] = np.array([float(x) for x in embedding_str.strip('[]').split(',')])

    # MMR selection
    selected = []
    remaining = rows.copy()

    # Select first item with best relevance (multi-modal: max over all centroids)
    if remaining:
        best_idx = 0
        best_relevance = -1
        for i, row in enumerate(remaining):
            relevance = max(np.dot(row['_vec'], c) for c in centroids)
            if relevance > best_relevance:
                best_relevance = relevance
                best_idx = i
        selected.append(remaining.pop(best_idx))

    # Greedy MMR selection for remaining items
    while len(selected) < k and remaining:
        best_idx = 0
        best_score = -float('inf')

        for i, row in enumerate(remaining):
            candidate_emb = row['_vec']

            # Relevance: max cosine similarity to any centroid (multi-modal)
            relevance = max(np.dot(candidate_emb, c) for c in centroids)

            # Redundancy: max similarity to already selected
            redundancy = 0
            for sel in selected:
                sel_emb = sel['_vec']
                redundancy = max(redundancy, np.dot(candidate_emb, sel_emb))

            # MMR score
            mmr_score = relevance - RC['mmr_penalty'] * redundancy

            if mmr_score > best_score:
                best_score = mmr_score
                best_idx = i

        selected.append(remaining.pop(best_idx))

    # Convert to ImageCard format
    return [_row_to_card(row) for row in selected]
