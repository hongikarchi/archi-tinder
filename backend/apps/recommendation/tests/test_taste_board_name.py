"""
test_taste_board_name.py — TASTE-BOARD-NAME: auto-naming for Taste session boards.

Coverage:
  (1) Placeholder name → generate_taste_board_name called → auto-name used.
  (2) Dedup: 'Brick House' already exists → 'Brick House (1)' returned.
  (3) Gemini failure → deterministic fallback from filters (style+program).
  (4) All-empty filters + Gemini failure → 'Untitled'.
  (5) User-provided REAL name is NOT overridden.
  (6) _sanitise_board_name: strips punctuation, clamps to 2 words, Title Case.
  (7) _deterministic_board_name: priority order respected.
"""
import pytest
from unittest.mock import MagicMock, patch


# ---------------------------------------------------------------------------
# Unit tests for pure helpers (no DB)
# ---------------------------------------------------------------------------

class TestSanitiseBoardName:

    def test_basic_title_case(self):
        from apps.recommendation.services.generation import _sanitise_board_name
        assert _sanitise_board_name('brick house') == 'Brick House'

    def test_strips_punctuation(self):
        from apps.recommendation.services.generation import _sanitise_board_name
        assert _sanitise_board_name('"Brick House!"') == 'Brick House'

    def test_clamps_to_two_words(self):
        from apps.recommendation.services.generation import _sanitise_board_name
        result = _sanitise_board_name('Japanese Modern Minimalist Architecture')
        assert result == 'Japanese Modern'

    def test_empty_string(self):
        from apps.recommendation.services.generation import _sanitise_board_name
        assert _sanitise_board_name('') == ''

    def test_none(self):
        from apps.recommendation.services.generation import _sanitise_board_name
        assert _sanitise_board_name(None) == ''

    def test_single_word(self):
        from apps.recommendation.services.generation import _sanitise_board_name
        assert _sanitise_board_name('brutalist') == 'Brutalist'

    def test_collapses_whitespace(self):
        from apps.recommendation.services.generation import _sanitise_board_name
        assert _sanitise_board_name('  coastal   pavilion  ') == 'Coastal Pavilion'

    def test_clamps_to_40_chars(self):
        from apps.recommendation.services.generation import _sanitise_board_name
        long_word = 'A' * 50
        result = _sanitise_board_name(long_word)
        assert len(result) <= 40


class TestDeterministicBoardName:

    def test_style_and_program(self):
        from apps.recommendation.services.generation import _deterministic_board_name
        result = _deterministic_board_name({'style': 'modern', 'program': 'museum'})
        assert result == 'Modern Museum'

    def test_style_only(self):
        from apps.recommendation.services.generation import _deterministic_board_name
        result = _deterministic_board_name({'style': 'brutalist'})
        assert result == 'Brutalist'

    def test_empty_filters(self):
        from apps.recommendation.services.generation import _deterministic_board_name
        assert _deterministic_board_name({}) == 'Untitled'

    def test_priority_order_style_wins_over_material(self):
        from apps.recommendation.services.generation import _deterministic_board_name
        # style has higher priority than material
        result = _deterministic_board_name({'material': 'glass', 'style': 'contemporary'})
        assert result.startswith('Contemporary')

    def test_location_fallback(self):
        from apps.recommendation.services.generation import _deterministic_board_name
        result = _deterministic_board_name({'location_country': 'japan'})
        assert result == 'Japan'

    def test_none_values_skipped(self):
        from apps.recommendation.services.generation import _deterministic_board_name
        result = _deterministic_board_name({'style': None, 'program': 'housing'})
        assert result == 'Housing'


