"""
test_inspect.py — ADMIN-DBCHECK-1: internal DB-quality inspection API.

Coverage:
  - InspectBuildingsListView: 401 unauthenticated, pagination shape (mocked
    connections['buildings'] cursor + mocked engine.get_buildings_by_ids),
    next_after null on last (short) page, cached total.
  - InspectBuildingDetailView: 401 unauthenticated, 404 on missing/non-publishable
    row, 200 flat shape with embedding_present/embedding_dim and no raw embedding.
  - InspectSearchView: 401 unauthenticated, 400 on missing/oversized query,
    mocked engine.search_by_filters_scored (no LLM parsing, no live
    DB), fallback path when search returns empty.

No real DB round-trip against canonical_v2_buildings — all raw-SQL cursor use
is mocked via patch('apps.recommendation.views.inspect.connections').
"""
from unittest.mock import MagicMock, patch

import pytest

from django.core.cache import cache

_MOCK_CARD = {
    'building_id': 'bld_000001',
    'canonical_bld_id': 'bld_000001',
    'name_en': 'Test Building',
    'image_url': 'https://example.com/img.jpg',
}


_UNSET = object()


def _cursor_mock(fetchall_rows=None, fetchone_row=_UNSET, description=None):
    cur = MagicMock()
    cur.__enter__ = lambda s: s
    cur.__exit__ = MagicMock(return_value=False)
    if fetchall_rows is not None:
        cur.fetchall.return_value = fetchall_rows
    if fetchone_row is not _UNSET:
        cur.fetchone.return_value = fetchone_row
    if description is not None:
        cur.description = description
    return cur


def _connections_mock(cursors):
    """connections['buildings'].cursor() side_effect over successive cursor mocks."""
    conn = MagicMock()
    conn.cursor.side_effect = cursors
    connections = MagicMock()
    connections.__getitem__.return_value = conn
    return connections


@pytest.fixture(autouse=True)
def _clear_inspect_cache():
    cache.delete('inspect:total_publishable')
    yield
    cache.delete('inspect:total_publishable')


# ── InspectBuildingsListView ───────────────────────────────────────────────────

