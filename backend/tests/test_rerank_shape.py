"""
test_rerank_shape.py -- #9 rerank metadata shape alignment regression test.

Verifies that the producer shape in sessions.py (metadata.axis_* wrapper) is
consumed correctly by rerank_candidates, i.e., no axis value reads as None.
"""
import json
from unittest.mock import MagicMock


def _make_card(bid, architect='TestArch', style='Brutalist',
               typology='Museum', material_visual=None, atmosphere='austere'):
    """Return a card in engine._row_to_card shape (metadata.axis_* keys)."""
    return {
        'canonical_bld_id': bid,
        'name': f'Building {bid}',
        'metadata': {
            'axis_architects': architect,
            'axis_style': style,
            'axis_typology': typology,
            'axis_material_visual': material_visual if material_visual is not None else ['concrete'],
            'axis_atmosphere': atmosphere,
        },
    }


def _mock_response(text):
    resp = MagicMock()
    resp.text = text
    return resp


class TestRerankMetadataShape:
    """Verify that rerank_candidates reads non-None axis values from the correct shape."""

    def test_valid_shape_returns_ranking(self, monkeypatch):
        """
        When candidates use metadata.axis_* shape, rerank_candidates returns the
        Gemini ranking without falling back to input order.
        """
        from apps.recommendation import services

        candidates = [_make_card('B00001'), _make_card('B00002')]
        ids = ['B00001', 'B00002']
        reversed_ids = list(reversed(ids))
        valid_response = json.dumps({'ranking': reversed_ids})

        monkeypatch.setattr(
            services, '_retry_gemini_call',
            lambda func, *a, **kw: _mock_response(valid_response),
        )

        result = services.rerank_candidates(candidates, 'liked summary')
        assert result == reversed_ids

    def test_axis_values_read_correctly(self, monkeypatch):
        """
        Inject candidates and capture what prompt is sent to Gemini.
        The captured prompt must contain injected axis values, not fallbacks
        ('anon' for architect, empty strings for other axes).
        """
        from apps.recommendation import services

        candidates = [
            _make_card('B00001', architect='Tadao Ando', style='Modernist',
                       typology='Museum', material_visual=['concrete', 'stone'],
                       atmosphere='contemplative quiet'),
            _make_card('B00002', architect='Zaha Hadid', style='Parametric',
                       typology='Public', material_visual=['steel', 'glass'],
                       atmosphere='fluid dramatic'),
        ]
        ids = ['B00001', 'B00002']
        valid_response = json.dumps({'ranking': ids})

        fake_client = MagicMock()
        fake_client.models.generate_content.side_effect = (
            lambda *a, **kw: _mock_response(valid_response)
        )
        monkeypatch.setattr(services, '_get_client', lambda: fake_client)

        # _retry_gemini_call must forward args so the client mock gets exercised
        # with the real contents/config (mirrors the real wrapper, which calls
        # func(*args, **kwargs) -- a bare func() drops the contents kwarg).
        monkeypatch.setattr(services, '_retry_gemini_call', lambda func, *a, **kw: func(*a, **kw))

        services.rerank_candidates(candidates, 'some liked summary')

        assert fake_client.models.generate_content.called
        call_kwargs = fake_client.models.generate_content.call_args
        # contents is passed as a keyword argument
        contents_arg = call_kwargs[1].get('contents') or (
            call_kwargs[0][0] if call_kwargs[0] else None
        )
        assert contents_arg is not None
        prompt_text = str(contents_arg)

        assert 'Tadao Ando' in prompt_text, (
            'axis_architects not read: got fallback "anon" instead of "Tadao Ando"'
        )
        assert 'Zaha Hadid' in prompt_text, (
            'axis_architects not read: got fallback "anon" instead of "Zaha Hadid"'
        )
        assert 'Modernist' in prompt_text
        assert 'Parametric' in prompt_text
        assert 'contemplative quiet' in prompt_text
        assert 'fluid dramatic' in prompt_text

    def test_no_keyerror_on_valid_shape(self, monkeypatch):
        """rerank_candidates must not raise KeyError for the correct card shape."""
        from apps.recommendation import services

        candidates = [_make_card(f'B{i:05d}') for i in range(5)]
        ids = [c['canonical_bld_id'] for c in candidates]
        valid_response = json.dumps({'ranking': ids})

        monkeypatch.setattr(
            services, '_retry_gemini_call',
            lambda func, *a, **kw: _mock_response(valid_response),
        )

        result = services.rerank_candidates(candidates, 'liked summary')
        assert result == ids

    def test_graceful_on_missing_metadata(self, monkeypatch):
        """
        If a card arrives with no metadata key (defensive edge case),
        rerank_candidates must not raise and must fall back to empty strings.
        """
        from apps.recommendation import services

        candidates = [
            {'canonical_bld_id': 'B00001', 'name': 'Building 1'},
            {'canonical_bld_id': 'B00002', 'name': 'Building 2'},
        ]
        ids = ['B00001', 'B00002']
        valid_response = json.dumps({'ranking': ids})

        monkeypatch.setattr(
            services, '_retry_gemini_call',
            lambda func, *a, **kw: _mock_response(valid_response),
        )

        result = services.rerank_candidates(candidates, 'liked summary')
        assert result == ids