# ---------------------------------------------------------------------------
# DB tests for dedup + generate_taste_board_name
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestDedupBoardName:

    def test_unique_name_returned_as_is(self, user_profile):
        from apps.recommendation.services.generation import _dedup_board_name
        result = _dedup_board_name('Brick House', user_profile)
        assert result == 'Brick House'

    def test_conflict_appends_1(self, user_profile):
        from apps.recommendation.models import Project
        from apps.recommendation.services.generation import _dedup_board_name
        Project.objects.create(user=user_profile, name='Brick House')
        result = _dedup_board_name('Brick House', user_profile)
        assert result == 'Brick House (1)'

    def test_conflict_chain(self, user_profile):
        from apps.recommendation.models import Project
        from apps.recommendation.services.generation import _dedup_board_name
        Project.objects.create(user=user_profile, name='Brick House')
        Project.objects.create(user=user_profile, name='Brick House (1)')
        result = _dedup_board_name('Brick House', user_profile)
        assert result == 'Brick House (2)'

    def test_different_user_no_conflict(self, user_profile, other_profile):
        from apps.recommendation.models import Project
        from apps.recommendation.services.generation import _dedup_board_name
        # other_profile already has 'Brick House' — user_profile should get it clean
        Project.objects.create(user=other_profile, name='Brick House')
        result = _dedup_board_name('Brick House', user_profile)
        assert result == 'Brick House'


@pytest.mark.django_db
class TestGenerateTasteBoardName:

    def _make_gemini_response(self, text):
        resp = MagicMock()
        resp.text = text
        return resp

    def test_gemini_success_returns_sanitised_name(self, user_profile):
        """Gemini returns 'Brick House' → function returns 'Brick House' (deduped)."""
        from apps.recommendation.services.generation import generate_taste_board_name
        mock_resp = self._make_gemini_response('Brick House')
        with patch('apps.recommendation.services.generate_content_with_fallback',
                   return_value=mock_resp):
            with patch('apps.recommendation.services._get_client', return_value=MagicMock()):
                result = generate_taste_board_name(
                    user_profile,
                    filters={'style': 'modern', 'program': 'museum'},
                    raw_query='brick buildings',
                )
        assert result == 'Brick House'

    def test_gemini_dedup_appends_suffix(self, user_profile):
        """When 'Brick House' already exists for user, returns 'Brick House (1)'."""
        from apps.recommendation.models import Project
        from apps.recommendation.services.generation import generate_taste_board_name
        Project.objects.create(user=user_profile, name='Brick House')
        mock_resp = self._make_gemini_response('Brick House')
        with patch('apps.recommendation.services.generate_content_with_fallback',
                   return_value=mock_resp):
            with patch('apps.recommendation.services._get_client', return_value=MagicMock()):
                result = generate_taste_board_name(
                    user_profile,
                    filters={'style': 'modern'},
                    raw_query='brick buildings',
                )
        assert result == 'Brick House (1)'

    def test_gemini_failure_fallback_from_filters(self, user_profile):
        """Gemini raises → deterministic fallback from style+program."""
        from apps.recommendation.services.generation import generate_taste_board_name
        with patch('apps.recommendation.services.generate_content_with_fallback',
                   side_effect=RuntimeError('Gemini timeout')):
            with patch('apps.recommendation.services._get_client', return_value=MagicMock()):
                result = generate_taste_board_name(
                    user_profile,
                    filters={'style': 'modern', 'program': 'museum'},
                    raw_query='modern museum',
                )
        assert result == 'Modern Museum'

    def test_gemini_empty_response_fallback(self, user_profile):
        """Gemini returns empty string → fallback from filters."""
        from apps.recommendation.services.generation import generate_taste_board_name
        mock_resp = self._make_gemini_response('')
        with patch('apps.recommendation.services.generate_content_with_fallback',
                   return_value=mock_resp):
            with patch('apps.recommendation.services._get_client', return_value=MagicMock()):
                result = generate_taste_board_name(
                    user_profile,
                    filters={'style': 'brutalist'},
                    raw_query='',
                )
        assert result == 'Brutalist'

    def test_all_empty_filters_gemini_failure_returns_untitled(self, user_profile):
        """All-empty filters + Gemini failure → 'Untitled'."""
        from apps.recommendation.services.generation import generate_taste_board_name
        with patch('apps.recommendation.services.generate_content_with_fallback',
                   side_effect=TimeoutError('timeout')):
            with patch('apps.recommendation.services._get_client', return_value=MagicMock()):
                result = generate_taste_board_name(
                    user_profile,
                    filters={},
                    raw_query='',
                )
        assert result == 'Untitled'


