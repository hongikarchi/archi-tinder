"""
test_topic02.py -- Sprint 4 Topic 02: Gemini setwise rerank per Investigation 12.

Tests cover:
- rerank_candidates callable check
- Valid JSON response -> reordered list returned
- Invalid JSON -> fallback to input order + logger.warning
- Missing ids in ranking -> fallback
- Extra (hallucinated) ids -> fallback
- Exception from Gemini call -> fallback, no propagation
- Failure event emitted on validation failure
- _liked_summary_for_rerank line format with [Like]/[Love] intensity tags
- SessionResultView with flag ON -> predicted_cards reordered per rerank
- SessionResultView with flag OFF (default) -> no rerank call
"""
import json
import pytest
from unittest.mock import MagicMock, patch


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_candidates(ids):
    """Build minimal candidate dicts for rerank_candidates."""
    return [
        {
            'building_id': bid,
            'name_en': f'Building {bid}',
            'atmosphere': 'calm serene',
            'material': 'concrete',
            'architect': 'Anon',
            'style': 'Contemporary',
            'program': 'Museum',
        }
        for bid in ids
    ]


def _mock_gemini_response(text):
    """Return a mock Gemini response object with .text attribute."""
    resp = MagicMock()
    resp.text = text
    return resp


# ---------------------------------------------------------------------------
# TestRerankCandidates
# ---------------------------------------------------------------------------

