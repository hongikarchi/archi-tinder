"""
test_reaction.py -- Phase 15 SOC2 reaction backend tests.

Coverage:
  TestReactionCreate         (5)  -- 201 public project, idempotent 200, private non-owner 403,
                                     private owner 201, nonexistent project 404
  TestReactionDelete         (4)  -- 204 + count decrement, not reacted 404,
                                     private non-owner 403, project 404
  TestIsReactedInjection     (4)  -- anon (false), auth+reacted (true),
                                     auth+not-reacted (false), owner of private (true)
  TestReactionModel          (2)  -- unique_together enforced, str representation
  TestReactionEdgeCases      (4)  -- project cascade delete, user cascade (counter decrement),
                                     Greatest floor guard, signal fires on create only
  TestReactionThrottle       (1)  -- throttle scope + class configured
"""
import uuid
import pytest
from django.db import IntegrityError


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_public_project(profile):
    from apps.recommendation.models import Project
    return Project.objects.create(
        user=profile, name='Public Board', visibility='public',
    )


def _make_private_project(profile):
    from apps.recommendation.models import Project
    return Project.objects.create(
        user=profile, name='Private Board', visibility='private',
    )


def _react_url(project_id):
    return f'/api/v1/projects/{project_id}/react/'


def _project_url(project_id):
    return f'/api/v1/projects/{project_id}/'


# ---------------------------------------------------------------------------
# TestReactionCreate
# ---------------------------------------------------------------------------

class TestReactionCreate:

    @pytest.mark.django_db
    def test_react_public_project_returns_201(self, user_a, user_b, auth_client_a):
        """POST /projects/{public}/react/ by non-owner returns 201 with correct shape."""
        _, b_profile = user_b
        project = _make_public_project(b_profile)

        response = auth_client_a.post(_react_url(project.project_id))
        assert response.status_code == 201
        data = response.json()
        assert data['reacted'] is True
        assert 'reaction_count' in data

    @pytest.mark.django_db
    def test_react_increments_reaction_count(self, user_a, user_b, auth_client_a):
        """reaction_count on project is incremented by 1 after POST."""
        _, b_profile = user_b
        project = _make_public_project(b_profile)

        auth_client_a.post(_react_url(project.project_id))
        project.refresh_from_db()
        assert project.reaction_count == 1

    @pytest.mark.django_db
    def test_react_twice_idempotent_200(self, user_a, user_b, auth_client_a):
        """Second POST to react returns 200; reaction_count stays at 1."""
        _, b_profile = user_b
        project = _make_public_project(b_profile)

        auth_client_a.post(_react_url(project.project_id))
        response = auth_client_a.post(_react_url(project.project_id))
        assert response.status_code == 200
        project.refresh_from_db()
        assert project.reaction_count == 1

    @pytest.mark.django_db
    def test_react_private_project_non_owner_returns_403(self, user_a, user_b, auth_client_a):
        """POST to react on private project by non-owner returns 403."""
        _, b_profile = user_b
        project = _make_private_project(b_profile)

        response = auth_client_a.post(_react_url(project.project_id))
        assert response.status_code == 403
        project.refresh_from_db()
        assert project.reaction_count == 0

    @pytest.mark.django_db
    def test_react_private_project_owner_returns_201(self, user_b, auth_client_b):
        """POST to react on own private project returns 201 (owner can react)."""
        _, b_profile = user_b
        project = _make_private_project(b_profile)

        response = auth_client_b.post(_react_url(project.project_id))
        assert response.status_code == 201
        project.refresh_from_db()
        assert project.reaction_count == 1

    @pytest.mark.django_db
    def test_react_nonexistent_project_returns_404(self, auth_client_a):
        """POST to react on non-existent project UUID returns 404."""
        fake_id = str(uuid.uuid4())
        response = auth_client_a.post(_react_url(fake_id))
        assert response.status_code == 404

    @pytest.mark.django_db
    def test_react_response_count_matches_db(self, user_a, user_b, auth_client_a):
        """reaction_count in POST 201 response matches the DB value after signal fires."""
        _, b_profile = user_b
        project = _make_public_project(b_profile)

        response = auth_client_a.post(_react_url(project.project_id))
        assert response.status_code == 201
        project.refresh_from_db()
        assert response.json()['reaction_count'] == project.reaction_count


# ---------------------------------------------------------------------------
# TestReactionDelete
# ---------------------------------------------------------------------------

