"""inspect.py -- ADMIN-DBCHECK-1: internal DB-quality inspection endpoints.

Three read-only, IsAuthenticated endpoints used by the internal /db-check
frontend tool to eyeball the full canonical_v2_buildings corpus:

  GET  /api/v1/inspect/buildings/            -- keyset-paginated grid list
  GET  /api/v1/inspect/buildings/<id>/       -- full row detail (minus raw embedding)
  POST /api/v1/inspect/search/               -- natural-language search, larger limit

DB notes (HARD RULES):
  - canonical_v2_buildings is Make-DB-owned; accessed via connections['buildings']
    (read-only raw SQL, never ORM/migrate).
  - Every query gates on is_publishable = true.
  - All SQL is parameterized -- no f-string interpolation of user input.
"""
import logging

from django.core.cache import cache
from django.db import connections
from django.shortcuts import get_object_or_404  # noqa: F401 -- kept for parity with sibling views
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .. import engine, services

logger = logging.getLogger('apps.recommendation')

_TOTAL_PUBLISHABLE_CACHE_KEY = 'inspect:total_publishable'
_TOTAL_PUBLISHABLE_TTL = 3600  # ~1h

_DEFAULT_PAGE_SIZE = 60
_MAX_PAGE_SIZE = 100

_MAX_SEARCH_QUERY_LEN = 2000
_DEFAULT_SEARCH_LIMIT = 100
_MAX_SEARCH_LIMIT = 100
_SEARCH_FALLBACK_N = 20


def _get_total_publishable():
    """Cached count of is_publishable=true rows. TTL ~1h (INSPECT-1 spec)."""
    cached = cache.get(_TOTAL_PUBLISHABLE_CACHE_KEY)
    if cached is not None:
        return cached
    with connections['buildings'].cursor() as cur:
        cur.execute(
            'SELECT count(*) FROM canonical_v2_buildings WHERE is_publishable = true'
        )
        total = cur.fetchone()[0]
    cache.set(_TOTAL_PUBLISHABLE_CACHE_KEY, total, _TOTAL_PUBLISHABLE_TTL)
    return total


class InspectBuildingsListView(APIView):
    """GET /api/v1/inspect/buildings/ -- keyset-paginated all-buildings grid.

    Query params:
      after:      optional canonical_bld_id cursor (exclusive lower bound)
      page_size:  optional int, default 60, cap 100

    Response:
      {
        "results": [ImageCard, ...],
        "next_after": <last canonical_bld_id in this page> | null,
        "total": <int, cached ~1h>,
      }
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        after = request.query_params.get('after') or None

        try:
            page_size = int(request.query_params.get('page_size', _DEFAULT_PAGE_SIZE))
        except (TypeError, ValueError):
            page_size = _DEFAULT_PAGE_SIZE
        if page_size <= 0:
            page_size = _DEFAULT_PAGE_SIZE
        page_size = min(page_size, _MAX_PAGE_SIZE)

        if after:
            sql = (
                'SELECT canonical_bld_id FROM canonical_v2_buildings'
                ' WHERE is_publishable = true AND canonical_bld_id > %s'
                ' ORDER BY canonical_bld_id'
                ' LIMIT %s'
            )
            params = [after, page_size]
        else:
            sql = (
                'SELECT canonical_bld_id FROM canonical_v2_buildings'
                ' WHERE is_publishable = true'
                ' ORDER BY canonical_bld_id'
                ' LIMIT %s'
            )
            params = [page_size]

        with connections['buildings'].cursor() as cur:
            cur.execute(sql, params)
            ids = [row[0] for row in cur.fetchall()]

        cards = engine.get_buildings_by_ids(ids) if ids else []

        next_after = ids[-1] if len(ids) == page_size and ids else None

        return Response({
            'results': cards,
            'next_after': next_after,
            'total': _get_total_publishable(),
        })


# Every non-embedding column listed in the spec. Order mirrors the spec list.
_DETAIL_COLUMNS = [
    'canonical_bld_id', 'name', 'names_alts', 'location_city', 'location_country',
    'project_year', 'architect_canonical_ids', 'architect_names', 'architects_text',
    'program', 'style', 'color_tone', 'atmosphere', 'material_visual',
    'visual_description', 'image_derived', 'covers_by_type', 'all_images',
    'best_image_per_cluster', 'cover_image_url_default', 'display_cover_url',
    'source_refs', 'source_urls', 'identity_source', 'confidence_tier', 'n_sources',
    'is_publishable', 'publishability_reasons', 'needs_image_derived_backfill',
    'typology_primary', 'typology_tags', 'architectural_elements', 'updated_at',
]

_DETAIL_SELECT_SQL = (
    'SELECT ' + ', '.join(_DETAIL_COLUMNS) + ', '
    '(embedding IS NOT NULL) AS embedding_present, '
    'CASE WHEN embedding IS NULL THEN NULL ELSE vector_dims(embedding) END AS embedding_dim '
    'FROM canonical_v2_buildings '
    'WHERE canonical_bld_id = %s AND is_publishable = true'
)


class InspectBuildingDetailView(APIView):
    """GET /api/v1/inspect/buildings/<canonical_bld_id>/ -- full row detail.

    Excludes the raw embedding vector; includes embedding_present/embedding_dim
    instead. 404 when the id does not exist or is not publishable.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request, canonical_bld_id):
        with connections['buildings'].cursor() as cur:
            cur.execute(_DETAIL_SELECT_SQL, [canonical_bld_id])
            row = cur.fetchone()
            if row is None:
                return Response(
                    {'detail': 'Building not found.'},
                    status=status.HTTP_404_NOT_FOUND,
                )
            cols = [c[0] for c in cur.description]

        data = dict(zip(cols, row))
        updated_at = data.get('updated_at')
        if updated_at is not None and hasattr(updated_at, 'isoformat'):
            data['updated_at'] = updated_at.isoformat()

        return Response(data)