class TestRerankCandidates:
    """Sprint 4 Topic 02: Gemini setwise rerank per Investigation 12."""

    def test_rerank_returns_input_on_disabled_flag(self):
        """Caller (views.py) gates on flag; rerank_candidates itself doesn't gate."""
        from apps.recommendation import services
        assert callable(services.rerank_candidates)

    def test_rerank_validates_json_response(self, monkeypatch):
        """Valid JSON ranking from Gemini -> returns reordered list."""
        from apps.recommendation import services

        ids = ['B00001', 'B00002', 'B00003']
        reversed_order = list(reversed(ids))
        valid_response = json.dumps({'ranking': reversed_order})

        monkeypatch.setattr(
            services, '_retry_gemini_call',
            lambda func, *a, **kw: _mock_gemini_response(valid_response),
        )

        result = services.rerank_candidates(_make_candidates(ids), 'liked summary text')
        assert result == reversed_order

    def test_rerank_falls_back_on_invalid_json(self, monkeypatch):
        """Gemini returns malformed JSON -> logger.warning + return input order."""
        from apps.recommendation import services

        ids = ['B00001', 'B00002', 'B00003']
        monkeypatch.setattr(
            services, '_retry_gemini_call',
            lambda func, *a, **kw: _mock_gemini_response('this is not JSON {{{'),
        )

        import logging
        with patch.object(logging.getLogger('apps.recommendation'), 'warning') as mock_warn:
            result = services.rerank_candidates(_make_candidates(ids), 'liked summary')

        assert result == ids
        assert mock_warn.called

    def test_rerank_falls_back_on_missing_ids(self, monkeypatch):
        """Gemini ranking missing some input ids -> fall back to input order."""
        from apps.recommendation import services

        ids = ['B00001', 'B00002', 'B00003']
        # ranking is missing B00003
        partial_response = json.dumps({'ranking': ['B00001', 'B00002']})
        monkeypatch.setattr(
            services, '_retry_gemini_call',
            lambda func, *a, **kw: _mock_gemini_response(partial_response),
        )

        result = services.rerank_candidates(_make_candidates(ids), 'liked summary')
        assert result == ids

    def test_rerank_falls_back_on_extra_ids(self, monkeypatch):
        """Gemini ranking has hallucinated ids -> fall back."""
        from apps.recommendation import services

        ids = ['B00001', 'B00002']
        # ranking includes hallucinated B99999
        extra_response = json.dumps({'ranking': ['B00001', 'B00002', 'B99999']})
        monkeypatch.setattr(
            services, '_retry_gemini_call',
            lambda func, *a, **kw: _mock_gemini_response(extra_response),
        )

        result = services.rerank_candidates(_make_candidates(ids), 'liked summary')
        assert result == ids

    def test_rerank_falls_back_on_duplicates(self, monkeypatch):
        """Gemini ranking has duplicates -> set check fails -> fall back."""
        from apps.recommendation import services

        ids = ['B00001', 'B00002', 'B00003']
        # B00001 appears twice, B00003 missing
        dup_response = json.dumps({'ranking': ['B00001', 'B00001', 'B00002']})
        monkeypatch.setattr(
            services, '_retry_gemini_call',
            lambda func, *a, **kw: _mock_gemini_response(dup_response),
        )

        result = services.rerank_candidates(_make_candidates(ids), 'liked summary')
        assert result == ids

    def test_rerank_falls_back_on_exception(self, monkeypatch):
        """Gemini call raises -> fall back, no exception propagates."""
        from apps.recommendation import services

        ids = ['B00001', 'B00002']

        def _raise(*a, **kw):
            raise RuntimeError('network error')

        monkeypatch.setattr(services, '_retry_gemini_call', _raise)

        result = services.rerank_candidates(_make_candidates(ids), 'liked summary')
        assert result == ids

    def test_rerank_emits_failure_event_on_parse_fail(self, monkeypatch):
        """Validation failure emits event via event_log.emit_event."""
        from apps.recommendation import services

        ids = ['B00001', 'B00002']
        monkeypatch.setattr(
            services, '_retry_gemini_call',
            lambda func, *a, **kw: _mock_gemini_response('not valid json'),
        )

        emitted = []

        def _fake_emit(event_type, session=None, user=None, **payload):
            emitted.append({'event_type': event_type, 'payload': payload})

        monkeypatch.setattr(services.event_log, 'emit_event', _fake_emit)

        services.rerank_candidates(_make_candidates(ids), 'liked summary')

        assert len(emitted) == 1
        assert emitted[0]['event_type'] == 'failure'
        assert emitted[0]['payload'].get('failure_type') == 'gemini_rerank'
        assert emitted[0]['payload'].get('rerank_status') == 'parse_fail'

    def test_rerank_emits_failure_event_on_id_mismatch(self, monkeypatch):
        """id_mismatch -> failure event with rerank_status='id_mismatch'."""
        from apps.recommendation import services

        ids = ['B00001', 'B00002', 'B00003']
        mismatch_response = json.dumps({'ranking': ['B00001', 'B00002']})
        monkeypatch.setattr(
            services, '_retry_gemini_call',
            lambda func, *a, **kw: _mock_gemini_response(mismatch_response),
        )

        emitted = []

        def _fake_emit(event_type, session=None, user=None, **payload):
            emitted.append({'event_type': event_type, 'payload': payload})

        monkeypatch.setattr(services.event_log, 'emit_event', _fake_emit)

        services.rerank_candidates(_make_candidates(ids), 'liked summary')

        assert any(e['payload'].get('rerank_status') in ('id_mismatch', 'duplicates')
                   for e in emitted)

    def test_rerank_truncates_to_60(self, monkeypatch):
        """More than 60 candidates -> truncated to 60 before Gemini call."""
        from apps.recommendation import services

        ids = [f'B{i:05d}' for i in range(80)]
        candidates = _make_candidates(ids)

        captured = []

        def _fake_call(func, *a, **kw):
            # Call the function to capture what user prompt was built
            # We intercept by examining the candidates slice
            captured.append(True)
            # Return valid response for first 60 ids
            first_60 = ids[:60]
            return _mock_gemini_response(json.dumps({'ranking': first_60}))

        monkeypatch.setattr(services, '_retry_gemini_call', _fake_call)

        result = services.rerank_candidates(candidates, 'liked summary')
        # Result should be the first 60 (truncated input order matches valid ranking)
        assert len(result) == 60
        assert result == ids[:60]

    def test_rerank_empty_candidates(self):
        """Empty candidates list -> empty list returned immediately."""
        from apps.recommendation import services
        result = services.rerank_candidates([], 'liked summary')
        assert result == []

    def test_liked_summary_helper_format(self, monkeypatch):
        """_liked_summary_for_rerank produces expected line format with intensity tags."""
        from apps.recommendation import services

        liked_ids = [
            {'id': 'B00001', 'intensity': 1.0},   # should be [Like]
            {'id': 'B00002', 'intensity': 1.8},   # should be [Love]
            'B00003',                               # legacy str, intensity 1.0 -> [Like]
        ]

        # Mock the SQL fetch to return canned metadata
        fake_rows = [
            {'building_id': 'B00001', 'name_en': 'House A', 'style': 'Modernist',
             'atmosphere': 'calm', 'material': 'concrete'},
            {'building_id': 'B00002', 'name_en': 'Museum B', 'style': 'Brutalist',
             'atmosphere': 'dramatic', 'material': 'stone'},
            {'building_id': 'B00003', 'name_en': 'Chapel C', 'style': 'Vernacular',
             'atmosphere': 'quiet', 'material': 'timber'},
        ]

        with patch('apps.recommendation.services.connection') as mock_conn:
            mock_cursor = MagicMock()
            mock_cursor.__enter__ = MagicMock(return_value=mock_cursor)
            mock_cursor.__exit__ = MagicMock(return_value=False)
            mock_cursor.fetchall.return_value = [
                (r['building_id'], r['name_en'], r['style'], r['atmosphere'], r['material'])
                for r in fake_rows
            ]
            mock_cursor.description = [
                ('building_id',), ('name_en',), ('style',), ('atmosphere',), ('material',)
            ]
            mock_conn.cursor.return_value = mock_cursor

            summary = services._liked_summary_for_rerank(liked_ids)

        # Verify format: name_en (style, atmosphere, material) [tag]
        assert 'House A' in summary
        assert '[Like]' in summary
        assert '[Love]' in summary
        assert 'Museum B' in summary

        lines = summary.strip().split('\n')
        assert len(lines) == 3

        # Find line for B00002 (intensity 1.8) -> must have [Love]
        b2_line = next(line for line in lines if 'Museum B' in line)
        assert '[Love]' in b2_line

        # Find line for B00001 (intensity 1.0) -> must have [Like]
        b1_line = next(line for line in lines if 'House A' in line)
        assert '[Like]' in b1_line

    def test_liked_summary_legacy_str_shape(self):
        """Legacy liked_ids as plain strings default to intensity=1.0 -> [Like]."""
        from apps.recommendation import services

        liked_ids = ['B00001', 'B00002']

        with patch('apps.recommendation.services.connection') as mock_conn:
            mock_cursor = MagicMock()
            mock_cursor.__enter__ = MagicMock(return_value=mock_cursor)
            mock_cursor.__exit__ = MagicMock(return_value=False)
            mock_cursor.fetchall.return_value = []
            mock_cursor.description = [
                ('building_id',), ('name_en',), ('style',), ('atmosphere',), ('material',)
            ]
            mock_conn.cursor.return_value = mock_cursor

            summary = services._liked_summary_for_rerank(liked_ids)

        # Fallback to building_id when no metadata
        assert 'B00001' in summary
        assert '[Like]' in summary
        assert '[Love]' not in summary

    def test_liked_summary_empty_input(self):
        """Empty liked_ids -> empty string returned."""
        from apps.recommendation import services
        result = services._liked_summary_for_rerank([])
        assert result == ''


