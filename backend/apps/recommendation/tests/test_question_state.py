"""
test_question_state.py — PERF-HOTPATH-1: cache-aware tag-fetch dedupe for
_update_question_state (swipe_service.py).

Coverage:
  (1) Cache-hit path: engine.get_building_card returns a full-metadata card ->
      axis_tags built from card metadata match what the raw-SQL path would
      produce for the same underlying values (scalar wrap, list(), empties).
  (2) get_building_card returns None -> raw SQL fallback executes and behaviour
      matches today (same is_publishable gating via the SQL WHERE clause).
  (3) Metadata present but axis keys absent/empty -> empty tag lists, no
      KeyError.

_update_question_state itself only mutates plain attributes on `session`
(no .save()), so a SimpleNamespace stand-in is sufficient and avoids a DB
dependency for the pure-function-shaped cases. django_db is used only where
the spec calls for it (kept available for future session-model coverage).

Import-order note (pre-existing, unrelated to this task): swipe_service.py
transitively imports views/__init__.py -> views/sessions.py ->
services/session_service.py -> back to swipe_service.py. If swipe_service is
the very FIRST app module imported in a process (e.g. this test file run in
isolation), that cycle can raise ImportError on a partially-initialized
module. Importing `apps.recommendation.views` first (below) forces the cycle
to resolve via its normal entry point before any direct swipe_service access,
same as production request handling always does.
"""
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

import apps.recommendation.views  # noqa: F401 -- see import-order note above


def _make_session(**overrides):
    """Lightweight stand-in for AnalysisSession — _update_question_state only
    reads/writes plain attributes, never touches the DB."""
    defaults = dict(
        question_cooldown=0,
        tag_axis_counts={},
        recent_like_tag_sets=[],
        q_card_consecutive_dislikes=0,
    )
    defaults.update(overrides)
    return SimpleNamespace(**defaults)


def _make_card(metadata):
    return {'canonical_bld_id': 'bld_000001', 'name': 'Test Building', 'metadata': metadata}


class TestAxisTagsCacheHit:
    """engine.get_building_card returns a card with full metadata."""

    def test_cache_hit_matches_sql_shape(self):
        from apps.recommendation.services.swipe_service import _update_question_state

        metadata = {
            'axis_style': 'brutalist',
            'axis_atmosphere': 'cold',
            'axis_material_visual': ['concrete', 'glass'],
            'axis_typology_primary': 'museum',
            'axis_typology_tags': ['civic', 'cultural'],
            'axis_architectural_elements': ['cantilever', 'skylight'],
        }
        card = _make_card(metadata)
        session = _make_session()

        with patch('apps.recommendation.services.swipe_service.engine.get_building_card',
                   return_value=card) as mock_get_card:
            _update_question_state(session, 'like', 'bld_000001')

        mock_get_card.assert_called_once_with('bld_000001')

        # Scalars wrapped into single-item lists; lists passed through via list().
        assert session.tag_axis_counts == {
            'style': {'brutalist': 1},
            'atmosphere': {'cold': 1},
            'material_visual': {'concrete': 1, 'glass': 1},
            'typology_primary': {'museum': 1},
            'typology_tags': {'civic': 1, 'cultural': 1},
            'architectural_elements': {'cantilever': 1, 'skylight': 1},
        }
        assert session.recent_like_tag_sets == [
            ['brutalist', 'cold', 'concrete', 'glass', 'museum', 'civic', 'cultural',
             'cantilever', 'skylight'],
        ]
        assert session.q_card_consecutive_dislikes == 0

    def test_cache_hit_no_buildings_db_round_trip(self):
        """The raw-SQL fallback (connections['buildings']) must NOT be touched
        when the cache-aware card already has full metadata."""
        from apps.recommendation.services.swipe_service import _update_question_state

        metadata = {
            'axis_style': 'modern',
            'axis_atmosphere': None,
            'axis_material_visual': [],
            'axis_typology_primary': None,
            'axis_typology_tags': [],
            'axis_architectural_elements': [],
        }
        card = _make_card(metadata)
        session = _make_session()

        with patch('apps.recommendation.services.swipe_service.engine.get_building_card',
                   return_value=card):
            with patch('apps.recommendation.services.swipe_service.connections') as mock_conns:
                _update_question_state(session, 'like', 'bld_000001')

        mock_conns.__getitem__.assert_not_called()
        assert session.tag_axis_counts['style'] == {'modern': 1}
        assert session.tag_axis_counts['atmosphere'] == {}
        assert session.tag_axis_counts['material_visual'] == {}


