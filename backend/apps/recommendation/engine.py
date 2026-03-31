"""
engine.py — Recommendation algorithm using pgvector.
All DB access is raw SQL against architecture_vectors (owned by Make DB).
"""
import math
import random
import logging
from django.conf import settings
from django.db import connection

logger = logging.getLogger('apps.recommendation')

RC = settings.RECOMMENDATION  # shorthand for constants


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


def select_next_image(pref_vector, exposed_ids, current_round, filters=None):
    """
    Epsilon-greedy next image selection.
    Returns an ImageCard dict, or None if no candidates remain.
    """
    epsilon = max(
        RC['min_epsilon'],
        RC['initial_epsilon'] * ((1 - RC['epsilon_decay']) ** current_round),
    )

    exclude_sql = ''
    params_base = []
    if exposed_ids:
        placeholders = ','.join(['%s'] * len(exposed_ids))
        exclude_sql = f'building_id NOT IN ({placeholders})'
        params_base = list(exposed_ids)

    filter_where, filter_params = _build_filter_sql(filters)

    def _combined_where(extra=''):
        parts = []
        if exclude_sql:
            parts.append(exclude_sql)
        if filter_where:
            parts.append(filter_where.replace('WHERE ', ''))
        if extra:
            parts.append(extra)
        return ('WHERE ' + ' AND '.join(parts)) if parts else ''

    if random.random() < epsilon or not pref_vector:
        # Explore: random unexposed building
        where = _combined_where()
        with connection.cursor() as cur:
            cur.execute(
                f'SELECT building_id, name_en, project_name, architect, location_country, '
                f'city, year, area_sqm, program, style, atmosphere, color_tone, material, material_visual, url, tags, image_photos, image_drawings '
                f'FROM architecture_vectors {where} ORDER BY RANDOM() LIMIT 1',
                params_base + filter_params,
            )
            rows = _dictfetchall(cur)
    else:
        # Exploit: most similar to preference vector
        vec_str = _vec_to_pg(pref_vector)
        where = _combined_where()
        with connection.cursor() as cur:
            cur.execute(
                f'SELECT building_id, name_en, project_name, architect, location_country, '
                f'city, year, area_sqm, program, style, atmosphere, color_tone, material, material_visual, url, tags, image_photos, image_drawings '
                f'FROM architecture_vectors {where} '
                f'ORDER BY embedding <=> %s::vector LIMIT 1',
                params_base + filter_params + [vec_str],
            )
            rows = _dictfetchall(cur)

    return _row_to_card(rows[0]) if rows else None


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