@pytest.mark.django_db
class TestInspectBuildingsList:

    def test_unauthenticated_returns_401(self, api_client):
        resp = api_client.get('/api/v1/inspect/buildings/')
        assert resp.status_code == 401

    def test_non_admin_user_returns_403(self, auth_client):
        """ADMIN-DASH-1: a plain authenticated user is no longer enough."""
        assert auth_client.get('/api/v1/inspect/buildings/').status_code == 403
        assert auth_client.get('/api/v1/inspect/buildings/bld_000001/').status_code == 403
        assert auth_client.post('/api/v1/inspect/search/', {'query': 'x'}, format='json').status_code == 403

    def test_pagination_shape_full_page(self, admin_client):
        """page_size rows returned -> next_after is the last id, total cached."""
        ids = [('bld_000001',), ('bld_000002',)]
        id_cursor = _cursor_mock(fetchall_rows=ids)
        count_cursor = _cursor_mock(fetchone_row=(2500,))
        mock_connections = _connections_mock([id_cursor, count_cursor])

        with patch('apps.recommendation.views.inspect.connections', mock_connections), \
             patch('apps.recommendation.views.inspect.engine.get_buildings_by_ids',
                   return_value=[_MOCK_CARD, _MOCK_CARD]) as mock_hydrate:
            resp = admin_client.get('/api/v1/inspect/buildings/?page_size=2')

        assert resp.status_code == 200, resp.json()
        data = resp.json()
        assert data['results'] == [_MOCK_CARD, _MOCK_CARD]
        assert data['next_after'] == 'bld_000002'
        assert data['total'] == 2500
        mock_hydrate.assert_called_once_with(['bld_000001', 'bld_000002'])

    def test_pagination_last_page_next_after_null(self, admin_client):
        """Fewer rows than page_size -> next_after is null (last page)."""
        ids = [('bld_000099',)]
        id_cursor = _cursor_mock(fetchall_rows=ids)
        count_cursor = _cursor_mock(fetchone_row=(1,))
        mock_connections = _connections_mock([id_cursor, count_cursor])

        with patch('apps.recommendation.views.inspect.connections', mock_connections), \
             patch('apps.recommendation.views.inspect.engine.get_buildings_by_ids',
                   return_value=[_MOCK_CARD]):
            resp = admin_client.get('/api/v1/inspect/buildings/?page_size=60')

        assert resp.status_code == 200, resp.json()
        data = resp.json()
        assert data['next_after'] is None

    def test_after_cursor_passed_to_sql(self, admin_client):
        """after= param must be forwarded as a bind parameter (parameterized SQL)."""
        id_cursor = _cursor_mock(fetchall_rows=[])
        count_cursor = _cursor_mock(fetchone_row=(0,))
        mock_connections = _connections_mock([id_cursor, count_cursor])

        with patch('apps.recommendation.views.inspect.connections', mock_connections), \
             patch('apps.recommendation.views.inspect.engine.get_buildings_by_ids',
                   return_value=[]):
            resp = admin_client.get('/api/v1/inspect/buildings/?after=bld_000050')

        assert resp.status_code == 200
        sql, params = id_cursor.execute.call_args[0]
        assert '%s' in sql
        assert 'bld_000050' in params
        assert 'is_publishable = true' in sql

    def test_page_size_capped_at_100(self, admin_client):
        id_cursor = _cursor_mock(fetchall_rows=[])
        count_cursor = _cursor_mock(fetchone_row=(0,))
        mock_connections = _connections_mock([id_cursor, count_cursor])

        with patch('apps.recommendation.views.inspect.connections', mock_connections), \
             patch('apps.recommendation.views.inspect.engine.get_buildings_by_ids',
                   return_value=[]):
            resp = admin_client.get('/api/v1/inspect/buildings/?page_size=9999')

        assert resp.status_code == 200
        _sql, params = id_cursor.execute.call_args[0]
        assert params[-1] == 100

    def test_total_is_cached_across_requests(self, admin_client):
        """Second request must not re-issue the count query (cache hit)."""
        id_cursor_1 = _cursor_mock(fetchall_rows=[])
        count_cursor = _cursor_mock(fetchone_row=(42,))
        mock_connections_1 = _connections_mock([id_cursor_1, count_cursor])

        with patch('apps.recommendation.views.inspect.connections', mock_connections_1), \
             patch('apps.recommendation.views.inspect.engine.get_buildings_by_ids',
                   return_value=[]):
            resp1 = admin_client.get('/api/v1/inspect/buildings/')
        assert resp1.json()['total'] == 42

        # Second call: only the id-cursor should fire; count cursor absent from
        # side_effect list would raise StopIteration if the view tried to query it.
        id_cursor_2 = _cursor_mock(fetchall_rows=[])
        mock_connections_2 = _connections_mock([id_cursor_2])

        with patch('apps.recommendation.views.inspect.connections', mock_connections_2), \
             patch('apps.recommendation.views.inspect.engine.get_buildings_by_ids',
                   return_value=[]):
            resp2 = admin_client.get('/api/v1/inspect/buildings/')
        assert resp2.status_code == 200
        assert resp2.json()['total'] == 42


# ── InspectBuildingDetailView ──────────────────────────────────────────────────

@pytest.mark.django_db
class TestInspectBuildingDetail:

    def test_unauthenticated_returns_401(self, api_client):
        resp = api_client.get('/api/v1/inspect/buildings/bld_000001/')
        assert resp.status_code == 401

    def test_404_on_missing_or_non_publishable(self, admin_client):
        cur = _cursor_mock(fetchone_row=None)
        mock_connections = _connections_mock([cur])

        with patch('apps.recommendation.views.inspect.connections', mock_connections):
            resp = admin_client.get('/api/v1/inspect/buildings/bld_999999/')

        assert resp.status_code == 404

    def test_detail_shape_excludes_raw_embedding_includes_presence_fields(self, admin_client):
        cols = [
            'canonical_bld_id', 'name', 'names_alts', 'location_city', 'location_country',
            'project_year', 'architect_canonical_ids', 'architect_names', 'architects_text',
            'program', 'style', 'color_tone', 'atmosphere', 'material_visual',
            'visual_description', 'image_derived', 'covers_by_type', 'all_images',
            'best_image_per_cluster', 'cover_image_url_default', 'display_cover_url',
            'source_refs', 'source_urls', 'identity_source', 'confidence_tier', 'n_sources',
            'is_publishable', 'publishability_reasons', 'needs_image_derived_backfill',
            'typology_primary', 'typology_tags', 'architectural_elements', 'updated_at',
            'embedding_present', 'embedding_dim',
        ]
        row = tuple(
            {
                'canonical_bld_id': 'bld_000001',
                'name': 'Test',
                'is_publishable': True,
                'embedding_present': True,
                'embedding_dim': 384,
            }.get(c, None)
            for c in cols
        )
        cur = _cursor_mock(fetchone_row=row, description=[(c,) for c in cols])
        mock_connections = _connections_mock([cur])

        with patch('apps.recommendation.views.inspect.connections', mock_connections):
            resp = admin_client.get('/api/v1/inspect/buildings/bld_000001/')

        assert resp.status_code == 200, resp.json()
        data = resp.json()
        assert data['canonical_bld_id'] == 'bld_000001'
        assert data['embedding_present'] is True
        assert data['embedding_dim'] == 384
        assert 'embedding' not in data

        # SQL must be parameterized (no f-string of the id into the query text).
        sql, params = cur.execute.call_args[0]
        assert 'bld_000001' not in sql
        assert params == ['bld_000001']
        assert 'is_publishable = true' in sql
        assert 'vector_dims' in sql

    def test_updated_at_serialized_isoformat(self, admin_client):
        import datetime
        cols = ['canonical_bld_id', 'updated_at', 'embedding_present', 'embedding_dim']
        dt = datetime.datetime(2026, 1, 1, 12, 0, 0)
        row = ('bld_000002', dt, True, 384)
        cur = _cursor_mock(fetchone_row=row, description=[(c,) for c in cols])
        mock_connections = _connections_mock([cur])

        with patch('apps.recommendation.views.inspect.connections', mock_connections):
            resp = admin_client.get('/api/v1/inspect/buildings/bld_000002/')

        assert resp.status_code == 200
        assert resp.json()['updated_at'] == dt.isoformat()


