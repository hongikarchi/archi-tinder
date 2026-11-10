"""
Management command: send_contest_deadline_reminders (FULL-CONTEST-NOTIF-1)

Daily job (Railway cron 00:00 UTC = 09:00 KST). For every published contest whose
target deadline is still in the future, notify the users who marked it
"interested" (ContestInterest) at D-7 and D-1.

Rules (docs/plans/2026-11-10-contest-deadline-notifications-design.md):
  - target = apply_deadline if set (kind 'apply'), else submission_deadline
    (kind 'deadline'); skipped once target <= now.
  - days_left = KST date(target) - KST date(now).
  - stage 7: 2 <= days_left <= 7 AND the user's interest was created on or before
    the D-7 KST day (target date - 7), i.e. they were already interested when D-7
    arrived. Later-interested users only get stage 1.
  - stage 1: days_left <= 1 (target still in the future).
  - Once per (recipient, contest, stage, deadline instant): idempotent, and a
    changed deadline re-evaluates. Social in_app opt-out is respected.

Usage:
    python manage.py send_contest_deadline_reminders
    python manage.py send_contest_deadline_reminders --dry-run
    python manage.py send_contest_deadline_reminders --now 2026-11-10T00:00:00+00:00
"""
from datetime import timedelta
from zoneinfo import ZoneInfo

from django.core.management.base import BaseCommand, CommandError
from django.db.models.functions import Coalesce
from django.utils import timezone
from django.utils.dateparse import parse_datetime

from apps.contests.models import Contest
from apps.notifications.services import (
    notify_contest_deadline,
    would_notify_contest_deadline,
)

KST = ZoneInfo('Asia/Seoul')
# SQL pre-filter slack: target within now + 9 days covers days_left <= 7 plus any
# KST-date rounding; exact days_left is computed in Python.
_WINDOW_DAYS = 9


class Command(BaseCommand):
    help = 'Send D-7 / D-1 contest deadline notifications to interested users.'

    def add_arguments(self, parser):
        parser.add_argument('--dry-run', action='store_true',
                            help='Count what would be sent; write nothing.')
        parser.add_argument('--now', default=None,
                            help='ISO datetime to use as "now" (default: current time).')

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        now = self._parse_now(options['now'])
        now_kst_date = now.astimezone(KST).date()

        contests = (
            Contest.objects
            .filter(status=Contest.STATUS_PUBLISHED)
            .annotate(target_deadline=Coalesce('apply_deadline', 'submission_deadline'))
            .filter(target_deadline__gt=now,
                    target_deadline__lte=now + timedelta(days=_WINDOW_DAYS))
            .prefetch_related('interests__user')
        )

        scanned = created = skipped = 0
        for contest in contests:
            scanned += 1
            target = contest.target_deadline
            kind = 'apply' if contest.apply_deadline is not None else 'deadline'
            target_kst_date = target.astimezone(KST).date()
            days_left = (target_kst_date - now_kst_date).days
            if days_left > 7:
                continue
            stage = 7 if days_left >= 2 else 1
            d7_cutoff = target_kst_date - timedelta(days=7)

            for interest in contest.interests.all():
                if stage == 7 and interest.created_at.astimezone(KST).date() > d7_cutoff:
                    continue  # late interest: only D-1 applies to them
                recipient = interest.user
                if dry_run:
                    ok = would_notify_contest_deadline(recipient, contest, stage, target)
                else:
                    ok = notify_contest_deadline(recipient, contest, stage, kind, target)
                if ok:
                    created += 1
                else:
                    skipped += 1

        verb = 'would create' if dry_run else 'created'
        self.stdout.write(
            f'send_contest_deadline_reminders: contests scanned={scanned}, '
            f'notifications {verb}={created}, skipped={skipped}'
            f'{" (dry-run)" if dry_run else ""}'
        )

    @staticmethod
    def _parse_now(raw):
        if not raw:
            return timezone.now()
        parsed = parse_datetime(raw)
        if parsed is None:
            raise CommandError(f'--now: invalid ISO datetime: {raw!r}')
        if timezone.is_naive(parsed):
            parsed = timezone.make_aware(parsed, KST)
        return parsed
