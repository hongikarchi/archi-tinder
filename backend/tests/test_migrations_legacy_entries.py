"""
test_migrations_legacy_entries.py -- Verify 0019_normalize_legacy_entry_shapes.

Strategy: import the RunPython callable directly from the migration module and
invoke it against an in-memory SQLite DB (the standard pytest-django setup).
This tests the data-transformation logic, idempotency, and the update_fields
guard (rows that need no change must not be saved), without requiring a full
MigrationExecutor rollback/re-run cycle.

The migration file name starts with a digit so it cannot be imported via dotted
notation.  Use importlib to load it by file path instead.
"""
import importlib.util
import os
import pytest
from django.apps import apps as django_apps
from django.db import connection


def _load_migration():
    """Load 0019_normalize_legacy_entry_shapes.py via importlib (digit-prefixed filename)."""
    migration_path = os.path.join(
        os.path.dirname(__file__),
        '..', 'apps', 'recommendation', 'migrations',
        '0019_normalize_legacy_entry_shapes.py',
    )
    spec = importlib.util.spec_from_file_location('migration_0019', os.path.abspath(migration_path))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


_migration_module = _load_migration()
normalize_entry_shapes = _migration_module.normalize_entry_shapes


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestNormalizeLegacyEntryShapes:

    def test_str_entries_converted_to_dicts(self):
        """str entries in liked_ids / saved_ids become {'id': <str>}."""
        from apps.recommendation.models import Project
        from apps.accounts.models import UserProfile
        from django.contrib.auth.models import User

        user = User.objects.create_user(username='migtest1', email='migtest1@test.com')
        profile = UserProfile.objects.create(user=user, display_name='Mig Test 1')
        project = Project.objects.create(
            user=profile,
            name='Legacy Entry Test',
            liked_ids=['bld_a', {'id': 'bld_b', 'intensity': 1.0}],
            saved_ids=['bld_c'],
        )

        # Run the migration callable directly
        normalize_entry_shapes(django_apps, connection.schema_editor())

        project.refresh_from_db()

        # All liked_ids entries must be dicts with 'id' key
        for entry in project.liked_ids:
            assert isinstance(entry, dict), f"Expected dict, got {type(entry)}: {entry}"
            assert 'id' in entry

        # IDs must be preserved
        liked_id_set = {e['id'] for e in project.liked_ids}
        assert 'bld_a' in liked_id_set
        assert 'bld_b' in liked_id_set

        # saved_ids entries must be dicts with 'id' key
        for entry in project.saved_ids:
            assert isinstance(entry, dict), f"Expected dict, got {type(entry)}: {entry}"
            assert 'id' in entry

        saved_id_set = {e['id'] for e in project.saved_ids}
        assert 'bld_c' in saved_id_set

    def test_dict_entries_untouched(self):
        """Entries already in dict shape must not be modified."""
        from apps.recommendation.models import Project
        from apps.accounts.models import UserProfile
        from django.contrib.auth.models import User

        user = User.objects.create_user(username='migtest2', email='migtest2@test.com')
        profile = UserProfile.objects.create(user=user, display_name='Mig Test 2')
        project = Project.objects.create(
            user=profile,
            name='Already Dict Test',
            liked_ids=[{'id': 'bld_x', 'intensity': 1.8}],
            saved_ids=[{'id': 'bld_y', 'saved_at': '2025-01-01T00:00:00Z'}],
        )
        original_liked = list(project.liked_ids)
        original_saved = list(project.saved_ids)

        normalize_entry_shapes(django_apps, connection.schema_editor())

        project.refresh_from_db()
        assert project.liked_ids == original_liked
        assert project.saved_ids == original_saved

    def test_idempotent_second_run_is_noop(self):
        """Running normalize twice must not change data or bump updated_at."""
        from apps.recommendation.models import Project
        from apps.accounts.models import UserProfile
        from django.contrib.auth.models import User

        user = User.objects.create_user(username='migtest3', email='migtest3@test.com')
        profile = UserProfile.objects.create(user=user, display_name='Mig Test 3')
        project = Project.objects.create(
            user=profile,
            name='Idempotency Test',
            liked_ids=['bld_a', {'id': 'bld_b'}],
            saved_ids=['bld_c'],
        )

        # First run: converts str → dict
        normalize_entry_shapes(django_apps, connection.schema_editor())
        project.refresh_from_db()
        after_first = {
            'liked_ids': list(project.liked_ids),
            'saved_ids': list(project.saved_ids),
            'updated_at': project.updated_at,
        }

        # Second run: no str entries remain; must not save
        normalize_entry_shapes(django_apps, connection.schema_editor())
        project.refresh_from_db()

        assert project.liked_ids == after_first['liked_ids']
        assert project.saved_ids == after_first['saved_ids']
        # updated_at must not have changed (update_fields=['liked_ids','saved_ids']
        # excludes updated_at; auto_now only fires when updated_at is in update_fields
        # or save() is called with no update_fields)
        assert project.updated_at == after_first['updated_at']

    def test_mixed_shape_row_all_become_dicts(self):
        """A row with mixed str + dict entries in both fields is fully normalized."""
        from apps.recommendation.models import Project
        from apps.accounts.models import UserProfile
        from django.contrib.auth.models import User

        user = User.objects.create_user(username='migtest4', email='migtest4@test.com')
        profile = UserProfile.objects.create(user=user, display_name='Mig Test 4')
        project = Project.objects.create(
            user=profile,
            name='Mixed Shape Test',
            liked_ids=['bld_a', {'id': 'bld_b'}, 'bld_c'],
            saved_ids=['bld_d', {'id': 'bld_e', 'saved_at': '2025-01-01T00:00:00Z'}, 'bld_f'],
        )

        normalize_entry_shapes(django_apps, connection.schema_editor())
        project.refresh_from_db()

        assert all(isinstance(e, dict) and 'id' in e for e in project.liked_ids)
        assert all(isinstance(e, dict) and 'id' in e for e in project.saved_ids)

        liked_ids = {e['id'] for e in project.liked_ids}
        assert liked_ids == {'bld_a', 'bld_b', 'bld_c'}

        saved_ids = {e['id'] for e in project.saved_ids}
        assert saved_ids == {'bld_d', 'bld_e', 'bld_f'}
