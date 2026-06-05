import logging
import os
import uuid as _uuid
import requests
from django.contrib.auth.models import User
from django.db import transaction
from django.utils import timezone
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import AnonRateThrottle
from rest_framework.views import APIView
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.tokens import RefreshToken
from django.conf import settings

from rest_framework_simplejwt.settings import api_settings

from ..authentication import invalidate_user_cache
from ..models import UserProfile, SocialAccount
from ..serializers import UserSerializer
from ..throttling import GuestLoginThrottle, GuestPromoteThrottle

logger = logging.getLogger('apps.accounts')


# -- Guest helpers -------------------------------------------------------------

VALID_ONBOARDING_ROLES = {choice[0] for choice in UserProfile.ONBOARDING_ROLE_CHOICES}


def _clean_guest_display_name(value):
    """Trim and truncate display_name; fall back to 'Guest'."""
    if not isinstance(value, str):
        return 'Guest'
    value = value.strip()
    if not value:
        return 'Guest'
    return value[:30]


def _exchange_google_code(code):
    """Exchange Google auth code for user info dict.

    Returns dict with keys: provider_id, email, display_name, avatar_url.
    Raises ValueError on any failure so callers can return 400/502.

    Defined as a module-level function so tests can monkeypatch it at its own
    module path (NOT the facade path — the facade re-export is a name copy and
    does not intercept this binding):
        monkeypatch.setattr('apps.accounts.views.auth._exchange_google_code',
                            lambda code: {'provider_id': '...', ...})
    """
    try:
        token_resp = requests.post(
            'https://oauth2.googleapis.com/token',
            data={
                'code': code,
                'client_id': settings.GOOGLE_CLIENT_ID,
                'client_secret': settings.GOOGLE_CLIENT_SECRET,
                'redirect_uri': 'postmessage',
                'grant_type': 'authorization_code',
            },
            timeout=10,
        )
    except requests.RequestException as exc:
        raise ValueError(f'Google token exchange network error: {exc}') from exc

    if token_resp.status_code != 200:
        raise ValueError(
            f'Google token exchange failed: status={token_resp.status_code}'
        )
    access_token = token_resp.json().get('access_token')
    if not access_token:
        raise ValueError('Google token exchange returned no access_token')

    try:
        userinfo_resp = requests.get(
            'https://www.googleapis.com/oauth2/v3/userinfo',
            headers={'Authorization': f'Bearer {access_token}'},
            timeout=10,
        )
    except requests.RequestException as exc:
        raise ValueError(f'Google userinfo network error: {exc}') from exc

    if userinfo_resp.status_code != 200:
        raise ValueError(
            f'Google userinfo failed: status={userinfo_resp.status_code}'
        )
    info = userinfo_resp.json()
    return {
        'provider_id': info['sub'],
        'email': info.get('email', ''),
        'display_name': info.get('name', ''),
        'avatar_url': info.get('picture', ''),
    }


class DevLoginThrottle(AnonRateThrottle):
    rate = '5/minute'


def _get_or_create_user(provider, provider_id, email, display_name, avatar_url):
    """Find or create a UserProfile, linking by email for account merging."""
    social = SocialAccount.objects.filter(provider=provider, provider_id=provider_id).first()
    if social:
        profile = social.user
        update_fields = []
        if display_name:
            profile.display_name = display_name
            update_fields.append('display_name')
        if avatar_url:
            profile.avatar_url = avatar_url
            update_fields.append('avatar_url')
        if update_fields:
            profile.save(update_fields=update_fields)
        return profile

    # Check if email matches an existing account (account linking)
    profile = None
    if email:
        existing_user = User.objects.filter(email=email).first()
        if existing_user:
            profile = getattr(existing_user, 'profile', None)

    if profile is None:
        username = f'{provider}_{provider_id}'[:150]
        # Ensure unique username
        base = username
        n = 1
        while User.objects.filter(username=username).exists():
            username = f'{base}_{n}'
            n += 1
        django_user = User.objects.create_user(username=username, email=email or '')
        profile = UserProfile.objects.create(
            user=django_user,
            display_name=display_name or email or provider_id,
            avatar_url=avatar_url,
        )
    else:
        # Always sync display_name + avatar_url from the provider on every login
        update_fields = []
        if display_name:
            profile.display_name = display_name
            update_fields.append('display_name')
        if avatar_url:
            profile.avatar_url = avatar_url
            update_fields.append('avatar_url')
        if update_fields:
            profile.save(update_fields=update_fields)

    SocialAccount.objects.get_or_create(
        provider=provider,
        provider_id=provider_id,
        defaults={'user': profile},
    )
    return profile


