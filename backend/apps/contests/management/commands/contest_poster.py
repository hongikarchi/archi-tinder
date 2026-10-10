"""
Management command: contest_poster

  contest_poster <id> allow --url <https url> --credit "<name>" --basis "<공공누리 type or mail date>"
  contest_poster <id> restore   (only when poster_url and a stored basis exist)
  contest_poster <id> none

Production-usable (not DEBUG-gated). Poster 'allowed' needs documented
permission evidence (D6). Prints before -> after; exits non-zero on an unknown
id or a refused transition.
"""
from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from apps.contests.models import Contest
from apps.contests.validators import validate_http_url


class Command(BaseCommand):
    help = 'Manage a contest poster: allow (with evidence) | restore | none.'

    def add_arguments(self, parser):
        parser.add_argument('contest_id', type=int)
        parser.add_argument('action', choices=['allow', 'restore', 'none'])
        parser.add_argument('--url', default=None, help='Poster image URL (http/https).')
        parser.add_argument('--credit', default=None, help='Poster credit / rights holder name.')
        parser.add_argument('--basis', default=None, help='Permission basis (공공누리 type or mail date).')

    def handle(self, *args, **options):
        try:
            contest = Contest.objects.get(pk=options['contest_id'])
        except Contest.DoesNotExist:
            raise CommandError('contest %s not found' % options['contest_id'])
        before = contest.poster_status
        action = options['action']
        fields = {}

        if action == 'allow':
            url = (options['url'] or '').strip()
            basis = (options['basis'] or '').strip()
            if not url:
                raise CommandError('allow requires --url')
            if not basis:
                raise CommandError('allow requires a non-empty --basis')
            try:
                validate_http_url(url)
            except ValidationError:
                raise CommandError('--url must be an http(s) URL')
            fields = {
                'poster_url': url,
                'poster_credit': (options['credit'] or '').strip(),
                'poster_permission_basis': basis,
                'poster_permission_at': timezone.now(),
                'poster_status': Contest.POSTER_ALLOWED,
            }
        elif action == 'restore':
            if not contest.poster_url or not contest.poster_permission_basis:
                raise CommandError(
                    'restore needs both a stored poster_url and a permission basis; '
                    'use "allow --url ... --basis ..." instead'
                )
            try:
                validate_http_url(contest.poster_url)
            except ValidationError:
                raise CommandError('stored poster_url is not an http(s) URL')
            fields = {'poster_status': Contest.POSTER_ALLOWED}
        else:
            fields = {'poster_status': Contest.POSTER_NONE}

        # update(): bypasses Contest.save(); inputs were validated above.
        Contest.objects.filter(pk=contest.pk).update(updated_at=timezone.now(), **fields)
        self.stdout.write(self.style.SUCCESS(
            'contest %d poster_status: %s -> %s' % (contest.pk, before, fields['poster_status'])
        ))