class TestReactionDelete:

    @pytest.mark.django_db
    def test_unreact_returns_204_and_decrements(self, user_a, user_b, auth_client_a):
        """DELETE after react returns 204 and decrements reaction_count."""
        _, b_profile = user_b
        project = _make_public_project(b_profile)

        auth_client_a.post(_react_url(project.project_id))
        project.refresh_from_db()
        assert project.reaction_count == 1

        response = auth_client_a.delete(_react_url(project.project_id))
        assert response.status_code == 204

        project.refresh_from_db()
        assert project.reaction_count == 0

    @pytest.mark.django_db
    def test_unreact_when_not_reacted_returns_404(self, user_a, user_b, auth_client_a):
        """DELETE when not reacted returns 404 (not idempotent per spec)."""
        _, b_profile = user_b
        project = _make_public_project(b_profile)

        response = auth_client_a.delete(_react_url(project.project_id))
        assert response.status_code == 404

    @pytest.mark.django_db
    def test_unreact_after_visibility_flip_to_private_succeeds(
        self, user_a, user_b, auth_client_a,
    ):
        """User can retract own reaction even after owner flips project to private.

        Spec §3.2 leaves the cascade-on-unpublish dimension open. Reviewer judgment:
        users have unconditional sovereignty over their own reaction row — DELETE
        must not be visibility-gated, otherwise a public→private flip orphans the
        reaction permanently.
        """
        _, b_profile = user_b
        project = _make_public_project(b_profile)

        # User A reacts while public
        response = auth_client_a.post(_react_url(project.project_id))
        assert response.status_code == 201

        # Owner flips to private
        project.visibility = 'private'
        project.save(update_fields=['visibility'])

        # User A can still retract their reaction
        response = auth_client_a.delete(_react_url(project.project_id))
        assert response.status_code == 204

        project.refresh_from_db()
        assert project.reaction_count == 0

    @pytest.mark.django_db
    def test_unreact_private_project_not_reacted_returns_404(
        self, user_a, user_b, auth_client_a,
    ):
        """DELETE on private project where user never reacted returns 404 (not 403)."""
        _, b_profile = user_b
        project = _make_private_project(b_profile)

        response = auth_client_a.delete(_react_url(project.project_id))
        assert response.status_code == 404

    @pytest.mark.django_db
    def test_unreact_nonexistent_project_returns_404(self, auth_client_a):
        """DELETE on non-existent project UUID returns 404."""
        fake_id = str(uuid.uuid4())
        response = auth_client_a.delete(_react_url(fake_id))
        assert response.status_code == 404


# ---------------------------------------------------------------------------
# TestIsReactedInjection
# ---------------------------------------------------------------------------

class TestIsReactedInjection:

    @pytest.mark.django_db
    def test_is_reacted_false_for_unauthenticated(self, user_b, anon_client):
        """GET /projects/{public}/ without auth → is_reacted: false."""
        _, b_profile = user_b
        project = _make_public_project(b_profile)

        response = anon_client.get(_project_url(project.project_id))
        assert response.status_code == 200
        data = response.json()
        assert 'is_reacted' in data
        assert data['is_reacted'] is False

    @pytest.mark.django_db
    def test_is_reacted_true_after_reacting(self, user_a, user_b, auth_client_a):
        """GET /projects/{public}/ by A after A reacts → is_reacted: true."""
        _, b_profile = user_b
        project = _make_public_project(b_profile)

        auth_client_a.post(_react_url(project.project_id))
        response = auth_client_a.get(_project_url(project.project_id))
        assert response.status_code == 200
        assert response.json()['is_reacted'] is True

    @pytest.mark.django_db
    def test_is_reacted_false_when_not_reacted(self, user_a, user_b, auth_client_a):
        """GET /projects/{public}/ by A when A has NOT reacted → is_reacted: false."""
        _, b_profile = user_b
        project = _make_public_project(b_profile)

        response = auth_client_a.get(_project_url(project.project_id))
        assert response.status_code == 200
        assert response.json()['is_reacted'] is False

    @pytest.mark.django_db
    def test_is_reacted_owner_private_after_reacting(self, user_b, auth_client_b):
        """GET /projects/{private}/ by owner after owner reacts → is_reacted: true."""
        _, b_profile = user_b
        project = _make_private_project(b_profile)

        auth_client_b.post(_react_url(project.project_id))
        response = auth_client_b.get(_project_url(project.project_id))
        assert response.status_code == 200
        assert response.json()['is_reacted'] is True


# ---------------------------------------------------------------------------
# TestReactionModel
# ---------------------------------------------------------------------------

