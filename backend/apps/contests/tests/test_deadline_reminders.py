"""
test_deadline_reminders.py -- send_contest_deadline_reminders (FULL-CONTEST-NOTIF-1).
"""
from datetime import datetime, timedelta, timezone as dt_timezone
from io import StringIO
from zoneinfo import ZoneInfo

import pytest
from django.core.management import call_command

from apps.contests.models import Contest, ContestInterest
from apps.notifications.models import Notification

KST = ZoneInfo('Asia/Seoul')
UTC = dt_timezone.utc
# 2026-11-10 09:00 KST
NOW = datetime(2026, 11, 10, 0, 0, tzinfo=UTC)
LONG_AGO = datetime(2026, 10, 1, 0, 0, tzinfo=UTC)


def kst(y, m, d, h=18, mi=0):
    return datetime(y, m, d, h, mi, tzinfo=KST)


def _make(title='C', **kwargs):
    defaults = dict(
        title=title,
        organizer='Org',
        source_url='https://example.com/',
        submission_deadline=kst(2026, 11, 17),
        status=Contest.STATUS_PUBLISHED,
    )
    defaults.update(kwargs)
    return Contest.objects.create(**defaults)


def _interest(profile, contest, created_at=LONG_AGO):
    i = ContestInterest.objects.create(user=profile, contest=contest)
    ContestInterest.objects.filter(pk=i.pk).update(created_at=created_at)
    return i


def _run(now=NOW, *flags):
    out = StringIO()
    call_command('send_contest_deadline_reminders', *flags, '--now', now.isoformat(), stdout=out)
    return out.getvalue()


def _notifs(profile=None):
    qs = Notification.objects.filter(type='contest_deadline')
    return qs.filter(recipient=profile) if profile is not None else qs


@pytest.mark.django_db
class TestStages:
    def test_d7_fires_once(self, user_a):
        _, a = user_a
        c = _make(submission_deadline=kst(2026, 11, 17))  # days_left 7
        _interest(a, c)
        _run()
        n = _notifs(a).get()
        assert n.category == 'social'
        assert n.actor is None
        assert n.payload['contest_id'] == c.id
        assert n.payload['contest_title'] == 'C'
        assert n.payload['stage'] == 7
        assert n.payload['kind'] == 'deadline'
        assert n.payload['deadline_at'] == c.submission_deadline.astimezone(UTC).isoformat()

    def test_d7_catch_up_at_d3_sends_stage_7_once(self, user_a):
        _, a = user_a
        c = _make(submission_deadline=kst(2026, 11, 13))  # days_left 3
        _interest(a, c)
        _run()
        _run()
        n = _notifs(a).get()
        assert n.payload['stage'] == 7

    def test_d1_window(self, user_a):
        _, a = user_a
        c = _make(submission_deadline=kst(2026, 11, 11))  # days_left 1
        _interest(a, c)
        _run()
        assert [n.payload['stage'] for n in _notifs(a)] == [1]

    def test_same_day_future_deadline_is_stage_1(self, user_a):
        _, a = user_a
        c = _make(submission_deadline=kst(2026, 11, 10, 18))  # days_left 0, future
        _interest(a, c)
        _run()
        assert [n.payload['stage'] for n in _notifs(a)] == [1]

    def test_d7_then_d1_both_sent_over_time(self, user_a):
        _, a = user_a
        c = _make(submission_deadline=kst(2026, 11, 17))
        _interest(a, c)
        _run()
        _run(datetime(2026, 11, 16, 0, 0, tzinfo=UTC))
        assert sorted(n.payload['stage'] for n in _notifs(a)) == [1, 7]

    def test_more_than_7_days_skipped(self, user_a):
        _, a = user_a
        c = _make(submission_deadline=kst(2026, 11, 18))  # days_left 8
        _interest(a, c)
        _run()
        assert not _notifs().exists()