# ---------------------------------------------------------------------------
# Integration: session_service.create_session placeholder detection
# PERF-HOTPATH-1: create_session NEVER calls Gemini synchronously any more —
# it always inserts the deterministic (filters-only) fallback name at create
# time, and (only for placeholder names) registers a post-commit thread that
# may later upgrade the name via Gemini. These tests verify the synchronous
# fallback wiring + immediate return; the async upgrade itself is covered by
# TestAsyncBoardNameUpdate below.
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestCreateSessionAutoName:
    """Verify create_session wiring: placeholder triggers auto-name; real name preserved."""

    _STUB_POOL = ['bld_000001', 'bld_000002', 'bld_000003']
    _STUB_SCORES = {'bld_000001': 1.0, 'bld_000002': 0.9, 'bld_000003': 0.8}
    _STUB_CARD = {'canonical_bld_id': 'bld_000001', 'name': 'Test Building', 'image_url': 'http://x/1.jpg'}

    def _make_request(self, user_profile, name='', filters=None, raw_query='', extra=None):
        """Return a lightweight namespace that satisfies every request.* attribute
        create_session reads:
          - request.data  (dict-like, all payload keys)
          - request.user.id  (accessed when stage_decouple_enabled=True; False in tests
                              but the attribute must exist to avoid AttributeError)
        """
        from types import SimpleNamespace
        data = {
            'name': name,
            'filters': filters or {},
            'raw_query': raw_query,
            'query': None,
            'project_id': None,
            'filter_priority': [],
            'seed_ids': [],
            'force_new': False,
            'visual_description': None,
            'image_focus': None,
        }
        if extra:
            data.update(extra)
        # Wrap data in a SimpleNamespace so .get() works like a dict
        return SimpleNamespace(data=data, user=user_profile.user)

    def _run_create(self, user_profile, name='', filters=None, raw_query='',
                    gemini_name='Brick House', gemini_side_effect=None):
        """Run create_session with the pool/card machinery stubbed.

        gemini_name / gemini_side_effect control the Gemini mock so tests can
        assert it is NEVER consulted synchronously (the response must reflect
        the deterministic fallback regardless of what Gemini would return).
        """
        from apps.recommendation.services.session_service import create_session
        from django.utils import timezone
        from datetime import timedelta
        recent_cutoff = timezone.now() - timedelta(seconds=30)
        request = self._make_request(
            user_profile, name=name, filters=filters or {}, raw_query=raw_query,
        )
        mock_card = self._STUB_CARD
        # farthest_point_from_pool must return a different id each call so the
        # build_initial_batch loop can remove it from tier_ids without ValueError.
        # side_effect as an iterator yields pool ids in sequence, then StopIteration
        # which the loop treats as None (the 'else: break' branch).
        fpp_side_effect = iter(self._STUB_POOL)

        gemini_kwargs = (
            {'side_effect': gemini_side_effect} if gemini_side_effect is not None
            else {'return_value': MagicMock(text=gemini_name)}
        )

        with patch('apps.recommendation.services.generate_content_with_fallback',
                   **gemini_kwargs) as mock_gemini:
            with patch('apps.recommendation.services._get_client', return_value=MagicMock()):
                with patch('apps.recommendation.engine.create_pool_with_relaxation',
                           return_value=(self._STUB_POOL, self._STUB_SCORES, 1)):
                    with patch('apps.recommendation.engine.get_pool_embeddings',
                               return_value={bid: [0.1] * 384 for bid in self._STUB_POOL}):
                        with patch('apps.recommendation.engine.farthest_point_from_pool',
                                   side_effect=fpp_side_effect):
                            with patch('apps.recommendation.engine.get_buildings_by_ids',
                                       return_value=[mock_card, mock_card, mock_card]):
                                with patch('apps.recommendation.engine.get_building_card',
                                           return_value=mock_card):
                                    with patch('apps.recommendation.event_log.emit_event_batch'):
                                        resp = create_session(request, user_profile, recent_cutoff)
        return resp, mock_gemini

    def test_placeholder_empty_gets_deterministic_fallback_no_gemini_call(self, user_profile):
        """Empty name -> deterministic-from-filters fallback; Gemini never called synchronously."""
        from apps.recommendation.models import Project
        resp, mock_gemini = self._run_create(
            user_profile, name='', filters={'style': 'brick'}, gemini_name='Brick House',
        )
        assert resp.status_code == 201
        mock_gemini.assert_not_called()
        pid = resp.data['project_id']
        project = Project.objects.get(project_id=pid)
        assert project.name == 'Brick'
        assert resp.data['name'] == 'Brick'

    def test_placeholder_untitled_gets_deterministic_fallback(self, user_profile):
        """Name='Untitled' -> deterministic fallback applied, no Gemini wait."""
        from apps.recommendation.models import Project
        resp, mock_gemini = self._run_create(
            user_profile, name='Untitled', filters={'style': 'coastal'}, gemini_name='Coastal House',
        )
        assert resp.status_code == 201
        mock_gemini.assert_not_called()
        pid = resp.data['project_id']
        project = Project.objects.get(project_id=pid)
        assert project.name == 'Coastal'

    def test_placeholder_untitled_project_gets_deterministic_fallback(self, user_profile):
        """Name='Untitled Project' -> deterministic fallback applied."""
        from apps.recommendation.models import Project
        resp, mock_gemini = self._run_create(
            user_profile, name='Untitled Project', filters={'style': 'japanese'},
            gemini_name='Japanese Modern',
        )
        assert resp.status_code == 201
        mock_gemini.assert_not_called()
        pid = resp.data['project_id']
        project = Project.objects.get(project_id=pid)
        assert project.name == 'Japanese'

    def test_placeholder_all_empty_filters_falls_back_to_untitled(self, user_profile):
        """No usable filters -> 'Untitled' (deterministic fallback's own default)."""
        from apps.recommendation.models import Project
        resp, mock_gemini = self._run_create(user_profile, name='', filters={})
        assert resp.status_code == 201
        mock_gemini.assert_not_called()
        pid = resp.data['project_id']
        project = Project.objects.get(project_id=pid)
        assert project.name == 'Untitled'

    def test_real_name_not_overridden(self, user_profile):
        """User-provided real name 'My Gallery' is kept unchanged."""
        from apps.recommendation.models import Project
        resp, mock_gemini = self._run_create(user_profile, name='My Gallery', gemini_name='Brick House')
        assert resp.status_code == 201
        mock_gemini.assert_not_called()
        pid = resp.data['project_id']
        project = Project.objects.get(project_id=pid)
        assert project.name == 'My Gallery'

    def test_create_session_returns_immediately_even_if_gemini_would_hang(self, user_profile):
        """Placeholder name + a Gemini mock that would block forever -> response still
        returns promptly with the deterministic fallback name (no .join(timeout=12)
        anywhere on the request path any more).
        """
        import time
        from apps.recommendation.models import Project

        def _hanging_gemini(*args, **kwargs):
            # If create_session ever synchronously waited on this, the test
            # would hang/timeout. It must never be called at all.
            raise AssertionError('Gemini must not be called on the create_session hot path')

        start = time.monotonic()
        resp, mock_gemini = self._run_create(
            user_profile, name='', filters={'style': 'brutalist', 'program': 'museum'},
            gemini_side_effect=_hanging_gemini,
        )
        elapsed = time.monotonic() - start

        assert resp.status_code == 201
        mock_gemini.assert_not_called()
        assert elapsed < 2.0  # well under the old 12s join budget
        pid = resp.data['project_id']
        project = Project.objects.get(project_id=pid)
        assert project.name == 'Brutalist Museum'

    def test_placeholder_registers_post_commit_thread(self, user_profile):
        """Placeholder name + new project -> a callback is registered via
        transaction.on_commit (the async Gemini-upgrade thread spawn)."""
        with patch('apps.recommendation.services.session_service.transaction.on_commit') as mock_on_commit:
            resp, _ = self._run_create(user_profile, name='', filters={'style': 'brick'})
        assert resp.status_code == 201
        mock_on_commit.assert_called_once()

    def test_real_name_does_not_register_post_commit_thread(self, user_profile):
        """Non-placeholder client-provided name -> no on_commit registration
        (no async Gemini upgrade needed; the user's name is final)."""
        with patch('apps.recommendation.services.session_service.transaction.on_commit') as mock_on_commit:
            resp, _ = self._run_create(user_profile, name='My Gallery')
        assert resp.status_code == 201
        mock_on_commit.assert_not_called()


