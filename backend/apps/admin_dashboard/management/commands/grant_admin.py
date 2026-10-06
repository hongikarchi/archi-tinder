"""grant_admin <email> [--revoke] -- set/clear is_staff on the matching User.

is_staff is only ONE of the locks (IsAdminOperator also needs the email in
settings.ADMIN_EMAILS + a Google SocialAccount + non-guest); this command reports the
state of the other two so the operator sees why access may still be denied. Runs under
the runtime DB role (UPDATE is enough, no DDL).
"""
from django.conf import settings
from django.contrib.auth.models import User
from django.core.management.base import BaseCommand, CommandError

from apps.accounts.authentication import invalidate_user_cache
from apps.accounts.models import SocialAccount


class Command(BaseCommand):
    help = 'Grant (or --revoke) admin-dashboard staff status for a user by email.'

    def add_arguments(self, parser):
        parser.add_argument('email')
        parser.add_argument('--revoke', action='store_true', help='Clear is_staff instead of setting it.')

    def handle(self, *args, **opts):
        email = opts['email'].strip()
        users = list(User.objects.filter(email__iexact=email))
        if not users:
            raise CommandError(f'No user with email {email!r}.')
        if len(users) > 1:
            raise CommandError(f'{len(users)} users match {email!r}; refusing to guess.')
        user = users[0]
        revoke = opts['revoke']

        user.is_staff = not revoke
        user.save(update_fields=['is_staff'])
        # CachedJWTAuthentication would otherwise keep serving the stale user row.
        invalidate_user_cache(user.id)

        in_list = email.lower() in getattr(settings, 'ADMIN_EMAILS', ())
        has_google = SocialAccount.objects.filter(user__user=user, provider='google').exists()
        verb = 'revoked' if revoke else 'granted'
        self.stdout.write(self.style.SUCCESS(f'is_staff {verb} for user id={user.id} ({user.email}).'))
        self.stdout.write(f'  email in ADMIN_EMAILS:       {in_list}')
        self.stdout.write(f'  google SocialAccount exists: {has_google}')
        if not revoke and not (in_list and has_google):
            self.stdout.write(self.style.WARNING(
                '  Not yet an admin operator: the other locks above must also be True.'))