@pytest.mark.django_db
class TestLateInterest:
    def test_late_interest_at_d3_only_gets_d1(self, user_a, user_b):
        _, early = user_a
        _, late = user_b
        c = _make(submission_deadline=kst(2026, 11, 13))  # D-7 day = 11-06 KST
        _interest(early, c, created_at=kst(2026, 11, 6, 8))
        _interest(late, c, created_at=kst(2026, 11, 9, 12))
        _run()
        assert _notifs(early).count() == 1
        assert not _notifs(late).exists()
        # Next day (days_left 2) still no stage 7 for the late user; at D-1 they get stage 1.
        _run(datetime(2026, 11, 12, 0, 0, tzinfo=UTC))
        assert [n.payload['stage'] for n in _notifs(late)] == [1]

    def test_interest_on_d7_kst_day_counts_as_already_interested(self, user_a):
        _, a = user_a
        c = _make(submission_deadline=kst(2026, 11, 17))  # D-7 day = 11-10 KST
        _interest(a, c, created_at=kst(2026, 11, 10, 23, 0))
        _run()
        assert [n.payload['stage'] for n in _notifs(a)] == [7]

    def test_interest_after_d7_kst_day_is_late(self, user_a):
        _, a = user_a
        c = _make(submission_deadline=kst(2026, 11, 17))
        _interest(a, c, created_at=kst(2026, 11, 11, 0, 30))
        _run()
        assert not _notifs(a).exists()


@pytest.mark.django_db
class TestTargetSelection:
    def test_apply_deadline_preferred_kind_apply(self, user_a):
        _, a = user_a
        c = _make(apply_deadline=kst(2026, 11, 17), submission_deadline=kst(2026, 12, 25))
        _interest(a, c)
        _run()
        n = _notifs(a).get()
        assert n.payload['kind'] == 'apply'
        assert n.payload['deadline_at'] == c.apply_deadline.astimezone(UTC).isoformat()

    def test_fallback_submission_kind_deadline(self, user_a):
        _, a = user_a
        c = _make(submission_deadline=kst(2026, 11, 17))
        _interest(a, c)
        _run()
        assert _notifs(a).get().payload['kind'] == 'deadline'

    def test_past_apply_deadline_does_not_fall_back_to_submission(self, user_a):
        _, a = user_a
        c = _make(apply_deadline=kst(2026, 11, 9), submission_deadline=kst(2026, 11, 14))
        _interest(a, c)
        _run()
        assert not _notifs().exists()

    @pytest.mark.parametrize('status', [Contest.STATUS_HIDDEN, Contest.STATUS_PENDING])
    def test_unpublished_skipped(self, user_a, status):
        _, a = user_a
        c = _make(status=status, source_url='')
        _interest(a, c)
        _run()
        assert not _notifs().exists()

    def test_past_deadline_skipped(self, user_a):
        _, a = user_a
        c = _make(submission_deadline=datetime(2026, 11, 9, 23, 59, tzinfo=UTC))
        _interest(a, c)
        _run()
        assert not _notifs().exists()

    def test_deadline_earlier_today_skipped(self, user_a):
        _, a = user_a
        c = _make(submission_deadline=datetime(2026, 11, 9, 23, 59, tzinfo=UTC))  # 11-10 08:59 KST
        _interest(a, c)
        _run()
        assert not _notifs().exists()

    def test_only_interested_users_notified(self, user_a, user_b):
        _, a = user_a
        _, b = user_b
        c = _make(submission_deadline=kst(2026, 11, 11))
        _interest(a, c)
        _run()
        assert _notifs(a).count() == 1
        assert not _notifs(b).exists()


