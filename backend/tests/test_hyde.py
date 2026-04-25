"""
test_hyde.py -- Sprint 4 Topic 03: HyDE V_initial embedding + pool reranking.

Unit and integration tests for:
- embed_visual_description() service function
- Flag-gating (hyde_vinitial_enabled=False default)
- create_bounded_pool() HyDE paths (empty filters, empty cases, blended)
- create_pool_with_relaxation() v_initial threading
- Session creation wiring (v_initial stored, event emitted)
- Graceful degradation on HF failure

No real HF API calls are made — urllib.request.urlopen is mocked throughout.
No real DB queries against architecture_vectors — engine functions are mocked
for integration tests following the test_sessions.py pattern.
"""
import io
import json
import urllib.error
import pytest
from unittest.mock import patch, MagicMock
from django.conf import settings

from apps.recommendation import services
from apps.recommendation.engine import (
    create_bounded_pool,
    create_pool_with_relaxation,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_HF_URL = 'apps.recommendation.services.urllib.request.urlopen'
_EMBED_FN = 'apps.recommendation.services.embed_visual_description'
_FAKE_VEC = [0.01] * 384  # simple 384-dim float list (not unit-normalised; fine for tests)


def _make_hf_response(vec, status_code=200):
    """Build a mock urllib response returning the given vector as JSON."""
    resp = MagicMock()
    resp.status = status_code
    resp.read.return_value = json.dumps(vec).encode('utf-8')
    resp.__enter__ = lambda s: s
    resp.__exit__ = MagicMock(return_value=False)
    return resp


# ---------------------------------------------------------------------------
# TestEmbedVisualDescription
# ---------------------------------------------------------------------------

class TestEmbedVisualDescription:
    """Unit tests for services.embed_visual_description()."""

    def test_returns_none_when_hf_token_missing(self, monkeypatch):
        """Missing HF_TOKEN => returns None and emits failure event."""
        monkeypatch.setattr(settings, 'HF_TOKEN', '')
        with patch('apps.recommendation.services.event_log') as mock_log:
            result = services.embed_visual_description('a vivid building description')
        assert result is None
        mock_log.emit_event.assert_called_once()
        call_kwargs = mock_log.emit_event.call_args
        assert call_kwargs[0][0] == 'failure'
        assert call_kwargs[1].get('failure_type') == 'hyde'
        assert call_kwargs[1].get('reason') == 'missing_token'

    def test_returns_none_on_empty_text(self, monkeypatch):
        """Empty text => returns None silently (no event emitted; spec says no event for empty input)."""
        monkeypatch.setattr(settings, 'HF_TOKEN', 'hf_test_token')
        with patch('apps.recommendation.services.event_log') as mock_log:
            result = services.embed_visual_description('   ')
        assert result is None
        mock_log.emit_event.assert_not_called()

    def test_returns_vector_on_success_flat(self, monkeypatch):
        """HF returns flat [float*384] => returns list of 384 floats."""
        monkeypatch.setattr(settings, 'HF_TOKEN', 'hf_test_token')
        mock_resp = _make_hf_response(_FAKE_VEC, status_code=200)
        with patch(_HF_URL, return_value=mock_resp):
            with patch('apps.recommendation.services.event_log') as mock_log:
                result = services.embed_visual_description('bright concrete pavilion')
        assert isinstance(result, list)
        assert len(result) == 384
        assert all(isinstance(v, float) for v in result)
        # Timing event should be emitted on success
        mock_log.emit_event.assert_called_once()
        assert mock_log.emit_event.call_args[0][0] == 'hyde_call_timing'

    def test_returns_vector_on_success_batched(self, monkeypatch):
        """HF returns batched [[float*384]] => extracts first row."""
        monkeypatch.setattr(settings, 'HF_TOKEN', 'hf_test_token')
        batched_vec = [_FAKE_VEC]  # 2-D shape
        mock_resp = _make_hf_response(batched_vec, status_code=200)
        with patch(_HF_URL, return_value=mock_resp):
            result = services.embed_visual_description('steel and glass facade')
        assert isinstance(result, list)
        assert len(result) == 384

    def test_returns_none_on_http_503(self, monkeypatch):
        """HF raises HTTPError 503 => returns None, emits failure with http_status=503."""
        monkeypatch.setattr(settings, 'HF_TOKEN', 'hf_test_token')
        http_error = urllib.error.HTTPError(
            url='https://example.com', code=503, msg='Service Unavailable',
            hdrs=None, fp=io.BytesIO(b'service unavailable'),
        )
        with patch(_HF_URL, side_effect=http_error):
            with patch('apps.recommendation.services.event_log') as mock_log:
                result = services.embed_visual_description('timber house')
        assert result is None
        mock_log.emit_event.assert_called_once()
        call_kwargs = mock_log.emit_event.call_args
        assert call_kwargs[0][0] == 'failure'
        assert call_kwargs[1].get('http_status') == 503
        assert call_kwargs[1].get('recovery_path') == 'no_v_initial'

    def test_returns_none_on_http_401(self, monkeypatch):
        """HF raises HTTPError 401 => returns None, emits failure with http_status=401."""
        monkeypatch.setattr(settings, 'HF_TOKEN', 'hf_wrong_token')
        http_error = urllib.error.HTTPError(
            url='https://example.com', code=401, msg='Unauthorized',
            hdrs=None, fp=io.BytesIO(b'{"error":"Authorization error"}'),
        )
        with patch(_HF_URL, side_effect=http_error):
            with patch('apps.recommendation.services.event_log') as mock_log:
                result = services.embed_visual_description('pavilion with glass walls')
        assert result is None
        mock_log.emit_event.assert_called_once()
        call_kwargs = mock_log.emit_event.call_args
        assert call_kwargs[0][0] == 'failure'
        assert call_kwargs[1].get('http_status') == 401
        assert call_kwargs[1].get('recovery_path') == 'no_v_initial'

    def test_returns_none_on_wrong_dim(self, monkeypatch):
        """HF returns 128-dim vector => returns None."""
        monkeypatch.setattr(settings, 'HF_TOKEN', 'hf_test_token')
        mock_resp = _make_hf_response([0.1] * 128, status_code=200)
        with patch(_HF_URL, return_value=mock_resp):
            with patch('apps.recommendation.services.event_log') as mock_log:
                result = services.embed_visual_description('tall brick tower')
        assert result is None
        call_kwargs = mock_log.emit_event.call_args
        assert call_kwargs[0][0] == 'failure'
        assert 'wrong_dim' in call_kwargs[1].get('reason', '')

    def test_returns_none_on_network_exception(self, monkeypatch):
        """urllib.request.urlopen raises => returns None, emits failure."""
        monkeypatch.setattr(settings, 'HF_TOKEN', 'hf_test_token')
        with patch(_HF_URL, side_effect=OSError('connection refused')):
            with patch('apps.recommendation.services.event_log') as mock_log:
                result = services.embed_visual_description('brutalist mass')
        assert result is None
        call_kwargs = mock_log.emit_event.call_args
        assert call_kwargs[0][0] == 'failure'
        assert call_kwargs[1].get('failure_type') == 'hyde'

    def test_never_raises(self, monkeypatch):
        """embed_visual_description must never raise regardless of HF failure."""
        monkeypatch.setattr(settings, 'HF_TOKEN', 'hf_test_token')
        with patch(_HF_URL, side_effect=RuntimeError('catastrophic')):
            result = services.embed_visual_description('any text')
        assert result is None


# ---------------------------------------------------------------------------
# TestHydeFlagGating
# ---------------------------------------------------------------------------

class TestHydeFlagGating:
    """Flag-gating: hyde_vinitial_enabled=False is the default."""

    def test_flag_off_by_default(self):
        """Flag is False in settings.RECOMMENDATION."""
        assert settings.RECOMMENDATION.get('hyde_vinitial_enabled', False) is False

    def test_create_bounded_pool_ignores_v_initial_when_flag_off(self, monkeypatch):
        """With flag OFF, v_initial is ignored even if provided."""
        monkeypatch.setitem(settings.RECOMMENDATION, 'hyde_vinitial_enabled', False)

        # create_bounded_pool with empty filters + v_initial when flag off => random pool path
        with patch('apps.recommendation.engine._random_pool', return_value=['B00001']) as mock_rand:
            pool_ids, pool_scores = create_bounded_pool(
                {}, None, None, target=10, v_initial=_FAKE_VEC,
            )
        mock_rand.assert_called_once_with(10)
        assert pool_ids == ['B00001']
        assert pool_scores == {}

    def test_create_pool_with_relaxation_passes_none_v_initial_by_default(self, monkeypatch):
        """create_pool_with_relaxation still works with no v_initial kwarg (backward compat)."""
        monkeypatch.setitem(settings.RECOMMENDATION, 'hyde_vinitial_enabled', False)
        with patch('apps.recommendation.engine.create_bounded_pool',
                   return_value=(['B00001'], {'B00001': 0.9})) as mock_pool:
            pool_ids, pool_scores, tier = create_pool_with_relaxation(
                {'program': 'Museum'}, ['program'], [], target=10,
            )
        # v_initial=None must be passed through (keyword arg, not positional)
        call_kwargs = mock_pool.call_args[1]
        assert call_kwargs.get('v_initial') is None

    @pytest.mark.django_db
    def test_flag_off_with_visual_description_in_request_skips_hf(
        self, auth_client, monkeypatch
    ):
        """Flag OFF: visual_description in POST body must NOT trigger embed_visual_description call."""
        monkeypatch.setitem(settings.RECOMMENDATION, 'hyde_vinitial_enabled', False)

        import numpy as np
        fake_pool = [f'B{str(i).zfill(5)}' for i in range(1, 11)]
        fake_scores = {bid: 10 - i for i, bid in enumerate(fake_pool)}
        fake_embeddings = {bid: np.random.RandomState(i).randn(384) for i, bid in enumerate(fake_pool)}
        for bid in fake_embeddings:
            v = fake_embeddings[bid]
            fake_embeddings[bid] = v / np.linalg.norm(v)

        def _mock_farthest(pool_ids, exposed_ids, pool_embs):
            s = set(exposed_ids)
            for bid in pool_ids:
                if bid not in s:
                    return bid
            return None

        _V = 'apps.recommendation.views.engine'
        with patch(_EMBED_FN) as mock_embed, \
             patch(f'{_V}.create_pool_with_relaxation',
                   return_value=(fake_pool, fake_scores, 1)), \
             patch(f'{_V}.get_pool_embeddings',
                   return_value=fake_embeddings), \
             patch(f'{_V}.farthest_point_from_pool',
                   side_effect=_mock_farthest), \
             patch(f'{_V}.get_building_card',
                   side_effect=lambda bid: {'building_id': bid, 'name_en': bid,
                                            'project_name': '', 'image_url': '',
                                            'url': None, 'gallery': [],
                                            'gallery_drawing_start': 0, 'metadata': {}}):
            resp = auth_client.post(
                '/api/v1/analysis/sessions/',
                {'visual_description': 'a glass pavilion in the forest'},
                format='json',
            )

        assert resp.status_code == 201
        mock_embed.assert_not_called()


# ---------------------------------------------------------------------------
# TestHydeFlagOnSuccess
# ---------------------------------------------------------------------------

class TestHydeFlagOnSuccess:
    """Flag ON: v_initial drives SQL reranking in create_bounded_pool."""

    def test_hyde_only_path_builds_cosine_sql(self, monkeypatch):
        """empty filters + flag on + v_initial => cosine-similarity-only SQL path."""
        monkeypatch.setitem(settings.RECOMMENDATION, 'hyde_vinitial_enabled', True)

        fake_rows = [('B00001', 0.95), ('B00002', 0.80)]
        mock_cursor = MagicMock()
        mock_cursor.__enter__ = lambda s: s
        mock_cursor.__exit__ = MagicMock(return_value=False)
        mock_cursor.fetchall.return_value = fake_rows

        with patch('apps.recommendation.engine.connection') as mock_conn:
            mock_conn.cursor.return_value = mock_cursor
            pool_ids, pool_scores = create_bounded_pool(
                {}, None, None, target=10, v_initial=_FAKE_VEC,
            )

        assert pool_ids == ['B00001', 'B00002']
        assert pool_scores['B00001'] == pytest.approx(0.95)
        assert pool_scores['B00002'] == pytest.approx(0.80)
        # Confirm cosine SQL was used (not _random_pool)
        executed_sql = mock_cursor.execute.call_args[0][0]
        assert 'embedding <=> %s::vector' in executed_sql

    def test_filter_plus_hyde_blend_sql(self, monkeypatch):
        """Non-empty filters + flag on + v_initial => blended score SQL."""
        monkeypatch.setitem(settings.RECOMMENDATION, 'hyde_vinitial_enabled', True)

        fake_rows = [('B00001', 0.88)]
        mock_cursor = MagicMock()
        mock_cursor.__enter__ = lambda s: s
        mock_cursor.__exit__ = MagicMock(return_value=False)
        mock_cursor.fetchall.return_value = fake_rows

        with patch('apps.recommendation.engine.connection') as mock_conn:
            mock_conn.cursor.return_value = mock_cursor
            pool_ids, pool_scores = create_bounded_pool(
                {'program': 'Museum'}, ['program'], None, target=10, v_initial=_FAKE_VEC,
            )

        assert pool_ids == ['B00001']
        executed_sql = mock_cursor.execute.call_args[0][0]
        # Both filter case and cosine term should appear
        assert 'program = %s' in executed_sql
        assert 'embedding <=> %s::vector' in executed_sql

    def test_seed_ids_override_still_applied(self, monkeypatch):
        """Seed IDs get score 1.1 override even in HyDE path."""
        monkeypatch.setitem(settings.RECOMMENDATION, 'hyde_vinitial_enabled', True)

        fake_rows = [('B00002', 0.80)]
        mock_cursor = MagicMock()
        mock_cursor.__enter__ = lambda s: s
        mock_cursor.__exit__ = MagicMock(return_value=False)
        mock_cursor.fetchall.return_value = fake_rows

        with patch('apps.recommendation.engine.connection') as mock_conn:
            mock_conn.cursor.return_value = mock_cursor
            pool_ids, pool_scores = create_bounded_pool(
                {}, None, ['B00001'], target=10, v_initial=_FAKE_VEC,
            )

        assert 'B00001' in pool_scores
        assert pool_scores['B00001'] == pytest.approx(1.1)


# ---------------------------------------------------------------------------
# TestHydeFlagOnFailure
# ---------------------------------------------------------------------------

class TestHydeFlagOnFailure:
    """Graceful degradation: HF failure => session still created with v_initial=None."""

    @pytest.mark.django_db
    def test_session_created_when_embed_returns_none(self, auth_client, monkeypatch):
        """embed_visual_description returns None => session created, v_initial=None stored."""
        monkeypatch.setitem(settings.RECOMMENDATION, 'hyde_vinitial_enabled', True)

        from apps.recommendation.models import AnalysisSession
        import numpy as np

        fake_pool = [f'B{str(i).zfill(5)}' for i in range(1, 11)]
        fake_scores = {bid: 10 - i for i, bid in enumerate(fake_pool)}
        fake_embeddings = {bid: np.random.RandomState(i).randn(384) for i, bid in enumerate(fake_pool)}
        for bid in fake_embeddings:
            v = fake_embeddings[bid]
            fake_embeddings[bid] = v / np.linalg.norm(v)

        def _mock_farthest(pool_ids, exposed_ids, pool_embs):
            s = set(exposed_ids)
            for bid in pool_ids:
                if bid not in s:
                    return bid
            return None

        _V = 'apps.recommendation.views.engine'
        with patch(_EMBED_FN, return_value=None), \
             patch(f'{_V}.create_pool_with_relaxation',
                   return_value=(fake_pool, fake_scores, 1)), \
             patch(f'{_V}.get_pool_embeddings',
                   return_value=fake_embeddings), \
             patch(f'{_V}.farthest_point_from_pool',
                   side_effect=_mock_farthest), \
             patch(f'{_V}.get_building_card',
                   side_effect=lambda bid: {'building_id': bid, 'name_en': bid,
                                            'project_name': '', 'image_url': '',
                                            'url': None, 'gallery': [],
                                            'gallery_drawing_start': 0, 'metadata': {}}):
            resp = auth_client.post(
                '/api/v1/analysis/sessions/',
                {'visual_description': 'a beautiful brutalist chapel'},
                format='json',
            )

        assert resp.status_code == 201
        session_id = resp.data['session_id']
        session = AnalysisSession.objects.get(session_id=session_id)
        assert session.v_initial is None


# ---------------------------------------------------------------------------
# TestRefreshPoolIfLowPreservesVInitial
# ---------------------------------------------------------------------------

class TestRefreshPoolIfLowPreservesVInitial:
    """refresh_pool_if_low passes session.v_initial through to create_pool_with_relaxation."""

    @pytest.mark.django_db
    def test_v_initial_forwarded_on_escalation(self, user_profile, monkeypatch):
        """When pool is low, refresh_pool_if_low passes v_initial from session."""
        from apps.recommendation.models import AnalysisSession, Project
        from apps.recommendation.engine import refresh_pool_if_low

        project = Project.objects.create(user=user_profile, name='Test')
        pool = [f'B{str(i).zfill(5)}' for i in range(1, 6)]
        session = AnalysisSession.objects.create(
            user=user_profile,
            project=project,
            phase='exploring',
            pool_ids=pool,
            pool_scores={},
            current_round=0,
            preference_vector=[],
            exposed_ids=pool,  # all exposed => remaining=0 => escalation fires
            initial_batch=pool[:1],
            like_vectors=[],
            convergence_history=[],
            previous_pref_vector=[],
            original_filters={'program': 'Museum'},
            original_filter_priority=['program'],
            original_seed_ids=[],
            current_pool_tier=1,
            v_initial=_FAKE_VEC,
        )

        new_pool = ['B00010', 'B00011']
        captured_kwargs = {}

        def _mock_relaxation(*args, **kwargs):
            captured_kwargs.update(kwargs)
            return new_pool, {}, 2

        with patch('apps.recommendation.engine.create_pool_with_relaxation',
                   side_effect=_mock_relaxation):
            refresh_pool_if_low(session, threshold=5)

        assert 'v_initial' in captured_kwargs
        assert captured_kwargs['v_initial'] == _FAKE_VEC


# ---------------------------------------------------------------------------
# TestPgvectorShapeError
# ---------------------------------------------------------------------------

class TestPgvectorShapeError:
    """Malformed v_initial (wrong dim) is silently ignored."""

    def test_wrong_dim_v_initial_ignored_by_create_bounded_pool(self, monkeypatch):
        """v_initial with len != 384 is treated as no-HyDE (flag off path)."""
        monkeypatch.setitem(settings.RECOMMENDATION, 'hyde_vinitial_enabled', True)

        with patch('apps.recommendation.engine._random_pool', return_value=['B00001']) as mock_rand:
            pool_ids, pool_scores = create_bounded_pool(
                {}, None, None, target=10, v_initial=[0.1] * 100,  # wrong dim
            )

        mock_rand.assert_called_once_with(10)
        assert pool_ids == ['B00001']


# ---------------------------------------------------------------------------
# TestHydePgvectorQueryFailure (Fix 5)
# ---------------------------------------------------------------------------

class TestHydePgvectorQueryFailure:
    """pgvector SQL failure in create_bounded_pool => graceful degradation to non-HyDE path."""

    def test_hyde_query_failure_falls_back_to_filter_path(self, monkeypatch):
        """When HyDE SQL raises, event is emitted and filter-only SQL is executed instead."""
        monkeypatch.setitem(settings.RECOMMENDATION, 'hyde_vinitial_enabled', True)

        fallback_rows = [('B00099', 0.75)]
        call_count = [0]

        mock_cursor = MagicMock()
        mock_cursor.__enter__ = lambda s: s
        mock_cursor.__exit__ = MagicMock(return_value=False)

        def _execute_side_effect(sql, params):
            call_count[0] += 1
            if call_count[0] == 1:
                # First call is the HyDE blend query — raise to simulate pgvector error
                raise Exception('pgvector: wrong number of dimensions: 384 != 256')
            # Second call is the fallback filter-only query — succeeds
            mock_cursor.fetchall.return_value = fallback_rows

        mock_cursor.execute.side_effect = _execute_side_effect

        with patch('apps.recommendation.engine.connection') as mock_conn, \
             patch('apps.recommendation.engine.event_log') as mock_event_log:
            mock_conn.cursor.return_value = mock_cursor
            pool_ids, pool_scores = create_bounded_pool(
                {'program': 'Museum'}, ['program'], None, target=10, v_initial=_FAKE_VEC,
            )

        # Fallback path should have yielded results
        assert pool_ids == ['B00099']
        assert pool_scores['B00099'] == pytest.approx(0.75)
        # Failure event must be emitted
        mock_event_log.emit_event.assert_called_once()
        call_kwargs = mock_event_log.emit_event.call_args
        assert call_kwargs[0][0] == 'failure'
        assert call_kwargs[1].get('failure_type') == 'hyde_pool_query'
        assert call_kwargs[1].get('recovery_path') == 'no_v_initial'


# ---------------------------------------------------------------------------
# TestVisualDescriptionInputValidation (Fix 7)
# ---------------------------------------------------------------------------

class TestVisualDescriptionInputValidation:
    """SessionCreateView silently coerces invalid visual_description to None."""

    @pytest.mark.django_db
    def test_oversized_visual_description_is_coerced_to_none(self, auth_client, monkeypatch):
        """visual_description longer than 5000 chars => coerced to None, HF not called."""
        monkeypatch.setitem(settings.RECOMMENDATION, 'hyde_vinitial_enabled', True)

        import numpy as np
        fake_pool = [f'B{str(i).zfill(5)}' for i in range(1, 11)]
        fake_scores = {bid: 10 - i for i, bid in enumerate(fake_pool)}
        fake_embeddings = {bid: np.random.RandomState(i).randn(384) for i, bid in enumerate(fake_pool)}
        for bid in fake_embeddings:
            v = fake_embeddings[bid]
            fake_embeddings[bid] = v / np.linalg.norm(v)

        def _mock_farthest(pool_ids, exposed_ids, pool_embs):
            s = set(exposed_ids)
            for bid in pool_ids:
                if bid not in s:
                    return bid
            return None

        _V = 'apps.recommendation.views.engine'
        with patch(_EMBED_FN) as mock_embed, \
             patch(f'{_V}.create_pool_with_relaxation',
                   return_value=(fake_pool, fake_scores, 1)), \
             patch(f'{_V}.get_pool_embeddings',
                   return_value=fake_embeddings), \
             patch(f'{_V}.farthest_point_from_pool',
                   side_effect=_mock_farthest), \
             patch(f'{_V}.get_building_card',
                   side_effect=lambda bid: {'building_id': bid, 'name_en': bid,
                                            'project_name': '', 'image_url': '',
                                            'url': None, 'gallery': [],
                                            'gallery_drawing_start': 0, 'metadata': {}}):
            resp = auth_client.post(
                '/api/v1/analysis/sessions/',
                {'visual_description': 'x' * 5001},
                format='json',
            )

        assert resp.status_code == 201
        mock_embed.assert_not_called()

    @pytest.mark.django_db
    def test_non_string_visual_description_is_coerced_to_none(self, auth_client, monkeypatch):
        """visual_description that is not a string => coerced to None, HF not called."""
        monkeypatch.setitem(settings.RECOMMENDATION, 'hyde_vinitial_enabled', True)

        import numpy as np
        fake_pool = [f'B{str(i).zfill(5)}' for i in range(1, 11)]
        fake_scores = {bid: 10 - i for i, bid in enumerate(fake_pool)}
        fake_embeddings = {bid: np.random.RandomState(i).randn(384) for i, bid in enumerate(fake_pool)}
        for bid in fake_embeddings:
            v = fake_embeddings[bid]
            fake_embeddings[bid] = v / np.linalg.norm(v)

        def _mock_farthest(pool_ids, exposed_ids, pool_embs):
            s = set(exposed_ids)
            for bid in pool_ids:
                if bid not in s:
                    return bid
            return None

        _V = 'apps.recommendation.views.engine'
        with patch(_EMBED_FN) as mock_embed, \
             patch(f'{_V}.create_pool_with_relaxation',
                   return_value=(fake_pool, fake_scores, 1)), \
             patch(f'{_V}.get_pool_embeddings',
                   return_value=fake_embeddings), \
             patch(f'{_V}.farthest_point_from_pool',
                   side_effect=_mock_farthest), \
             patch(f'{_V}.get_building_card',
                   side_effect=lambda bid: {'building_id': bid, 'name_en': bid,
                                            'project_name': '', 'image_url': '',
                                            'url': None, 'gallery': [],
                                            'gallery_drawing_start': 0, 'metadata': {}}):
            resp = auth_client.post(
                '/api/v1/analysis/sessions/',
                {'visual_description': 12345},
                format='json',
            )

        assert resp.status_code == 201
        mock_embed.assert_not_called()