# ---------------------------------------------------------------------------
# _async_board_name_update: post-commit Gemini name-upgrade thread body
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestAsyncBoardNameUpdate:
    """Call the thread function directly (synchronously) — no real threading
    needed to exercise its logic. connections.close_all() is mocked out so
    the test's own SQLite/PG connection survives the call.
    """

    def _run(self, *args, **kwargs):
        from apps.recommendation.services.session_service import _async_board_name_update
        # _async_board_name_update does a LOCAL `from django.db import connections as
        # _connections` (telemetry-thread pattern) -- patch the real django.db.connections
        # object so both the entry and finally close_all() calls are captured.
        with patch('django.db.connections') as mock_conn:
            _async_board_name_update(*args, **kwargs)
        return mock_conn

    def test_applies_gemini_name_when_row_still_matches_fallback(self, user_profile):
        """Gemini succeeds and the row name still equals the fallback -> row updated."""
        from apps.recommendation.models import Project
        project = Project.objects.create(user=user_profile, name='Brick', filters={}, raw_query='')

        with patch('apps.recommendation.services.session_service.services._gemini_board_name_raw',
                   return_value='Brick House'):
            mock_conn = self._run(
                project.pk, 'Brick', {'style': 'brick'}, 'brick buildings', user_profile.pk,
            )

        project.refresh_from_db()
        assert project.name == 'Brick House'
        # close_all called on entry AND in finally (telemetry-thread pattern)
        assert mock_conn.close_all.call_count == 2

    def test_manual_rename_guard_leaves_renamed_row_untouched(self, user_profile):
        """User already renamed the board (name no longer equals fallback) ->
        the async updater must NOT clobber the manual rename."""
        from apps.recommendation.models import Project
        project = Project.objects.create(user=user_profile, name='Brick', filters={}, raw_query='')
        # Simulate a concurrent manual rename via ProjectDetailView.patch.
        Project.objects.filter(pk=project.pk).update(name='My Custom Name')

        with patch('apps.recommendation.services.session_service.services._gemini_board_name_raw',
                   return_value='Brick House'):
            self._run(project.pk, 'Brick', {'style': 'brick'}, 'brick buildings', user_profile.pk)

        project.refresh_from_db()
        assert project.name == 'My Custom Name'

    def test_empty_gemini_result_keeps_fallback(self, user_profile):
        """Gemini returns '' -> fallback name stays, no exception."""
        from apps.recommendation.models import Project
        project = Project.objects.create(user=user_profile, name='Brick', filters={}, raw_query='')

        with patch('apps.recommendation.services.session_service.services._gemini_board_name_raw',
                   return_value=''):
            self._run(project.pk, 'Brick', {'style': 'brick'}, 'brick buildings', user_profile.pk)

        project.refresh_from_db()
        assert project.name == 'Brick'

    def test_gemini_exception_keeps_fallback_and_never_raises(self, user_profile):
        """Gemini raises -> fallback name stays; the thread function itself
        never propagates the exception (would kill a daemon thread silently
        anyway, but the contract is explicit try/except -> log)."""
        from apps.recommendation.models import Project
        project = Project.objects.create(user=user_profile, name='Brick', filters={}, raw_query='')

        with patch('apps.recommendation.services.session_service.services._gemini_board_name_raw',
                   side_effect=RuntimeError('Gemini timeout')):
            # Must not raise.
            self._run(project.pk, 'Brick', {'style': 'brick'}, 'brick buildings', user_profile.pk)

        project.refresh_from_db()
        assert project.name == 'Brick'
