"""Dev-only: enforce the unified-ID rule (display_name == handle) on legacy rows.

Dry-run by default; pass --apply to write. Refuses to run against the
production DB host unless --allow-prod. Output: counts + profile ids only
(never emails / names).
"""
import unicodedata

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from apps.accounts.models import UserProfile
from apps.accounts.serializers import _HANDLE_RE, _HANDLE_RESERVED
from apps.accounts.views.auth import _suggest_handle

_PROD_HOST_MARKER = 'ep-broad-hat'


def _handle_is_valid(handle):
    """Format check only (uniqueness is guaranteed by the DB constraint)."""
    if not handle:
        return False
    if unicodedata.normalize('NFC', handle) != handle:
        return False
    if not _HANDLE_RE.fullmatch(handle):
        return False
    if len(handle) < 2 or len(handle) > 20:
        return False
    return handle.lower() not in _HANDLE_RESERVED


class Command(BaseCommand):
    help = (
        'Assign valid unique handles to profiles lacking one and set '
        'display_name = handle. Dry-run unless --apply.'
    )

    def add_arguments(self, parser):
        parser.add_argument('--apply', action='store_true',
                            help='Write changes (default: dry-run).')
        parser.add_argument('--allow-prod', action='store_true',
                            help='DANGEROUS: allow running against the production host.')

    def handle(self, *args, **options):
        host = str(settings.DATABASES['default'].get('HOST', '') or '')
        if _PROD_HOST_MARKER in host:
            if not options['allow_prod']:
                raise CommandError(
                    'Refusing to run: DATABASES default HOST is the production '
                    'database. This command is dev-only.'
                )
            self.stderr.write(self.style.ERROR(
                '!!! WARNING: --allow-prod set; operating on the PRODUCTION database !!!'
            ))

        apply = options['apply']
        assigned, synced = [], []
        for profile in UserProfile.objects.all().order_by('pk').iterator():
            fields = []
            if not _handle_is_valid(profile.handle):
                # Seed from the old handle, else the display name.
                profile.handle = _suggest_handle(profile.handle or profile.display_name)
                fields.append('handle')
                assigned.append(profile.pk)
            if profile.display_name != profile.handle:
                profile.display_name = profile.handle
                fields.append('display_name')
                synced.append(profile.pk)
            if fields and apply:
                profile.save(update_fields=fields)

        mode = 'APPLIED' if apply else 'DRY-RUN'
        self.stdout.write(f'[{mode}] handles assigned: {len(assigned)} ids={assigned}')
        self.stdout.write(f'[{mode}] display_name synced: {len(synced)} ids={synced}')
        if not apply:
            self.stdout.write('Re-run with --apply to write.')
