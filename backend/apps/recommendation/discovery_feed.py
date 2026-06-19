"""
discovery_feed.py — Discovery tab v3.2 chunk builder.

Pure functions: no engine.py edits. Imports engine helpers read-only.

Architecture:
  - create_discovery_draft       — create a new per-session timestamped draft board
  - get_discovery_draft          — look up a draft by id (ownership + prefix guard)
  - is_discovery_draft_name      — predicate for draft-board name detection
  - compute_discovery_tier       — 3-Tier logic (cold / single / multi)
  - build_discovery_chunk        — Exclusion Zone + FPS split + micro-interleave

Hard rules (also in CLAUDE.md):
  - All building SQL gates on is_publishable = true.
  - canonical_v2_buildings accessed via raw SQL on the 'buildings' connection only.
  - No ORM/migrate on canonical_v2_buildings.
  - engine.py is read-only (import, never modify).
"""
import random
import logging

import numpy as np
from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import connections as _dj_connections
from django.utils import timezone

from .models import Project
from . import engine
from .engine_vecmath import _normalize
from .engine_cards import _row_to_card

logger = logging.getLogger('apps.recommendation')

RC = settings.RECOMMENDATION  # shorthand

# Per-session draft boards are named with this prefix (e.g. 'discovery_260604_1430').
# These are normal visible boards — shown on the profile, not hidden.
DISCOVERY_DRAFT_PREFIX = 'discovery_'


# ── Local helper (avoids circular import through views._shared) ───────────────

def _liked_id_only(liked_ids):
    """Extract building_id strings from liked_ids (list[str] or list[{id,intensity}])."""
    return [
        entry if isinstance(entry, str) else entry['id']
        for entry in (liked_ids or [])
        if isinstance(entry, str) or (isinstance(entry, dict) and 'id' in entry)
    ]


# ── Draft name predicate ──────────────────────────────────────────────────────

def is_discovery_draft_name(name):
    """Return True iff `name` looks like a discovery draft board name."""
    return bool(name) and name.startswith(DISCOVERY_DRAFT_PREFIX)


# ── Draft Project helpers ─────────────────────────────────────────────────────

def create_discovery_draft(profile):
    """Create a brand-new per-session Discovery draft Project.

    Name format: 'discovery_YYMMDD_HHMM' (e.g. 'discovery_260604_1430').
    Every call creates a NEW board — NOT get_or_create.

    The draft holds:
      liked_ids    = Discovery right-swipes [{id, intensity}]
      disliked_ids = Discovery passes (list[str], rolling history)

    Draft boards are visible on the profile (normal boards with a
    name-prefix convention, not a hidden reserved name).
    """
    name = DISCOVERY_DRAFT_PREFIX + timezone.now().strftime('%y%m%d_%H%M')
    draft = Project.objects.create(
        user=profile,
        name=name,
        visibility='private',
    )
    return draft


def get_discovery_draft(profile, draft_id):
    """Return a draft Project by UUID iff it exists, is owned by profile,
    and its name starts with DISCOVERY_DRAFT_PREFIX.

    Returns None if:
      - project does not exist
      - project belongs to a different user
      - project name does not start with DISCOVERY_DRAFT_PREFIX
    """
    if not draft_id:
        return None
    try:
        draft = Project.objects.get(project_id=draft_id, user=profile)
    except (Project.DoesNotExist, ValueError, ValidationError):
        return None
    if not is_discovery_draft_name(draft.name):
        return None
    return draft


# ── Tier computation ──────────────────────────────────────────────────────────