def _make_token_response(profile):
    refresh = RefreshToken.for_user(profile.user)
    refresh['is_guest'] = profile.is_guest  # set on refresh BEFORE access_token so rotation propagates
    return {
        'access':  str(refresh.access_token),
        'refresh': str(refresh),
        'user':    UserSerializer(profile).data,
    }


# -- Guest (terminal wizard onboarding) ------------------------------------

class GuestLoginView(APIView):
    """POST /api/v1/auth/guest/

    Creates a lightweight guest account (is_guest=True, no email) from the
    terminal wizard onboarding flow.

    Body: {display_name, onboarding_role, consent_accepted: true,
           consent_policy_version: '1.0'}

    Rejects if consent_accepted is missing or false (PIPA requirement).
    Returns {access, refresh, user} — access token carries is_guest=True claim.
    """
    permission_classes = [AllowAny]
    authentication_classes = []
    throttle_classes = [GuestLoginThrottle]

    def post(self, request):
        # PIPA consent gate — must be JSON boolean true, not truthy string
        if request.data.get('consent_accepted') is not True:
            return Response(
                {'detail': 'consent_required',
                 'reason': 'PIPA consent must be explicitly accepted'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        display_name = _clean_guest_display_name(request.data.get('display_name'))

        onboarding_role = request.data.get('onboarding_role', '')
        if onboarding_role and onboarding_role not in VALID_ONBOARDING_ROLES:
            return Response(
                {'onboarding_role': 'Invalid onboarding role.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if onboarding_role is None:
            onboarding_role = ''

        policy_version = request.data.get('consent_policy_version', '1.0')
        if not isinstance(policy_version, str) or len(policy_version) > 10:
            policy_version = '1.0'

        with transaction.atomic():
            django_user = User(
                username=f'guest_{_uuid.uuid4().hex}',
                email='',
            )
            django_user.set_unusable_password()
            django_user.save()
            profile = UserProfile.objects.create(
                user=django_user,
                display_name=display_name,
                is_guest=True,
                onboarding_role=onboarding_role,
                consent_accepted_at=timezone.now(),
                consent_policy_version=policy_version,
            )

        logger.info('Guest account created: user=%s', profile.pk)
        return Response(_make_token_response(profile), status=status.HTTP_200_OK)


class GuestPromoteView(APIView):
    """POST /api/v1/auth/promote/

    Promotes a guest user to a verified user via Google OAuth.
    Requires: Authorization: Bearer <guest_jwt>
    Body: {provider: 'google', code: '<auth_code>'}

    Branch 1 (cross-device collision): existing verified user with the same
      Google identity found → merge all FK tables → delete guest → return
      target user JWT.
    Branch 2 (normal in-place transform): no collision → upgrade the same
      user row in-place → return fresh JWT with is_guest=False.
    """
    permission_classes = [IsAuthenticated]
    throttle_classes = [GuestPromoteThrottle]

    def post(self, request):
        guest_user = request.user

        # Re-check is_guest inside the view as replay protection.
        # DRF auth already validated the JWT signature; this guard ensures
        # a verified user's token can't be replayed here.
        try:
            guest_profile = guest_user.profile
        except UserProfile.DoesNotExist:
            return Response({'detail': 'profile_not_found'}, status=status.HTTP_400_BAD_REQUEST)

        if not guest_profile.is_guest:
            return Response({'detail': 'not_a_guest'}, status=status.HTTP_400_BAD_REQUEST)

        provider = request.data.get('provider', 'google')
        if provider != 'google':
            return Response(
                {'detail': 'unsupported_provider', 'supported': ['google']},
                status=status.HTTP_400_BAD_REQUEST,
            )

        code = request.data.get('code')
        if not code:
            return Response({'detail': 'code required'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            google_data = _exchange_google_code(code)
        except ValueError as exc:
            logger.warning('GuestPromoteView google exchange failed: %s', exc)
            return Response({'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        with transaction.atomic():
            # Branch detection: look for existing verified user with this Google identity
            existing_social = SocialAccount.objects.filter(
                provider='google',
                provider_id=google_data['provider_id'],
            ).select_related('user__user').first()

            existing_by_email = None
            if google_data['email']:
                existing_by_email = (
                    UserProfile.objects.filter(user__email=google_data['email'])
                    .exclude(pk=guest_profile.pk)
                    .select_related('user')
                    .first()
                )

            target_profile = (
                existing_social.user if existing_social else existing_by_email
            )

            if target_profile:
                # Branch 1 — cross-device collision: merge guest data into existing user.
                # Handles Follow dedup, ArchitectFollow (was missing), Reaction dedup,
                # liked_building_ids union, and counter-cache recompute — all inside
                # a nested atomic savepoint inside the outer transaction.atomic().
                from ..merge import merge_guest_into_target
                merge_guest_into_target(guest_profile, target_profile)

                # Ensure target has the Google SocialAccount — may be absent when
                # target was found by email-match only (no prior Google sign-in).
                SocialAccount.objects.get_or_create(
                    provider='google',
                    provider_id=google_data['provider_id'],
                    defaults={'user': target_profile},
                )

                # Blacklist all outstanding tokens for the guest user so the old
                # access token becomes unusable after this request completes.
                # Requires token_blacklist in INSTALLED_APPS (auto-creates
                # OutstandingToken rows via RefreshToken.for_user()).
                from rest_framework_simplejwt.token_blacklist.models import (
                    OutstandingToken, BlacklistedToken,
                )
                for ot in OutstandingToken.objects.filter(user=guest_user):
                    BlacklistedToken.objects.get_or_create(token=ot)

                invalidate_user_cache(guest_user.id)
                guest_profile.delete()
                guest_user.delete()
                merged_profile = target_profile

            else:
                # Branch 2 — in-place transform (most common case, single device).
                new_username = google_data['email']
                if User.objects.filter(username=new_username).exclude(pk=guest_user.pk).exists():
                    # Deterministic fallback — provider_id is collision-free
                    new_username = f"google_{google_data['provider_id']}"
                guest_user.username = new_username
                guest_user.email = google_data['email']
                guest_user.save(update_fields=['username', 'email'])

                guest_profile.is_guest = False
                guest_profile.display_name = (
                    guest_profile.display_name or google_data['display_name']
                )
                guest_profile.avatar_url = google_data.get('avatar_url', '') or guest_profile.avatar_url
                guest_profile.save(update_fields=['is_guest', 'display_name', 'avatar_url'])

                SocialAccount.objects.get_or_create(
                    provider='google',
                    provider_id=google_data['provider_id'],
                    defaults={'user': guest_profile},
                )

                # Blacklist old guest refresh tokens — they carry stale is_guest=True claim
                from rest_framework_simplejwt.token_blacklist.models import (
                    OutstandingToken, BlacklistedToken,
                )
                for outstanding in OutstandingToken.objects.filter(user=guest_user):
                    BlacklistedToken.objects.get_or_create(token=outstanding)

                invalidate_user_cache(guest_user.id)
                merged_profile = guest_profile

        # Issue fresh JWT pair for the merged/promoted user.
        refresh = RefreshToken.for_user(merged_profile.user)
        refresh['is_guest'] = merged_profile.is_guest  # set on refresh BEFORE access_token

        logger.info(
            'GuestPromoteView: promoted user=%s (branch=%s)',
            merged_profile.pk,
            'merge' if target_profile else 'in_place',
        )
        return Response({
            'access':   str(refresh.access_token),
            'refresh':  str(refresh),
            'user':     UserSerializer(merged_profile).data,
            'promoted': True,
            'merged':   bool(target_profile),
        })


# -- Google ----------------------------------------------------------------

class GoogleLoginView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []  # Don't validate existing tokens on login endpoints

    def post(self, request):
        access_token = request.data.get('access_token')
        code = request.data.get('code')

        # Auth-code flow: exchange code for access_token
        if code and not access_token:
            try:
                token_resp = requests.post(
                    'https://oauth2.googleapis.com/token',
                    data={
                        'code': code,
                        'client_id': settings.GOOGLE_CLIENT_ID,
                        'client_secret': settings.GOOGLE_CLIENT_SECRET,
                        'redirect_uri': 'postmessage',
                        'grant_type': 'authorization_code',
                    },
                    timeout=10,
                )
                if token_resp.status_code != 200:
                    logger.warning(
                        'Google token exchange failed: status=%d body=%s',
                        token_resp.status_code, token_resp.text[:300],
                    )
                    detail = 'Google token exchange failed'
                    if settings.DEBUG:
                        detail += f' (status={token_resp.status_code})'
                    return Response({'detail': detail}, status=status.HTTP_401_UNAUTHORIZED)
                token_data = token_resp.json()
                access_token = token_data.get('access_token')
                if not access_token:
                    logger.warning('Google token exchange returned no access_token: %s', token_data)
                    return Response(
                        {'detail': 'Google token exchange returned no access_token'},
                        status=status.HTTP_401_UNAUTHORIZED,
                    )
            except requests.RequestException as e:
                logger.error('Google token exchange network error: %s', e)
                return Response(
                    {'detail': 'Google token exchange network error'},
                    status=status.HTTP_502_BAD_GATEWAY,
                )

        if not access_token:
            return Response(
                {'detail': 'access_token or code required'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        resp = requests.get(
            'https://www.googleapis.com/oauth2/v3/userinfo',
            headers={'Authorization': f'Bearer {access_token}'},
            timeout=10,
        )
        if resp.status_code != 200:
            logger.warning(
                'Google userinfo failed: status=%d body=%s',
                resp.status_code, resp.text[:300],
            )
            detail = 'Failed to validate Google token'
            if settings.DEBUG:
                detail += f' (userinfo returned {resp.status_code})'
            return Response({'detail': detail}, status=status.HTTP_401_UNAUTHORIZED)

        info = resp.json()
        profile = _get_or_create_user(
            provider='google',
            provider_id=info['sub'],
            email=info.get('email'),
            display_name=info.get('name'),
            avatar_url=info.get('picture'),
        )
        logger.info('Google login: user=%s', profile.pk)
        return Response(_make_token_response(profile))


# -- Kakao -----------------------------------------------------------------

class KakaoLoginView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []  # Don't validate existing tokens on login endpoints

    def post(self, request):
        access_token = request.data.get('access_token')
        if not access_token:
            return Response({'detail': 'access_token required'}, status=status.HTTP_400_BAD_REQUEST)

        resp = requests.get(
            'https://kapi.kakao.com/v2/user/me',
            headers={'Authorization': f'Bearer {access_token}'},
            timeout=10,
        )
        if resp.status_code != 200:
            return Response({'detail': 'Invalid Kakao token'}, status=status.HTTP_401_UNAUTHORIZED)

        info   = resp.json()
        if not info.get('id'):
            return Response({'detail': 'Invalid Kakao response'}, status=status.HTTP_401_UNAUTHORIZED)
        kakao_id = str(info['id'])
        kakao_account = info.get('kakao_account', {})
        profile = _get_or_create_user(
            provider='kakao',
            provider_id=kakao_id,
            email=kakao_account.get('email'),
            display_name=kakao_account.get('profile', {}).get('nickname'),
            avatar_url=kakao_account.get('profile', {}).get('profile_image_url'),
        )
        logger.info('Kakao login: user=%s', profile.pk)
        return Response(_make_token_response(profile))


# -- Naver -----------------------------------------------------------------

class NaverLoginView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []  # Don't validate existing tokens on login endpoints

    def post(self, request):
        access_token = request.data.get('access_token')
        if not access_token:
            return Response({'detail': 'access_token required'}, status=status.HTTP_400_BAD_REQUEST)

        resp = requests.get(
            'https://openapi.naver.com/v1/nid/me',
            headers={'Authorization': f'Bearer {access_token}'},
            timeout=10,
        )
        if resp.status_code != 200:
            return Response({'detail': 'Invalid Naver token'}, status=status.HTTP_401_UNAUTHORIZED)

        info = resp.json().get('response', {})
        if not info.get('id'):
            return Response({'detail': 'Invalid Naver response'}, status=status.HTTP_401_UNAUTHORIZED)
        profile = _get_or_create_user(
            provider='naver',
            provider_id=info['id'],
            email=info.get('email'),
            display_name=info.get('name') or info.get('nickname'),
            avatar_url=info.get('profile_image'),
        )
        logger.info('Naver login: user=%s', profile.pk)
        return Response(_make_token_response(profile))


# -- Dev Login (automated testing only) ------------------------------------

class DevLoginView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []  # Don't validate existing tokens on login endpoints
    throttle_classes = [DevLoginThrottle]

    def post(self, request):
        secret = os.getenv('DEV_LOGIN_SECRET', '')
        if not secret:
            return Response(status=status.HTTP_404_NOT_FOUND)
        if request.data.get('secret') != secret:
            return Response({'detail': 'Invalid secret'}, status=status.HTTP_403_FORBIDDEN)

        user, _ = User.objects.get_or_create(
            email='test@architinder.dev',
            defaults={'username': 'test_architinder', 'first_name': 'Test User'},
        )
        profile, _ = UserProfile.objects.get_or_create(
            user=user, defaults={'display_name': 'Test User'},
        )
        return Response(_make_token_response(profile), status=status.HTTP_200_OK)


# -- Token refresh ---------------------------------------------------------

class TokenRefreshView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []  # Don't validate existing tokens on token refresh

    def post(self, request):
        refresh_token = request.data.get('refresh')
        if not refresh_token:
            return Response({'detail': 'refresh required'}, status=status.HTTP_400_BAD_REQUEST)
        try:
            refresh = RefreshToken(refresh_token)
            data = {'access': str(refresh.access_token)}
            user_id_from_refresh = refresh.get(api_settings.USER_ID_CLAIM)
            if settings.SIMPLE_JWT.get('ROTATE_REFRESH_TOKENS'):
                if settings.SIMPLE_JWT.get('BLACKLIST_AFTER_ROTATION'):
                    try:
                        refresh.blacklist()
                        if user_id_from_refresh is not None:
                            invalidate_user_cache(user_id_from_refresh)
                    except AttributeError:
                        # token_blacklist app not installed (dev mode without migrations)
                        pass
                refresh.set_jti()
                refresh.set_exp()
                refresh.set_iat()
                data['refresh'] = str(refresh)
            return Response(data)
        except TokenError:
            return Response({'detail': 'Invalid or expired token'}, status=status.HTTP_401_UNAUTHORIZED)


# -- Me --------------------------------------------------------------------

class MeView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        profile = getattr(request.user, 'profile', None)
        if not profile:
            return Response({'detail': 'Profile not found'}, status=status.HTTP_404_NOT_FOUND)
        return Response(UserSerializer(profile).data)


# -- Logout ----------------------------------------------------------------

class LogoutView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        refresh_token = request.data.get('refresh')
        if refresh_token:
            try:
                RefreshToken(refresh_token).blacklist()
            except Exception:
                pass
        # Evict the user cache. The access token still has its natural exp
        # but cache eviction forces the next authenticated request to re-fetch
        # User state from DB — picks up any out-of-band is_active/password change.
        if request.user and request.user.is_authenticated:
            invalidate_user_cache(request.user.id)
        return Response(status=status.HTTP_204_NO_CONTENT)
