"""
Management command: contest_status <id> published|hidden|pending

Production-usable (not DEBUG-gated). Prints before -> after; exits non-zero on
an unknown id (docs/decisions/2026-10-09-contest-real-data.md D3, 4-3).
"""
from django.core.management.base import BaseCommand, CommandError

from apps.contests.models import Contest


class Command(BaseCommand):
    help = 'Set a contest status: published | hidden | pending.'

    def add_arguments(self, parser):
        parser.add_argument('contest_id', type=int)
        parser.add_argument(
            'status', choices=[Contest.STATUS_PUBLISHED, Contest.STATUS_HIDDEN, Contest.STATUS_PENDING],
        )

    def handle(self, *args, **options):
        try:
            contest = Contest.objects.get(pk=options['contest_id'])
        except Contest.DoesNotExist:
            raise CommandError('contest %s not found' % options['contest_id'])
        before = contest.status
        Contest.objects.filter(pk=contest.pk).update(status=options['status'])
        self.stdout.write(self.style.SUCCESS(
            'contest %d status: %s -> %s' % (contest.pk, before, options['status'])
        ))