class InspectSearchView(APIView):
    """POST /api/v1/inspect/search/ -- natural-language search, larger limit.

    Wraps the existing services.parse_query + engine.search_by_filters_scored
    internals (same call shape as ParseQueryView's single-turn path) without
    the probe/priors machinery -- a single-shot search for DB inspection.

    Body: {"query": str (required, max 2000 chars), "limit": int (optional, default
    100, cap 100)}
    """
    permission_classes = [IsAuthenticated]

    def post(self, request):
        query = request.data.get('query')
        if not isinstance(query, str) or not query.strip():
            return Response(
                {'detail': 'query is required.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        query = query.strip()
        if len(query) > _MAX_SEARCH_QUERY_LEN:
            return Response(
                {'detail': f'query too long (max {_MAX_SEARCH_QUERY_LEN} chars).'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        raw_limit = request.data.get('limit', _DEFAULT_SEARCH_LIMIT)
        try:
            limit = int(raw_limit)
        except (TypeError, ValueError):
            limit = _DEFAULT_SEARCH_LIMIT
        if limit <= 0:
            limit = _DEFAULT_SEARCH_LIMIT
        limit = min(limit, _MAX_SEARCH_LIMIT)

        # Mirror ParseQueryView's single-turn call: conversation_history is a
        # single user turn, no prior_filters/language (skip probe/priors machinery).
        conversation_history = [{'role': 'user', 'text': query}]
        parsed = services.parse_query(conversation_history)

        filters = parsed.get('filters') or {}
        filter_priority = parsed.get('filter_priority') or []
        raw_query = parsed.get('raw_query') or query
        image_focus = parsed.get('image_focus')
        visual_description = parsed.get('visual_description')

        has_signal = bool(filters) or bool(raw_query and raw_query.strip())
        results = []
        if has_signal:
            results = engine.search_by_filters_scored(
                filters,
                raw_query=raw_query,
                filter_priority=filter_priority,
                limit=limit,
                image_focus=image_focus,
            )

        is_fallback = False
        if not results:
            results = engine.get_diverse_random(
                n=min(_SEARCH_FALLBACK_N, limit), image_focus=image_focus,
            )
            is_fallback = True

        return Response({
            'results': results,
            'structured_filters': filters,
            'filter_priority': filter_priority,
            'visual_description': visual_description,
            'is_fallback': is_fallback,
        })
