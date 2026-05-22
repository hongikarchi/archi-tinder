"""
test_userserializer.py -- Regression test for UserSerializer.user_id source.

Verifies that UserSerializer returns Django User.id (not UserProfile.id).
The test forces UserProfile.id != User.id by pre-creating a throwaway User so
the auth_user PK sequence runs ahead of the profiles sequence. The divergence
assertion at the top of the test makes it self-checking: if somehow the two ids
are equal, the test skips the interesting assertions and marks the setup wrong.
"""
import pytest
from django.contrib.auth.models import User

from apps.accounts.models import UserProfile
from apps.accounts.serializers import UserSerializer


class TestUserSerializerUserId:

    @pytest.mark.django_db
    def test_user_id_returns_django_user_id_not_profile_id(self, db):
        """UserSerializer.user_id equals User.id, not UserProfile.id.

        Setup: create a throwaway User first (no profile) so the auth_user
        id sequence runs ahead; then create the real User + its UserProfile.
        With separate auto-increment sequences, UserProfile.id == 1 while
        User.id == 2 -- forced divergence that exposes source='id' bugs.
        """
        # Throwaway user: advances the auth_user PK sequence only.
        User.objects.create_user(
            username='throwaway', email='throwaway@example.com', password='pass',
        )

        # Real user + profile -- UserProfile.id will be 1, User.id will be 2.
        real_user = User.objects.create_user(
            username='realuser', email='real@example.com', password='pass123',
        )
        profile = UserProfile.objects.create(
            user=real_user, display_name='Real User',
        )

        # Self-check: the setup must produce divergent ids.
        # If this fails, the id-divergence trick did not work (e.g. DB reset
        # both sequences) and the test cannot distinguish the bug from the fix.
        assert profile.id != profile.user.id, (
            f'Test setup error: profile.id ({profile.id}) == user.id ({profile.user.id}); '
            'id divergence not achieved -- adjust the throwaway-user strategy.'
        )

        data = UserSerializer(profile).data

        # Must equal the Django User pk, not the UserProfile pk.
        assert data['user_id'] == profile.user.id, (
            f"Expected user_id={profile.user.id} (User.id) but got {data['user_id']}. "
            f"UserProfile.id={profile.id}. Likely source='id' bug."
        )

        # Must NOT equal the UserProfile pk (the old buggy value).
        assert data['user_id'] != profile.id, (
            f"user_id={data['user_id']} equals UserProfile.id={profile.id} -- "
            "serializer returned profile PK instead of user PK."
        )