# ── InspectSearchView ──────────────────────────────────────────────────────────

@pytest.mark.django_db
class TestInspectSearch:

    def test_unauthenticated_returns_401(self, api_client):
        resp = api_client.post('/api/v1/inspect/search/', {'query': 'brutalist museum'}, format='json')
        assert resp.status_code == 401

    def test_missing_query_returns_400(self, admin_client):
        resp = admin_client.post('/api/v1/inspect/search/', {}, format='json')
        assert resp.status_code == 400

    def test_blank_query_returns_400(self, admin_client):
        resp = admin_client.post('/api/v1/inspect/search/', {'query': '   '}, format='json')
        assert resp.status_code == 400

    def test_oversized_query_returns_400(self, admin_client):
        resp = admin_client.post(
            '/api/v1/inspect/search/', {'query': 'x' * 2001}, format='json',
        )
        assert resp.status_code == 400

    def test_search_success_mocked(self, admin_client):
        with patch('apps.recommendation.views.inspect.engine.search_by_filters_scored',
                   return_value=[_MOCK_CARD]) as mock_search:
            resp = admin_client.post(
                '/api/v1/inspect/search/',
                {'query': 'brutalist museum', 'limit': 50},
                format='json',
            )

        assert resp.status_code == 200, resp.json()
        data = resp.json()
        assert data['results'] == [_MOCK_CARD]
        # No LLM parsing: filters are empty, raw query text drives ranking.
        assert data['structured_filters'] == {}
        assert data['filter_priority'] == []
        assert data['visual_description'] is None
        assert data['is_fallback'] is False

        args, search_kwargs = mock_search.call_args
        assert args[0] == {}
        assert search_kwargs['raw_query'] == 'brutalist museum'
        assert search_kwargs['limit'] == 50
        assert search_kwargs['filter_priority'] == []

    def test_limit_capped_at_100(self, admin_client):
        with patch('apps.recommendation.views.inspect.engine.search_by_filters_scored',
                   return_value=[_MOCK_CARD]) as mock_search:
            resp = admin_client.post(
                '/api/v1/inspect/search/', {'query': 'q', 'limit': 5000}, format='json',
            )
        assert resp.status_code == 200
        _, search_kwargs = mock_search.call_args
        assert search_kwargs['limit'] == 100

    def test_fallback_when_search_returns_empty(self, admin_client):
        search_patch = patch(
            'apps.recommendation.views.inspect.engine.search_by_filters_scored',
            return_value=[],
        )
        random_patch = patch(
            'apps.recommendation.views.inspect.engine.get_diverse_random',
            return_value=[_MOCK_CARD],
        )
        with search_patch, random_patch as mock_random:
            resp = admin_client.post(
                '/api/v1/inspect/search/', {'query': 'zzz nonsense'}, format='json',
            )
        assert resp.status_code == 200, resp.json()
        data = resp.json()
        assert data['is_fallback'] is True
        assert data['results'] == [_MOCK_CARD]
        mock_random.assert_called_once()
