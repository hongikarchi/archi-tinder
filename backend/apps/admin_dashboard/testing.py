"""Test helper: build a user/client at a chosen point on the IsAdminOperator matrix.

Shared by admin_dashboard tests and by the inspect / office-claims tests that now need a
full admin. Not imported by production code.
"""

ADMIN_TEST_EMAIL = 'admin@example.com'


def make_operator_client(settings, *, username='admin_op', email=ADMIN_TEST_EMAIL, is_staff=True,
                         guest=False, google=True, in_list=True):
    """Return (APIClient with JWT, User). Defaults produce a full admin operator."""
    from django.contrib.auth.models import User
    from rest_framework.test import APIClient
    from rest_framework_simplejwt.tokens import RefreshToken
    from apps.accounts.models import SocialAccount, UserProfile

    user = User.objects.create_user(username=username, email=email, password='testpass123')
    user.is_staff = is_staff
    user.save(update_fields=['is_staff'])
    profile = UserProfile.objects.create(user=user, display_name=username, is_guest=guest)
    if google:
        SocialAccount.objects.create(user=profile, provider='google', provider_id=f'g-{username}')
    settings.ADMIN_EMAILS = frozenset({email.lower()}) if in_list else frozenset()

    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f'Bearer {RefreshToken.for_user(user).access_token}')
    return client, user