class TestReactionModel:

    @pytest.mark.django_db
    def test_unique_together_enforced_at_orm(self, user_a, user_b):
        """Creating duplicate Reaction row via ORM raises IntegrityError."""
        from apps.social.models import Reaction
        _, a_profile = user_a
        _, b_profile = user_b
        project = _make_public_project(b_profile)

        Reaction.objects.create(user=a_profile, project=project)
        with pytest.raises(IntegrityError):
            Reaction.objects.create(user=a_profile, project=project)

    @pytest.mark.django_db
    def test_reaction_str_representation(self, user_a, user_b):
        """str(Reaction) contains user_id and project_id."""
        from apps.social.models import Reaction
        _, a_profile = user_a
        _, b_profile = user_b
        project = _make_public_project(b_profile)

        reaction = Reaction.objects.create(user=a_profile, project=project)
        s = str(reaction)
        assert str(a_profile.pk) in s
        assert str(project.project_id) in s


# ---------------------------------------------------------------------------
# TestReactionEdgeCases
# ---------------------------------------------------------------------------

class TestReactionEdgeCases:

    @pytest.mark.django_db
    def test_project_cascade_delete_removes_reactions(self, user_a, user_b):
        """Deleting the project cascades to its Reaction rows (no orphaned rows)."""
        from apps.social.models import Reaction
        _, a_profile = user_a
        _, b_profile = user_b
        project = _make_public_project(b_profile)

        Reaction.objects.create(user=a_profile, project=project)
        assert Reaction.objects.filter(project=project).count() == 1

        project.delete()
        assert Reaction.objects.filter(user=a_profile).count() == 0

    @pytest.mark.django_db
    def test_user_cascade_decrement_reaction_count(self, user_a, user_b):
        """Deleting the reacting user cascades to Reaction rows.

        post_delete signal fires per deleted Reaction, decrementing
        project.reaction_count via Greatest(..., 0).
        """
        from apps.social.models import Reaction
        user_a_obj, a_profile = user_a
        _, b_profile = user_b
        project = _make_public_project(b_profile)

        Reaction.objects.create(user=a_profile, project=project)
        project.refresh_from_db()
        assert project.reaction_count == 1

        # Delete A's auth user — cascades to UserProfile → Reaction rows.
        user_a_obj.delete()

        project.refresh_from_db()
        assert project.reaction_count == 0

    @pytest.mark.django_db
    def test_greatest_floor_prevents_negative_count(self, user_a, user_b):
        """Simulated double-delete: counter stays >= 0 with Greatest guard.

        Second filter().delete() is a no-op; no post_delete signal fires;
        counter is never decremented below zero.
        """
        from apps.social.models import Reaction
        _, a_profile = user_a
        _, b_profile = user_b
        project = _make_public_project(b_profile)

        Reaction.objects.create(user=a_profile, project=project)
        project.refresh_from_db()
        assert project.reaction_count == 1

        # First delete — should decrement
        deleted, _ = Reaction.objects.filter(user=a_profile, project=project).delete()
        assert deleted == 1
        project.refresh_from_db()
        assert project.reaction_count == 0

        # Second delete — no rows, no signal, count unchanged at 0
        deleted2, _ = Reaction.objects.filter(user=a_profile, project=project).delete()
        assert deleted2 == 0
        project.refresh_from_db()
        assert project.reaction_count == 0

    @pytest.mark.django_db
    def test_signal_increments_on_first_save_only(self, user_a, user_b):
        """post_save signal only increments reaction_count when created=True.

        Calling reaction.save() again (update path, created=False) must NOT
        increment counter a second time.
        """
        from apps.social.models import Reaction
        _, a_profile = user_a
        _, b_profile = user_b
        project = _make_public_project(b_profile)

        reaction = Reaction.objects.create(user=a_profile, project=project)
        project.refresh_from_db()
        assert project.reaction_count == 1

        # Force an update-save (created=False path in signal)
        reaction.save()
        project.refresh_from_db()
        assert project.reaction_count == 1, 'Counter must not double-increment on re-save'


# ---------------------------------------------------------------------------
# TestReactionThrottle
# ---------------------------------------------------------------------------

class TestReactionThrottle:

    def test_reaction_write_throttle_configured(self):
        """ReactionView uses ReactionWriteThrottle; scope registered in settings."""
        from django.conf import settings
        from apps.social.views import ReactionView, ReactionWriteThrottle
        from rest_framework.throttling import UserRateThrottle

        assert issubclass(ReactionWriteThrottle, UserRateThrottle)
        assert ReactionWriteThrottle.scope == 'reaction_write'
        assert ReactionWriteThrottle in ReactionView.throttle_classes

        throttle_rates = settings.REST_FRAMEWORK.get('DEFAULT_THROTTLE_RATES', {})
        assert 'reaction_write' in throttle_rates, (
            "'reaction_write' scope missing from REST_FRAMEWORK DEFAULT_THROTTLE_RATES"
        )