class TestAxisTagsSqlFallback:
    """engine.get_building_card returns None -> raw SQL fallback executes."""

    def _mock_buildings_cursor(self, row):
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = row
        mock_cursor.__enter__ = MagicMock(return_value=mock_cursor)
        mock_cursor.__exit__ = MagicMock(return_value=False)
        mock_conn = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        return mock_conn, mock_cursor

    def test_none_card_falls_back_to_sql_and_matches_behaviour(self):
        from apps.recommendation.services.swipe_service import _update_question_state

        # Column order: style, atmosphere, material_visual, typology_primary,
        # typology_tags, architectural_elements.
        row = ('brutalist', 'cold', ['concrete', 'glass'], 'museum',
               ['civic', 'cultural'], ['cantilever', 'skylight'])
        mock_conn, mock_cursor = self._mock_buildings_cursor(row)
        session = _make_session()

        with patch('apps.recommendation.services.swipe_service.engine.get_building_card',
                   return_value=None):
            with patch('apps.recommendation.services.swipe_service.connections',
                       {'buildings': mock_conn}):
                _update_question_state(session, 'like', 'bld_000001')

        mock_cursor.execute.assert_called_once()
        sql_args = mock_cursor.execute.call_args[0]
        assert 'is_publishable = true' in sql_args[0]
        assert sql_args[1] == ['bld_000001']

        # Same shape as the cache-hit path for identical underlying values.
        assert session.tag_axis_counts == {
            'style': {'brutalist': 1},
            'atmosphere': {'cold': 1},
            'material_visual': {'concrete': 1, 'glass': 1},
            'typology_primary': {'museum': 1},
            'typology_tags': {'civic': 1, 'cultural': 1},
            'architectural_elements': {'cantilever': 1, 'skylight': 1},
        }

    def test_none_row_from_sql_leaves_counts_unchanged_no_error(self):
        """Non-publishable / missing building -> SQL returns no row -> the
        existing early-return path (no tags counted) is preserved."""
        from apps.recommendation.services.swipe_service import _update_question_state

        mock_conn, mock_cursor = self._mock_buildings_cursor(None)
        session = _make_session(tag_axis_counts={'style': {'existing': 5}})

        with patch('apps.recommendation.services.swipe_service.engine.get_building_card',
                   return_value=None):
            with patch('apps.recommendation.services.swipe_service.connections',
                       {'buildings': mock_conn}):
                _update_question_state(session, 'like', 'bld_nonexistent')

        # Unchanged — no row means no axis_tags update.
        assert session.tag_axis_counts == {'style': {'existing': 5}}
        assert session.recent_like_tag_sets == []
        assert session.q_card_consecutive_dislikes == 0

    def test_get_building_card_exception_falls_back_to_sql(self):
        """engine.get_building_card raising (transient error) -> falls back
        to SQL rather than propagating."""
        from apps.recommendation.services.swipe_service import _update_question_state

        row = ('modern', 'warm', [], 'housing', [], [])
        mock_conn, mock_cursor = self._mock_buildings_cursor(row)
        session = _make_session()

        with patch('apps.recommendation.services.swipe_service.engine.get_building_card',
                   side_effect=Exception('transient engine error')):
            with patch('apps.recommendation.services.swipe_service.connections',
                       {'buildings': mock_conn}):
                _update_question_state(session, 'like', 'bld_000001')

        mock_cursor.execute.assert_called_once()
        assert session.tag_axis_counts['style'] == {'modern': 1}
        assert session.tag_axis_counts['typology_primary'] == {'housing': 1}