def _tier_from_project_rows(rows):
    """Pure-function tier computation from pre-fetched project rows.

    rows: iterable of dicts with at least {'name': str, 'liked_ids': list|None}.
    Scoped to the rows provided — callers are responsible for applying any cap.

    Tier thresholds (from RECOMMENDATION dict):
      Tier 1 (cold)   : cumulative_likes < discovery_tier2_min_likes (10)
      Tier 3 (multi)  : project_count >= discovery_tier3_min_projects (2)
                        OR cumulative_likes >= discovery_tier3_min_likes (50)
      Tier 2 (single) : else (likes >= 10 AND projects <= 1)

    project_count: EXCLUDES auto draft boards (name starts with 'discovery_').
    cumulative_likes: includes ALL provided rows (drafts + real).

    n_local + n_global = discovery_chunk_size (10).
    """
    tier2_min_likes = RC.get('discovery_tier2_min_likes', 10)
    tier3_min_projects = RC.get('discovery_tier3_min_projects', 2)
    tier3_min_likes = RC.get('discovery_tier3_min_likes', 50)
    chunk_size = RC.get('discovery_chunk_size', 10)
    t2_local = RC.get('discovery_tier2_local', 2)
    t2_global = RC.get('discovery_tier2_global', 8)
    t3_local = RC.get('discovery_tier3_local', 4)
    t3_global = RC.get('discovery_tier3_global', 6)

    cumulative_likes = 0
    project_count = 0
    for p in rows:
        liked = p.get('liked_ids') or []
        cumulative_likes += len(liked)
        # Draft boards (name starts with DISCOVERY_DRAFT_PREFIX) are excluded
        # from the tier project_count but their likes still accumulate.
        if not is_discovery_draft_name(p['name']):
            project_count += 1

    # Determine tier
    if cumulative_likes < tier2_min_likes:
        tier = 1
        n_local = 0
        n_global = chunk_size
    elif project_count >= tier3_min_projects or cumulative_likes >= tier3_min_likes:
        tier = 3
        n_local = t3_local
        n_global = t3_global
        # Ensure sum == chunk_size (config values should be correct, but guard)
        if n_local + n_global != chunk_size:
            n_global = chunk_size - n_local
    else:
        tier = 2
        n_local = t2_local
        n_global = t2_global
        if n_local + n_global != chunk_size:
            n_global = chunk_size - n_local

    return {
        'tier': tier,
        'n_local': n_local,
        'n_global': n_global,
        'cumulative_likes': cumulative_likes,
        'project_count': project_count,
    }


def compute_discovery_tier(profile):
    """Return tier dict: tier (1|2|3), n_local, n_global, cumulative_likes, project_count.

    Thin wrapper: fetches the most-recent discovery_recent_boards_cap (default 10)
    boards and delegates to _tier_from_project_rows().  Kept for backwards
    compatibility with callers that do not pre-fetch rows themselves.

    project_count: EXCLUDES auto draft boards (name starts with 'discovery_').
    cumulative_likes: from the capped board window only.

    n_local + n_global = discovery_chunk_size (10).
    """
    cap = RC.get('discovery_recent_boards_cap', 10)
    rows = list(
        Project.objects.filter(user=profile)
        .order_by('-created_at')[:cap]
        .values('name', 'liked_ids')
    )
    return _tier_from_project_rows(rows)


# ── Greedy FPS (mirrors engine.py lines 222-235) ──────────────────────────────

def _greedy_fps(rows, n):
    """Greedy farthest-point sampling over `rows` (each has '_vec' float list).

    Starts from rows[0], then iteratively picks the row maximising
    minimum cosine distance to already-selected rows.

    Returns up to n rows. Does NOT modify the input list.
    """
    if not rows:
        return []
    if n <= 0:
        return []
    if len(rows) <= n:
        return list(rows)

    selected = [rows[0]]
    remaining = list(rows[1:])
    while len(selected) < n and remaining:
        best_idx, best_dist = 0, -1.0
        for i, r in enumerate(remaining):
            min_sim = min(
                sum(a * b for a, b in zip(r['_vec'], s['_vec']))
                for s in selected
            )
            dist = 1.0 - min_sim  # cosine distance
            if dist > best_dist:
                best_idx, best_dist = i, dist
        selected.append(remaining.pop(best_idx))
    return selected


# ── Micro-interleave ──────────────────────────────────────────────────────────

