"""
Management command: contest_poster

  contest_poster <id> set --url <http(s) url> [--credit "<name>"]
  contest_poster <id> clear

Posters are hotlinked by default: a stored poster_url is shown, an empty one
falls back. An operator takes a poster down with `clear`. Production-usable
(not DEBUG-gated). Prints before -> after; exits non-zero on an unknown id or
an invalid URL.
"""
from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from apps.contests.models import Contest
from apps.contests.validators import validate_http_url


class Command(BaseCommand):
    help = 'Set or clear a contest poster URL: set --url ... | clear.'

    def add_arguments(self, parser):
        parser.add_argument('contest_id', type=int)
        parser.add_argument('action', choices=['set', 'clear'])
        parser.add_argument('--url', default=None, help='Poster image URL (http/https).')
        parser.add_argument('--credit', default=None, help='Poster credit / rights holder name.')

    def handle(self, *args, **options):
        try:
            contest = Contest.objects.get(pk=options['contest_id'])
        except Contest.DoesNotExist:
            raise CommandError('contest %s not found' % options['contest_id'])
        before = contest.poster_url
        fields = {}

        if options['action'] == 'set':
            url = (options['url'] or '').strip()
            if not url:
                raise CommandError('set requires --url')
            try:
                validate_http_url(url)
            except ValidationError:
                raise CommandError('--url must be an http(s) URL')
            fields['poster_url'] = url
            if options['credit'] is not None:
                fields['poster_credit'] = options['credit'].strip()
        else:
            fields['poster_url'] = None

        # update(): bypasses Contest.save(); the URL was validated above.
        Contest.objects.filter(pk=contest.pk).update(updated_at=timezone.now(), **fields)
        self.stdout.write(self.style.SUCCESS(
            'contest %d poster_url: %s -> %s' % (contest.pk, before, fields['poster_url'])
        ))