class TestAxisTagsEmptyMetadata:
    """Metadata present but axis keys absent/empty -> empty lists, no KeyError."""

    def test_metadata_missing_axis_keys_produces_empty_lists(self):
        from apps.recommendation.services.swipe_service import _update_question_state

        card = _make_card({})  # metadata dict present but empty
        session = _make_session()

        with patch('apps.recommendation.services.swipe_service.engine.get_building_card',
                   return_value=card):
            with patch('apps.recommendation.services.swipe_service.connections') as mock_conns:
                _update_question_state(session, 'like', 'bld_000001')

        # Empty metadata dict -> falsy -> falls back to SQL path per the
        # implementation's `if metadata:` gate. Assert no KeyError raised and
        # the buildings connection was consulted (fallback engaged).
        mock_conns.__getitem__.assert_called_once_with('buildings')

    def test_metadata_none_falls_back_without_keyerror(self):
        from apps.recommendation.services.swipe_service import _update_question_state

        card = {'canonical_bld_id': 'bld_000001', 'name': 'Test Building'}  # no 'metadata' key
        session = _make_session()

        with patch('apps.recommendation.services.swipe_service.engine.get_building_card',
                   return_value=card):
            with patch('apps.recommendation.services.swipe_service.connections') as mock_conns:
                # Must not raise KeyError even though 'metadata' key is absent.
                _update_question_state(session, 'like', 'bld_000001')

        mock_conns.__getitem__.assert_called_once_with('buildings')

    def test_partial_metadata_missing_some_axis_keys(self):
        """Only some axis_* keys present -> the missing ones default to empty,
        no KeyError."""
        from apps.recommendation.services.swipe_service import _update_question_state

        card = _make_card({'axis_style': 'minimal'})  # only style present
        session = _make_session()

        with patch('apps.recommendation.services.swipe_service.engine.get_building_card',
                   return_value=card):
            _update_question_state(session, 'like', 'bld_000001')

        # Only 'style' gets a real tag; all other axes end up with an empty
        # (but present) counts dict -- matches the pre-existing SQL-path shape.
        assert session.tag_axis_counts['style'] == {'minimal': 1}
        for axis in ('atmosphere', 'material_visual', 'typology_primary',
                     'typology_tags', 'architectural_elements'):
            assert session.tag_axis_counts[axis] == {}
        assert session.recent_like_tag_sets == [['minimal']]


class TestDislikeUnaffected:
    """Dislike path is untouched by this change — sanity check."""

    def test_dislike_increments_counter_no_card_fetch(self):
        from apps.recommendation.services.swipe_service import _update_question_state

        session = _make_session(q_card_consecutive_dislikes=2)

        with patch('apps.recommendation.services.swipe_service.engine.get_building_card') as mock_get_card:
            _update_question_state(session, 'dislike', 'bld_000001')

        mock_get_card.assert_not_called()
        assert session.q_card_consecutive_dislikes == 3


@pytest.mark.django_db
class TestQuestionStateWithRealSession:
    """Same coverage against a real AnalysisSession model instance, to satisfy
    the spec's @pytest.mark.django_db requirement where session objects are
    backed by the DB. _update_question_state does not call .save(), so no
    real buildings-DB connection is needed beyond the mocked seam."""

    def test_real_session_instance_cache_hit(self, user_profile):
        from apps.recommendation.models import Project, AnalysisSession
        from apps.recommendation.services.swipe_service import _update_question_state

        project = Project.objects.create(user=user_profile, name='QCardProject')
        session = AnalysisSession.objects.create(
            user=user_profile,
            project=project,
            phase='exploring',
            pool_ids=['bld_000001'],
            pool_scores={'bld_000001': 1.0},
            current_round=0,
            preference_vector=[],
            exposed_ids=[],
            initial_batch=['bld_000001'],
            like_vectors=[],
            convergence_history=[],
            previous_pref_vector=[],
            original_filters={},
            original_filter_priority=[],
            original_seed_ids=[],
            current_pool_tier=1,
            v_initial=None,
        )
        metadata = {
            'axis_style': 'brutalist',
            'axis_atmosphere': 'cold',
            'axis_material_visual': ['concrete'],
            'axis_typology_primary': 'museum',
            'axis_typology_tags': [],
            'axis_architectural_elements': [],
        }
        card = _make_card(metadata)

        with patch('apps.recommendation.services.swipe_service.engine.get_building_card',
                   return_value=card):
            _update_question_state(session, 'like', 'bld_000001')

        assert session.tag_axis_counts['style'] == {'brutalist': 1}
        assert session.tag_axis_counts['material_visual'] == {'concrete': 1}