def _interleave_local_global(local_rows, global_rows):
    """Place local (L=취향) and global (G=탐험) cards in the pattern [G,L,G,G,L,G,L,G,G,L].

    The pattern has 10 slots. L positions are at indices [1, 4, 6, 9] (0-based)
    for the 40:60 default (4 local out of 10). For other ratios we spread L items
    at evenly-spaced positions across the total count.

    If fewer items than the chunk, we still do best-effort placement.
    """
    total = len(local_rows) + len(global_rows)
    if total == 0:
        return []

    n_local = len(local_rows)
    n_global = len(global_rows)

    if n_local == 0:
        return list(global_rows)
    if n_global == 0:
        return list(local_rows)

    # Compute evenly-spaced L positions across `total` slots
    # e.g. n_local=4, total=10 → positions at floor(total/(n_local+1) * k) for k in 1..n_local
    l_positions = set()
    for k in range(1, n_local + 1):
        pos = int(round(total * k / (n_local + 1)))
        # Clamp to valid range
        pos = max(0, min(total - 1, pos))
        l_positions.add(pos)

    # Ensure exactly n_local positions (adjust in case of collision)
    while len(l_positions) < n_local:
        for i in range(total):
            if i not in l_positions:
                l_positions.add(i)
                break

    result = [None] * total
    l_iter = iter(local_rows)
    g_iter = iter(global_rows)

    for i in range(total):
        if i in l_positions:
            try:
                result[i] = next(l_iter)
            except StopIteration:
                result[i] = next(g_iter, None)
        else:
            try:
                result[i] = next(g_iter)
            except StopIteration:
                result[i] = next(l_iter, None)

    return [r for r in result if r is not None]


# ── Candidate fetch (raw SQL, 2-query pattern) ────────────────────────────────

def _fetch_candidates(exclude_ids, dislike_centroid, chunk_size):
    """Fetch a bounded set of candidate buildings from canonical_v2_buildings.

    Uses the same 2-query pattern as engine.get_diverse_random:
      1) Fetch IDs only (fast, no heavy columns) with exclusion + dislike-zone filter.
      2) Python random.sample to bound the set.
      3) Fetch full rows + embeddings for the sample.

    dislike_centroid: list[float] or None. When set, adds a pgvector cosine
    DISTANCE filter so candidates must be farther than
    discovery_dislike_zone_threshold from the centroid.

    Returns list of row dicts (each row has 'embedding' text field for parsing).
    """
    dislike_zone_threshold = RC.get('discovery_dislike_zone_threshold', 0.15)
    # Oversample: chunk_size * 8 capped at 120 — enough for FPS to work on
    sample_cap = min(chunk_size * 8, 120)

    # Build required columns (mirrors get_diverse_random)
    # _build_select_columns lives in engine.py, not engine_cards.py
    from .engine import _build_select_columns as _bsc
    _required_cols = [
        'canonical_bld_id', 'name', 'architect_names', 'architects_text',
        'location_country', 'location_city', 'project_year',
        'program', 'style', 'atmosphere', 'color_tone', 'material_visual',
        'typology_primary', 'typology_tags', 'architectural_elements',
        'visual_description',
        'covers_by_type', 'all_images', 'display_cover_url',
        'cover_image_url_default', 'source_urls',
    ]
    _cols = _bsc(_required_cols, ())

    conn = _dj_connections['buildings']

    # ── Query 1: ID-only fetch with exclusion + optional dislike zone ──────
    params_1 = []
    where_parts = ['is_publishable = true']

    if exclude_ids:
        where_parts.append('canonical_bld_id <> ALL(%s)')
        params_1.append(list(exclude_ids))

    if dislike_centroid is not None:
        # pgvector cosine distance operator <=>; candidates must be FARTHER than threshold
        from .engine_vecmath import _vec_to_pg
        centroid_str = _vec_to_pg(dislike_centroid)
        where_parts.append('embedding <=> %s::vector > %s')
        params_1.extend([centroid_str, dislike_zone_threshold])

    where_sql = 'WHERE ' + ' AND '.join(where_parts)

    with conn.cursor() as cur:
        cur.execute(
            f'SELECT canonical_bld_id FROM canonical_v2_buildings {where_sql}',
            params_1,
        )
        all_ids = [row[0] for row in cur.fetchall()]

    if not all_ids:
        return []

    # ── Python sample (no ORDER BY RANDOM() full-corpus sort) ─────────────
    sampled_ids = random.sample(all_ids, min(sample_cap, len(all_ids)))

    # ── Query 2: full rows + embedding for sample ──────────────────────────
    # Must re-gate on is_publishable = true (rows could theoretically change
    # between query 1 and query 2; CLAUDE.md requires it on every query).
    with conn.cursor() as cur:
        cur.execute(
            f'SELECT {_cols}, embedding::text FROM canonical_v2_buildings'
            f' WHERE canonical_bld_id = ANY(%s) AND is_publishable = true',
            [sampled_ids],
        )
        cols = [c[0] for c in cur.description]
        rows = [dict(zip(cols, row)) for row in cur.fetchall()]

    # Restore sample order (Postgres ANY returns PK order)
    rows_by_id = {r['canonical_bld_id']: r for r in rows}
    return [rows_by_id[bid] for bid in sampled_ids if bid in rows_by_id]


