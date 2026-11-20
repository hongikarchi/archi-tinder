"""Tests for messaging migration 0002 (contact request -> follow data conversion)."""
import importlib

import pytest
from django.db import connection
from django.db.migrations.executor import MigrationExecutor

migration = importlib.import_module('apps.messaging.migrations.0002_follow_replaces_contact_request')
plan_follows = migration.plan_follows


class TestPlanFollows:
    def test_accepted_is_mutual(self):
        assert plan_follows([(1, 2, 'accepted')], [], []) == {(1, 2), (2, 1)}

    def test_pending_is_one_way(self):
        assert plan_follows([(1, 2, 'pending')], [], []) == {(1, 2)}

    def test_ignored_not_converted(self):
        assert plan_follows([(1, 2, 'ignored')], [], []) == set()

    def test_block_either_direction_skips_pair(self):
        rows = [(1, 2, 'accepted'), (3, 4, 'pending'), (5, 6, 'accepted')]
        assert plan_follows(rows, [(2, 1), (3, 4)], []) == {(5, 6), (6, 5)}

    def test_pending_skips_ineligible_recipient_accepted_does_not(self):
        rows = [(1, 2, 'pending'), (3, 2, 'accepted'), (4, 5, 'pending')]
        assert plan_follows(rows, [], {2}) == {(3, 2), (2, 3), (4, 5)}

    def test_never_self_edges(self):
        assert plan_follows([(1, 1, 'accepted'), (2, 2, 'pending')], [], []) == set()

    def test_duplicates_collapse_and_empty_is_noop(self):
        rows = [(1, 2, 'pending'), (1, 2, 'pending'), (2, 1, 'pending')]
        assert plan_follows(rows, [], []) == {(1, 2), (2, 1)}
        assert plan_follows([], [], []) == set()


@pytest.mark.django_db(transaction=True)
class TestConvertOnHistoricalModels:
    """Run the real migration against historical models (ContactRequest still exists there)."""

    def _migrate(self, *targets):
        executor = MigrationExecutor(connection)
        executor.migrate(list(targets))
        return MigrationExecutor(connection).loader.project_state(list(targets)).apps

    def _restore_leaf(self):
        self._migrate(*MigrationExecutor(connection).loader.graph.leaf_nodes())

    def test_convert_idempotent_with_counts(self, capsys):
        before = [('messaging', '0001_initial'), ('social', '0008_userfollow')]
        target = [('messaging', '0002_follow_replaces_contact_request')]
        old = self._migrate(*before)
        try:
            User = old.get_model('auth', 'User')
            UserProfile = old.get_model('accounts', 'UserProfile')
            PersonalityProfile = old.get_model('accounts', 'PersonalityProfile')
            ContactRequest = old.get_model('messaging', 'ContactRequest')
            Block = old.get_model('messaging', 'Block')

            def mk(name, guest=False, opt_in=None):
                u = User.objects.create(username=name, email=f'{name}@example.com')
                p = UserProfile.objects.create(user=u, display_name=name, is_guest=guest)
                if opt_in is not None:
                    PersonalityProfile.objects.create(
                        user=p, axis_1=0, axis_2=0, axis_3=0, axis_4=0, axis_5=0,
                        type_code='CLON', discovery_opt_in=opt_in,
                    )
                return p

            a, b, c, d, e, f, g, h = (
                mk('a'), mk('b'), mk('c'), mk('d'), mk('e'),
                mk('f_guest', guest=True), mk('g_optout', opt_in=False), mk('h'),
            )
            ContactRequest.objects.create(sender=a, recipient=b, status='accepted')
            ContactRequest.objects.create(sender=a, recipient=c, status='pending')
            ContactRequest.objects.create(sender=a, recipient=d, status='ignored')
            ContactRequest.objects.create(sender=a, recipient=e, status='pending')
            Block.objects.create(blocker=e, blocked=a)  # blocked -> skipped
            ContactRequest.objects.create(sender=a, recipient=f, status='pending')  # guest
            ContactRequest.objects.create(sender=a, recipient=g, status='pending')  # opt-out
            ContactRequest.objects.create(sender=h, recipient=g, status='accepted')  # survives opt-out

            new = self._migrate(*target)
            out = capsys.readouterr().out
            assert "'accepted': 2" in out and "'pending': 4" in out and "'ignored': 1" in out
            assert 'follows created: 5' in out
            UserFollow = new.get_model('social', 'UserFollow')
            edges = set(UserFollow.objects.values_list('follower_id', 'following_id'))
            assert edges == {
                (a.pk, b.pk), (b.pk, a.pk), (a.pk, c.pk), (h.pk, g.pk), (g.pk, h.pk),
            }

            # Idempotent: run the conversion again with the same data -> no new rows.
            migration.convert_contact_requests(old, None)
            assert UserFollow.objects.count() == 5
            # Nothing was deleted: the legacy rows and the table are still there.
            assert ContactRequest.objects.count() == 7
        finally:
            # The orphaned table is not flushed by pytest-django (Django forgot the
            # model) and its FKs are dropped, so remove the legacy rows ourselves.
            ContactRequest.objects.all().delete()
            self._restore_leaf()

    def test_noop_on_zero_rows(self, capsys):
        old = self._migrate(('messaging', '0001_initial'), ('social', '0008_userfollow'))
        try:
            assert old.get_model('messaging', 'ContactRequest').objects.count() == 0
            self._migrate(('messaging', '0002_follow_replaces_contact_request'))
            out = capsys.readouterr().out
            assert 'nothing to convert' in out
        finally:
            self._restore_leaf()


@pytest.mark.django_db
def test_orphan_table_kept_and_fks_dropped_on_postgres():
    if connection.vendor != 'postgresql':
        pytest.skip('FK drop is Postgres-only')
    with connection.cursor() as cur:
        cur.execute("SELECT to_regclass('messaging_contactrequest') IS NOT NULL")
        assert cur.fetchone()[0] is True  # table kept (a follow-up issue drops it)
        cur.execute(
            "SELECT count(*) FROM pg_constraint "
            "WHERE conrelid = 'messaging_contactrequest'::regclass AND contype = 'f'"
        )
        assert cur.fetchone()[0] == 0
