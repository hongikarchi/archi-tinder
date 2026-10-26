"""Dev-only: enforce the unified-ID rule (display_name == handle) on legacy rows.

Dry-run by default; pass --apply to write. Refuses to run against the
production DB host unless --allow-prod. Output: counts + profile ids only
(never emails / names).
"""
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from apps.accounts.models import UserProfile
from apps.accounts.identity import ensure_unified_identity

_PROD_HOST_MARKER = 'ep-broad-hat'


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
            # Seed from the old handle, else the display name.
            fields = ensure_unified_identity(
                profile, profile.handle or profile.display_name, replace_invalid=True,
            )
            if 'handle' in fields:
                assigned.append(profile.pk)
            if 'display_name' in fields:
                synced.append(profile.pk)
            if fields and apply:
                profile.save(update_fields=fields)

        mode = 'APPLIED' if apply else 'DRY-RUN'
        self.stdout.write(f'[{mode}] handles assigned: {len(assigned)} ids={assigned}')
        self.stdout.write(f'[{mode}] display_name synced: {len(synced)} ids={synced}')
        if not apply:
            self.stdout.write('Re-run with --apply to write.')