# ── Main chunk builder ────────────────────────────────────────────────────────

def build_discovery_chunk(
    profile,
    centroids,
    client_buffer_ids=None,
    chunk_size=None,
    # DISCOVERY-PERF-1: pre-fetched project rows (recent-cap boards only).
    # When provided, these rows are used for exclude_set (board part) and
    # dislike aggregation — no additional DB query is issued.
    # When None, a fresh capped fetch is performed internally (backwards-compat).
    _project_rows=None,
    # Pre-computed tier_info dict (from _tier_from_project_rows / compute_discovery_tier).
    # When None, computed from _project_rows (or fetched internally).
    _tier_info=None,
):
    """Build a 10-card Discovery chunk for the given profile.

    Steps:
      1. Use pre-fetched _project_rows (most-recent cap boards) — or fetch them.
         Build exclude set from those rows (liked + disliked + saved).
         PLUS profile.liked_building_ids and client_buffer_ids (no cap on these).
      2. Aggregate disliked_ids from _project_rows for the dislike centroid.
         If no passes, no dislike zone.
      3. Fetch candidates via 2-query pattern (IDs only → sample → full rows).
      4. Parse embeddings.
      5. Split into local (sim >= discovery_local_sim_radius to any centroid)
         and global (farther) pools.
      6. Greedy FPS pick n_local from local pool, n_global from global pool;
         backfill if either pool is short.
      7. Micro-interleave and return _row_to_card dicts.

    centroids: list of np.ndarray or list of list[float] (may be empty for cold).
    client_buffer_ids: optional iterable of building id strings already shown
        to the client but not yet acted on.
    _project_rows: pre-fetched list of dicts (name/liked_ids/disliked_ids/saved_ids).
        Scoped to recent-cap boards. Pass from the view to avoid re-querying.
    _tier_info: pre-computed tier dict. If None, derived from _project_rows.
    """
    if chunk_size is None:
        chunk_size = RC.get('discovery_chunk_size', 10)

    dislike_window = RC.get('discovery_dislike_history_window', 30)
    local_sim_radius = RC.get('discovery_local_sim_radius', 0.55)

    # ── Resolve project rows (1 fetch if not pre-supplied) ─────────────────
    if _project_rows is None:
        cap = RC.get('discovery_recent_boards_cap', 10)
        _project_rows = list(
            Project.objects.filter(user=profile)
            .order_by('-created_at')[:cap]
            .values('name', 'liked_ids', 'disliked_ids', 'saved_ids')
        )

    # ── Compute tier split (from pre-fetched rows) ─────────────────────────
    if _tier_info is None:
        _tier_info = _tier_from_project_rows(_project_rows)
    n_local = _tier_info['n_local']
    n_global = _tier_info['n_global']

    # ── Build exclude set (board part: from recent-cap rows only) ──────────
    # DISCOVERY-PERF-1: exclude_set boards are scoped to the recent-cap window.
    # Older boards' buildings may re-appear — this is the intended product spec.
    exclude_set = set()
    for project in _project_rows:
        for bid in _liked_id_only(project.get('liked_ids')):
            if isinstance(bid, str):
                exclude_set.add(bid)
        for bid in (project.get('disliked_ids') or []):
            if isinstance(bid, str):
                exclude_set.add(bid)
        for entry in (project.get('saved_ids') or []):
            if isinstance(entry, dict):
                bid = entry.get('id')
            else:
                bid = entry
            if isinstance(bid, str) and bid:
                exclude_set.add(bid)

    # BACK-RECOMMEND-4: also exclude buildings liked via the Profile
    # "liked buildings" tab (UserProfile.liked_building_ids) so they
    # don't reappear in the Discovery chunk. No cap — cost is O(0) DB hits.
    for bid in list(profile.liked_building_ids or []):
        if isinstance(bid, str) and bid:
            exclude_set.add(bid)

    if client_buffer_ids:
        for bid in client_buffer_ids:
            if isinstance(bid, str) and bid:
                exclude_set.add(bid)

    # ── Dislike centroid (rolling window, from recent-cap rows) ───────────
    # Aggregate disliked_ids from the capped project rows.
    # Ordering is preserved within each project's list; interleaving across
    # projects is not strictly temporal (acceptable trade-off).
    all_dislike_ids = []
    for project in _project_rows:
        disliked = project.get('disliked_ids') or []
        if isinstance(disliked, list):
            all_dislike_ids.extend(bid for bid in disliked if isinstance(bid, str))
    recent_dislike_ids = all_dislike_ids[-dislike_window:]

    dislike_centroid = None
    if recent_dislike_ids:
        emb_map = engine.get_pool_embeddings(recent_dislike_ids)
        vecs = [emb_map[bid] for bid in recent_dislike_ids if bid in emb_map]
        if vecs:
            mean_vec = np.mean(np.stack(vecs), axis=0)
            normed = _normalize(mean_vec.tolist())
            dislike_centroid = normed if normed else None

    # ── Fetch candidates ───────────────────────────────────────────────────
    rows = _fetch_candidates(exclude_set, dislike_centroid, chunk_size)
    if not rows:
        return []

    # ── Parse embeddings ───────────────────────────────────────────────────
    parsed_rows = []
    for row in rows:
        raw = row.get('embedding')
        if not raw:
            continue
        vec = [float(x) for x in raw.strip('[]').split(',')]
        row['_vec'] = vec
        parsed_rows.append(row)

    if not parsed_rows:
        return []

    # ── Split into local / global pools ───────────────────────────────────
    # Normalise centroids to plain float lists for dot-product comparison
    centroid_vecs = []
    for c in (centroids or []):
        if isinstance(c, np.ndarray):
            centroid_vecs.append(c.tolist())
        else:
            centroid_vecs.append(list(c))

    local_pool = []
    global_pool = []

    if not centroid_vecs:
        # Cold / Tier 1: all candidates go to global pool
        global_pool = parsed_rows
    else:
        for row in parsed_rows:
            v = row['_vec']
            max_sim = max(
                sum(a * b for a, b in zip(v, cv))
                for cv in centroid_vecs
            )
            if max_sim >= local_sim_radius:
                local_pool.append(row)
            else:
                global_pool.append(row)

    # ── Greedy FPS pick with backfill ─────────────────────────────────────
    local_selected = _greedy_fps(local_pool, n_local)
    global_selected = _greedy_fps(global_pool, n_global)

    # Track selected ids to prevent duplicates in backfill.
    selected_ids = set()
    for r in local_selected:
        selected_ids.add(r['canonical_bld_id'])
    for r in global_selected:
        selected_ids.add(r['canonical_bld_id'])

    # Backfill: if a pool came up short, fill the deficit from the OTHER
    # pool's unused candidates (those not already selected).
    #
    # NOTE: _greedy_fps returns at most n items, so the previous guards
    # "len(global_selected) > n_global" were permanently False.  The correct
    # check is whether a deficit exists and unused candidates are available.
    local_deficit = n_local - len(local_selected)
    global_deficit = n_global - len(global_selected)

    if local_deficit > 0:
        unused_global = [r for r in global_pool if r['canonical_bld_id'] not in selected_ids]
        backfill = _greedy_fps(unused_global, local_deficit)
        for r in backfill:
            local_selected.append(r)
            selected_ids.add(r['canonical_bld_id'])

    if global_deficit > 0:
        unused_local = [r for r in local_pool if r['canonical_bld_id'] not in selected_ids]
        backfill = _greedy_fps(unused_local, global_deficit)
        for r in backfill:
            global_selected.append(r)
            selected_ids.add(r['canonical_bld_id'])

    # ── Micro-interleave ──────────────────────────────────────────────────
    interleaved = _interleave_local_global(local_selected, global_selected)

    return [_row_to_card(r) for r in interleaved]