# ---------------------------------------------------------------------------
# TestSessionResultViewRerank -- DB-level integration
# ---------------------------------------------------------------------------

class TestSessionResultViewRerank:
    """SessionResultView integration: flag controls rerank invocation."""

    @pytest.mark.django_db
    def test_session_result_skips_rerank_when_disabled(self, auth_client, monkeypatch):
        """SessionResultView with flag off (default) -> no rerank call."""
        from django.conf import settings
        # Ensure flag is off
        monkeypatch.setitem(settings.RECOMMENDATION, 'gemini_rerank_enabled', False)

        from apps.recommendation import services, engine

        fake_cards = [
            {'building_id': 'B00001', 'name_en': 'Building A', 'atmosphere': 'calm',
             'material': 'concrete', 'architect': 'Anon', 'style': 'Contemporary',
             'program': 'Museum'},
        ]
        # Mock engine calls to avoid raw SQL on architecture_vectors
        monkeypatch.setattr(engine, 'get_top_k_mmr', lambda *a, **kw: list(fake_cards))
        monkeypatch.setattr(engine, 'get_top_k_results', lambda *a, **kw: list(fake_cards))

        mock_rerank = MagicMock(return_value=['B00001'])
        monkeypatch.setattr(services, 'rerank_candidates', mock_rerank)

        # Create minimal session
        from apps.recommendation.models import AnalysisSession, Project
        from apps.accounts.models import UserProfile

        profile = UserProfile.objects.get(user__username='testuser')
        project = Project.objects.create(
            user=profile,
            name='Test Project',
            liked_ids=[],
            disliked_ids=[],
        )
        import uuid
        session = AnalysisSession.objects.create(
            session_id=uuid.uuid4(),
            user=profile,
            project=project,
            status='completed',
            phase='exploring',
            preference_vector=[0.0] * 384,
            like_vectors=[],
            exposed_ids=[],
            current_round=0,
            convergence_history=[],
        )

        resp = auth_client.get(f'/api/v1/analysis/sessions/{session.session_id}/result/')
        assert resp.status_code == 200
        mock_rerank.assert_not_called()

    @pytest.mark.django_db
    def test_session_result_uses_rerank_when_enabled(self, auth_client, monkeypatch):
        """SessionResultView with flag on -> predicted_cards reordered per rerank."""
        from django.conf import settings
        monkeypatch.setitem(settings.RECOMMENDATION, 'gemini_rerank_enabled', True)

        from apps.recommendation import services, engine

        # Fake get_top_k_mmr to return 2 cards with known building_ids
        fake_cards = [
            {'building_id': 'B00001', 'name_en': 'Building A', 'atmosphere': 'calm',
             'material': 'concrete', 'architect': 'Anon', 'style': 'Contemporary',
             'program': 'Museum'},
            {'building_id': 'B00002', 'name_en': 'Building B', 'atmosphere': 'dramatic',
             'material': 'stone', 'architect': 'Anon', 'style': 'Brutalist',
             'program': 'Museum'},
        ]
        monkeypatch.setattr(engine, 'get_top_k_mmr', lambda *a, **kw: list(fake_cards))
        monkeypatch.setattr(engine, 'get_top_k_results', lambda *a, **kw: list(fake_cards))

        # rerank reverses the order
        reversed_ids = ['B00002', 'B00001']
        mock_rerank = MagicMock(return_value=reversed_ids)
        monkeypatch.setattr(services, 'rerank_candidates', mock_rerank)
        monkeypatch.setattr(services, '_liked_summary_for_rerank', lambda x: 'liked summary')

        from apps.recommendation.models import AnalysisSession, Project
        from apps.accounts.models import UserProfile

        profile = UserProfile.objects.get(user__username='testuser')
        project = Project.objects.create(
            user=profile,
            name='Test Project Rerank',
            liked_ids=[{'id': 'B00010', 'intensity': 1.0}],
            disliked_ids=[],
        )
        import uuid
        session = AnalysisSession.objects.create(
            session_id=uuid.uuid4(),
            user=profile,
            project=project,
            status='completed',
            phase='analyzing',
            preference_vector=[0.0] * 384,
            like_vectors=[{'embedding': [0.0] * 384, 'round': 1}],
            exposed_ids=[],
            current_round=1,
            convergence_history=[],
        )

        resp = auth_client.get(f'/api/v1/analysis/sessions/{session.session_id}/result/')
        assert resp.status_code == 200
        mock_rerank.assert_called_once()

        data = resp.json()
        predicted = data.get('predicted_images', [])
        assert len(predicted) == 2
        # Verify reordering: B00002 should come first (reversed by mock_rerank)
        assert predicted[0]['building_id'] == 'B00002'
        assert predicted[1]['building_id'] == 'B00001'
