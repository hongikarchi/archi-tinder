"""
test_bookmark.py -- Sprint 4 Result page bookmark endpoint tests.

Covers POST /api/v1/projects/<project_id>/bookmark/ per spec §8 + Spec v1.2 §6.
Tests: toggle semantics, rank_zone derivation, event emission, validation, auth isolation.
"""
import pytest
from apps.recommendation.models import Project, SessionEvent


def _make_project(user_profile, saved_ids=None):
    return Project.objects.create(
        user=user_profile,
        name='Bookmark Test Project',
        saved_ids=saved_ids or [],
    )


def _bookmark_url(project_id):
    return f'/api/v1/projects/{project_id}/bookmark/'


def _payload(card_id='B00042', action='save', rank=5, session_id=None):
    data = {'card_id': card_id, 'action': action, 'rank': rank}
    if session_id is not None:
        data['session_id'] = str(session_id)
    return data


# ── Toggle semantics ───────────────────────────────────────────────────────────

@pytest.mark.django_db
class TestBookmarkToggleSemantics:

    def test_save_bookmark_updates_saved_ids(self, auth_client, user_profile):
        project = _make_project(user_profile)
        resp = auth_client.post(
            _bookmark_url(project.project_id),
            _payload(card_id='B00042', action='save', rank=3),
            format='json',
        )
        assert resp.status_code == 200
        data = resp.json()
        assert 'B00042' in data['saved_ids']
        assert data['count'] == 1

        project.refresh_from_db()
        ids = [e['id'] for e in project.saved_ids if isinstance(e, dict)]
        assert 'B00042' in ids

    def test_save_idempotent(self, auth_client, user_profile):
        """POSTing save twice for the same card yields exactly one entry."""
        project = _make_project(user_profile)
        for _ in range(2):
            resp = auth_client.post(
                _bookmark_url(project.project_id),
                _payload(card_id='B00042', action='save', rank=1),
                format='json',
            )
            assert resp.status_code == 200

        project.refresh_from_db()
        ids = [e['id'] for e in project.saved_ids if isinstance(e, dict)]
        assert ids.count('B00042') == 1
        assert len(ids) == 1

    def test_unsave_removes_from_saved_ids(self, auth_client, user_profile):
        project = _make_project(user_profile)
        # Save first
        auth_client.post(
            _bookmark_url(project.project_id),
            _payload(card_id='B00042', action='save', rank=2),
            format='json',
        )
        # Then unsave
        resp = auth_client.post(
            _bookmark_url(project.project_id),
            _payload(card_id='B00042', action='unsave', rank=2),
            format='json',
        )
        assert resp.status_code == 200
        data = resp.json()
        assert 'B00042' not in data['saved_ids']
        assert data['count'] == 0

        project.refresh_from_db()
        ids = [e['id'] for e in project.saved_ids if isinstance(e, dict)]
        assert 'B00042' not in ids

    def test_unsave_when_not_saved_is_noop(self, auth_client, user_profile):
        """Unsaving a card that was never saved returns 200 with empty list."""
        project = _make_project(user_profile)
        resp = auth_client.post(
            _bookmark_url(project.project_id),
            _payload(card_id='B99999', action='unsave', rank=10),
            format='json',
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data['saved_ids'] == []
        assert data['count'] == 0


# ── Validation ─────────────────────────────────────────────────────────────────

@pytest.mark.django_db
class TestBookmarkValidation:

    def test_invalid_action_rejected(self, auth_client, user_profile):
        project = _make_project(user_profile)
        resp = auth_client.post(
            _bookmark_url(project.project_id),
            {'card_id': 'B00042', 'action': 'invalid', 'rank': 1},
            format='json',
        )
        assert resp.status_code == 400
        assert 'action' in resp.json()['detail'].lower()

    def test_rank_zero_rejected(self, auth_client, user_profile):
        project = _make_project(user_profile)
        resp = auth_client.post(
            _bookmark_url(project.project_id),
            {'card_id': 'B00042', 'action': 'save', 'rank': 0},
            format='json',
        )
        assert resp.status_code == 400

    def test_rank_over_100_rejected(self, auth_client, user_profile):
        project = _make_project(user_profile)
        resp = auth_client.post(
            _bookmark_url(project.project_id),
            {'card_id': 'B00042', 'action': 'save', 'rank': 101},
            format='json',
        )
        assert resp.status_code == 400

    def test_rank_string_rejected(self, auth_client, user_profile):
        project = _make_project(user_profile)
        resp = auth_client.post(
            _bookmark_url(project.project_id),
            {'card_id': 'B00042', 'action': 'save', 'rank': 'abc'},
            format='json',
        )
        assert resp.status_code == 400

    def test_missing_card_id_rejected(self, auth_client, user_profile):
        project = _make_project(user_profile)
        resp = auth_client.post(
            _bookmark_url(project.project_id),
            {'action': 'save', 'rank': 1},
            format='json',
        )
        assert resp.status_code == 400

    def test_empty_card_id_rejected(self, auth_client, user_profile):
        project = _make_project(user_profile)
        resp = auth_client.post(
            _bookmark_url(project.project_id),
            {'card_id': '', 'action': 'save', 'rank': 1},
            format='json',
        )
        assert resp.status_code == 400

    def test_card_id_too_long_rejected(self, auth_client, user_profile):
        project = _make_project(user_profile)
        resp = auth_client.post(
            _bookmark_url(project.project_id),
            {'card_id': 'B' * 21, 'action': 'save', 'rank': 1},
            format='json',
        )
        assert resp.status_code == 400

    def test_card_id_non_string_rejected(self, auth_client, user_profile):
        project = _make_project(user_profile)
        resp = auth_client.post(
            _bookmark_url(project.project_id),
            {'card_id': 12345, 'action': 'save', 'rank': 1},
            format='json',
        )
        assert resp.status_code == 400


# ── Event emission ─────────────────────────────────────────────────────────────

@pytest.mark.django_db
class TestBookmarkEventEmission:

    def test_emits_bookmark_event_with_rank_zone_primary(self, auth_client, user_profile):
        """rank <= 10 → rank_zone == 'primary'."""
        project = _make_project(user_profile)
        resp = auth_client.post(
            _bookmark_url(project.project_id),
            _payload(card_id='B00042', action='save', rank=5),
            format='json',
        )
        assert resp.status_code == 200
        event = SessionEvent.objects.filter(
            user=user_profile, event_type='bookmark',
        ).order_by('-created_at').first()
        assert event is not None
        assert event.payload['rank_zone'] == 'primary'
        assert event.payload['card_id'] == 'B00042'

    def test_emits_bookmark_event_with_rank_zone_secondary(self, auth_client, user_profile):
        """rank > 10 → rank_zone == 'secondary'."""
        project = _make_project(user_profile)
        resp = auth_client.post(
            _bookmark_url(project.project_id),
            _payload(card_id='B00043', action='save', rank=15),
            format='json',
        )
        assert resp.status_code == 200
        event = SessionEvent.objects.filter(
            user=user_profile, event_type='bookmark',
        ).order_by('-created_at').first()
        assert event is not None
        assert event.payload['rank_zone'] == 'secondary'

    def test_emits_bookmark_event_with_provenance_placeholder(self, auth_client, user_profile):
        """All 3 provenance booleans default False (Sprint 4 frontend wire-up deferred)."""
        project = _make_project(user_profile)
        auth_client.post(
            _bookmark_url(project.project_id),
            _payload(card_id='B00044', action='save', rank=1),
            format='json',
        )
        event = SessionEvent.objects.filter(
            user=user_profile, event_type='bookmark',
        ).order_by('-created_at').first()
        assert event is not None
        prov = event.payload['provenance']
        assert prov['in_cosine_top10'] is False
        assert prov['in_gemini_top10'] is False
        assert prov['in_dpp_top10'] is False

    def test_emits_bookmark_event_with_action_field(self, auth_client, user_profile):
        """Event payload carries action value for analytics."""
        project = _make_project(user_profile)
        auth_client.post(
            _bookmark_url(project.project_id),
            _payload(card_id='B00045', action='save', rank=7),
            format='json',
        )
        event = SessionEvent.objects.filter(
            user=user_profile, event_type='bookmark',
        ).order_by('-created_at').first()
        assert event is not None
        assert event.payload['action'] == 'save'

    def test_rank_corpus_is_none_placeholder(self, auth_client, user_profile):
        """rank_corpus emitted as null (Investigation 08 deferred)."""
        project = _make_project(user_profile)
        auth_client.post(
            _bookmark_url(project.project_id),
            _payload(card_id='B00046', action='save', rank=3),
            format='json',
        )
        event = SessionEvent.objects.filter(
            user=user_profile, event_type='bookmark',
        ).order_by('-created_at').first()
        assert event is not None
        assert event.payload['rank_corpus'] is None


# ── Auth / ownership ───────────────────────────────────────────────────────────

@pytest.mark.django_db
class TestBookmarkAuthIsolation:

    def test_unauthorized_other_user_project_404(self, auth_client, user_profile):
        """Bookmark on a project owned by another user returns 404."""
        from django.contrib.auth.models import User
        from apps.accounts.models import UserProfile
        other_user = User.objects.create_user(
            username='other_bm_user', email='other_bm@test.com', password='pass123',
        )
        other_profile = UserProfile.objects.create(
            user=other_user, display_name='Other BM User',
        )
        project = Project.objects.create(user=other_profile, name='NotMine')
        resp = auth_client.post(
            _bookmark_url(project.project_id),
            _payload(),
            format='json',
        )
        assert resp.status_code == 404

    def test_unauthenticated_returns_401(self, api_client, user_profile):
        project = _make_project(user_profile)
        resp = api_client.post(
            _bookmark_url(project.project_id),
            _payload(),
            format='json',
        )
        assert resp.status_code == 401

    def test_invalid_session_id_silently_ignored(self, auth_client, user_profile):
        """A non-UUID session_id must not crash the request; event still emitted."""
        project = _make_project(user_profile)
        resp = auth_client.post(
            _bookmark_url(project.project_id),
            {**_payload(), 'session_id': 'not-a-uuid'},
            format='json',
        )
        assert resp.status_code == 200