@pytest.mark.django_db
class TestGatingAndIdempotency:
    def test_social_in_app_off_skipped(self, user_a, user_b):
        _, a = user_a
        _, b = user_b
        a.notifications = {'social': {'in_app': False}}
        a.save()
        c = _make(submission_deadline=kst(2026, 11, 11))
        _interest(a, c)
        _interest(b, c)
        _run()
        assert not _notifs(a).exists()
        assert _notifs(b).count() == 1

    def test_idempotent_rerun_even_after_read(self, user_a):
        _, a = user_a
        c = _make(submission_deadline=kst(2026, 11, 11))
        _interest(a, c)
        _run()
        Notification.objects.update(read_at=NOW)
        out = _run()
        assert _notifs(a).count() == 1
        assert 'created=0' in out

    def test_changed_deadline_sends_new_reminder(self, user_a):
        _, a = user_a
        c = _make(submission_deadline=kst(2026, 11, 11))
        _interest(a, c)
        _run()
        Contest.objects.filter(pk=c.pk).update(submission_deadline=kst(2026, 11, 12))
        _run()
        deadlines = {n.payload['deadline_at'] for n in _notifs(a)}
        assert len(deadlines) == 2
        assert _notifs(a).count() == 2

    def test_dry_run_writes_nothing(self, user_a):
        _, a = user_a
        c = _make(submission_deadline=kst(2026, 11, 11))
        _interest(a, c)
        out = _run(NOW, '--dry-run')
        assert not Notification.objects.exists()
        assert 'would create=1' in out
        assert 'dry-run' in out
        out2 = _run()
        assert 'created=1' in out2
        assert _notifs(a).count() == 1

    def test_summary_line(self, user_a):
        _, a = user_a
        c = _make(submission_deadline=kst(2026, 11, 11))
        _interest(a, c)
        out = _run()
        assert 'contests scanned=1' in out
        assert 'created=1' in out


@pytest.mark.django_db
class TestKstBoundary:
    def test_utc_evening_is_next_kst_day(self, user_a):
        _, a = user_a
        # now = 2026-11-10T15:30Z = 2026-11-11 00:30 KST. Target 11-12 18:00 KST:
        # KST days_left 1 -> stage 1 (UTC dates would say 2 -> stage 7).
        c = _make(submission_deadline=kst(2026, 11, 12))
        _interest(a, c)
        _run(datetime(2026, 11, 10, 15, 30, tzinfo=UTC))
        assert [n.payload['stage'] for n in _notifs(a)] == [1]

    def test_target_utc_date_differs_from_kst_date(self, user_a):
        _, a = user_a
        # Target 2026-11-17 02:00 KST = 11-16 17:00Z. KST days_left from 11-10 = 7.
        c = _make(submission_deadline=kst(2026, 11, 17, 2))
        _interest(a, c)
        _run()
        assert [n.payload['stage'] for n in _notifs(a)] == [7]

    def test_naive_now_treated_as_kst(self, user_a):
        _, a = user_a
        c = _make(submission_deadline=kst(2026, 11, 11))
        _interest(a, c)
        out = StringIO()
        call_command('send_contest_deadline_reminders', '--now', '2026-11-10T09:00:00', stdout=out)
        assert _notifs(a).count() == 1

    def test_invalid_now_errors(self):
        from django.core.management.base import CommandError
        with pytest.raises(CommandError):
            call_command('send_contest_deadline_reminders', '--now', 'nope')


@pytest.mark.django_db
class TestServiceDirect:
    def test_returns_bool_and_dedupes(self, user_a):
        from apps.notifications.services import notify_contest_deadline
        _, a = user_a
        c = _make()
        dl = c.submission_deadline
        assert notify_contest_deadline(a, c, 7, 'deadline', dl) is True
        assert notify_contest_deadline(a, c, 7, 'deadline', dl) is False
        assert notify_contest_deadline(a, c, 1, 'deadline', dl) is True
        assert Notification.objects.count() == 2

    def test_never_raises(self, user_a):
        from apps.notifications.services import notify_contest_deadline
        _, a = user_a
        assert notify_contest_deadline(a, None, 7, 'deadline', timedelta(0)) is False
