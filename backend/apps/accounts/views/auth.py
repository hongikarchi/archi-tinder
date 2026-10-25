import logging
import os
import unicodedata
import uuid as _uuid
import requests
from django.contrib.auth.models import User
from django.db import IntegrityError, transaction
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

from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError

from ..authentication import invalidate_user_cache
from ..identity import ensure_unified_identity, suggest_handle as _suggest_handle
from ..models import UserProfile, SocialAccount
from ..serializers import (
    UserSerializer, validate_handle_value,
)
from rest_framework.exceptions import ValidationError as DRFValidationError
from ..throttling import (
    GuestLoginThrottle, GuestPromoteThrottle,
    RegisterThrottle, PasswordLoginThrottle, LinkEmailThrottle,
    SetPasswordThrottle, CheckHandleThrottle,
)
from apps.notifications.services import notify_security, record_device_and_maybe_notify

logger = logging.getLogger('apps.accounts')

# ---------------------------------------------------------------------------
# SECURITY: OAuth email-verified policy (account-takeover mitigation)
# ---------------------------------------------------------------------------
# Every social provider can return an email address that may or may not belong
# to the authenticating user.  Linking (or storing) an UNVERIFIED provider
# email onto an existing account is an account-takeover vector:
#
#   Attacker creates a provider account with email=victim@example.com
#   (unverified) → without this guard, our link-by-email branch would
#   silently attach their social credential to the victim's profile.
#
# Policy enforced by _get_or_create_user(email_verified=...):
#   - email-match linking: ONLY when email_verified=True
#   - new account creation: email stored ONLY when email_verified=True
#     (unverified address stored → reverse-takeover: a later verified login
#      for that address matches the attacker's account)
#
# Per-provider status:
#   Google → `email_verified` boolean in /oauth2/v3/userinfo (reliable)
#   Kakao  → `kakao_account.is_email_verified` (may be absent → default False)
#   Naver  → no verified field in /nid/me → always False (conservative)
# ---------------------------------------------------------------------------

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


def _clean_guest_optional_text(value, max_length):
    """Trim and truncate an optional free-text field; fall back to '' when absent/invalid.

    Used for role + affiliation at guest signup — truncates rather than rejects
    so an over-long value never raises a DB error (DataError / 500).
    """
    if not isinstance(value, str):
        return ''
    return value.strip()[:max_length]


def _exchange_google_code(code):
    """Exchange Google auth code for user info dict.

    Returns dict with keys: provider_id, email, display_name, avatar_url,
    email_verified.

    SECURITY: email_verified is included so callers can gate account-linking
    on provider-confirmed identity.  Never link/store an unverified email
    onto an existing account — that is the account-takeover vector.

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
        'provider_id':    info['sub'],
        'email':          info.get('email', ''),
        'display_name':   info.get('name', ''),
        'avatar_url':     info.get('picture', ''),
        # SECURITY: must be True before linking/storing email on an account.
        'email_verified': bool(info.get('email_verified', False)),
    }


class DevLoginThrottle(AnonRateThrottle):
    rate = '5/minute'


def _create_social_user(provider, provider_id, email, display_name, avatar_url,
                        email_verified):
    handle = _suggest_handle(display_name)
    with transaction.atomic():
        user = User(
            username=f'social_{_uuid.uuid4().hex[:20]}',
            email=email if (email and email_verified) else '',
        )
        user.set_unusable_password()
        user.save()
        profile = UserProfile.objects.create(
            user=user,
            handle=handle,
            display_name=handle,
            is_guest=False,
            avatar_url=avatar_url or '',
            consent_accepted_at=None,
        )
        SocialAccount.objects.create(
            provider=provider, provider_id=provider_id, user=profile,
        )
    return profile


def _get_or_create_user(provider, provider_id, email, display_name, avatar_url,
                        email_verified=False):
    """Find, link, or CREATE the UserProfile for a social login (never None).

    Social-only signup: the first social login creates the account
    (consent_accepted_at=None -> frontend must call POST /auth/onboarding/).

    SECURITY (account-takeover mitigation):
      email_verified must be True before we allow an email-address match to
      link a new social credential into an existing account, and before the
      email is stored on a newly created account.

    Branch (i)  - existing SocialAccount: always safe.
    Branch (ii) - email match: runs ONLY when email AND email_verified=True.
    Branch (iii)- create new user + profile + SocialAccount (atomic; one retry
                  with a fresh handle suggestion on IntegrityError).
    """
    # (i) pre-check: existing social credential -> return immediately (safe)
    social = SocialAccount.objects.filter(provider=provider, provider_id=provider_id).first()
    if social:
        profile = social.user
        # display_name is the user-owned unified ID (== handle): never overwrite.
        # avatar_url is provider-managed and safe to sync.
        if avatar_url:
            profile.avatar_url = avatar_url
            profile.save(update_fields=['avatar_url'])
        return profile

    # (ii) email-match account linking - ONLY when provider confirms email ownership
    profile = None
    if email and email_verified:
        existing_user = User.objects.filter(email=email).first()
        if existing_user:
            profile = getattr(existing_user, 'profile', None)

    if profile is not None:
        if avatar_url:
            profile.avatar_url = avatar_url
            profile.save(update_fields=['avatar_url'])
        SocialAccount.objects.get_or_create(
            provider=provider,
            provider_id=provider_id,
            defaults={'user': profile},
        )
        return profile

    # (iii) create
    try:
        return _create_social_user(
            provider, provider_id, email, display_name, avatar_url, email_verified,
        )
    except IntegrityError:
        # Handle race (or concurrent same-provider signup): retry once.
        social = SocialAccount.objects.filter(
            provider=provider, provider_id=provider_id,
        ).first()
        if social:
            return social.user
        return _create_social_user(
            provider, provider_id, email, display_name, avatar_url, email_verified,
        )


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
           consent_policy_version: '1.0',
           role (optional, free-text, max 50 chars — truncated if longer),
           affiliation (optional, free-text, max 100 chars — truncated if longer)}

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

        role = _clean_guest_optional_text(request.data.get('role', ''), 50)
        affiliation = _clean_guest_optional_text(request.data.get('affiliation', ''), 100)

        def _create_guest():
            with transaction.atomic():
                django_user = User(
                    username=f'guest_{_uuid.uuid4().hex}',
                    email='',
                )
                django_user.set_unusable_password()
                django_user.save()
                # Unified ID: display_name == handle. The free-text name only
                # seeds the suggested handle.
                handle = _suggest_handle(display_name)
                return UserProfile.objects.create(
                    user=django_user,
                    display_name=handle,
                    handle=handle,
                    is_guest=True,
                    onboarding_role=onboarding_role,
                    consent_accepted_at=timezone.now(),
                    consent_policy_version=policy_version,
                    role=role,
                    affiliation=affiliation,
                )

        try:
            profile = _create_guest()
        except IntegrityError:
            # Handle race (check-then-insert): retry once with a fresh suggestion.
            profile = _create_guest()

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
            # SECURITY: only look up an existing account by email when Google
            # confirms the email is verified.  An unverified email matching a
            # victim's address must NOT trigger a merge.
            if google_data['email'] and google_data.get('email_verified', False):
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
                # SECURITY: only store/use the Google email when verified.
                # Unverified email → username falls back to provider_id form,
                # email stays empty — prevents reverse-takeover where a later
                # verified login for that address matches this account.
                if google_data.get('email_verified', False) and google_data['email']:
                    new_username = google_data['email']
                    if User.objects.filter(username=new_username).exclude(pk=guest_user.pk).exists():
                        # Deterministic fallback — provider_id is collision-free
                        new_username = f"google_{google_data['provider_id']}"
                    safe_email = google_data['email']
                else:
                    new_username = f"google_{google_data['provider_id']}"
                    safe_email = ''
                guest_user.username = new_username
                guest_user.email = safe_email
                guest_user.save(update_fields=['username', 'email'])

                guest_profile.is_guest = False
                # Unified ID: keep display_name == handle; assign a handle only
                # when the guest lacks one (never rename an existing handle).
                ensure_unified_identity(
                    guest_profile,
                    guest_profile.display_name or google_data['display_name'],
                )
                guest_profile.avatar_url = google_data.get('avatar_url', '') or guest_profile.avatar_url
                guest_profile.save(
                    update_fields=['is_guest', 'handle', 'display_name', 'avatar_url']
                )

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

        if code and not access_token:
            try:
                info = _exchange_google_code(code)
            except ValueError as exc:
                logger.warning('Google code exchange failed: %s', exc)
                return Response(
                    {'detail': 'Google token exchange failed'},
                    status=status.HTTP_401_UNAUTHORIZED,
                )
        elif access_token:
            try:
                resp = requests.get(
                    'https://www.googleapis.com/oauth2/v3/userinfo',
                    headers={'Authorization': f'Bearer {access_token}'},
                    timeout=10,
                )
            except requests.RequestException as exc:
                logger.error('Google userinfo network error: %s', exc)
                return Response(
                    {'detail': 'Google network error'},
                    status=status.HTTP_502_BAD_GATEWAY,
                )
            if resp.status_code != 200:
                logger.warning('Google userinfo failed: status=%d', resp.status_code)
                return Response(
                    {'detail': 'Failed to validate Google token'},
                    status=status.HTTP_401_UNAUTHORIZED,
                )
            raw = resp.json()
            info = {
                'provider_id':    raw['sub'],
                'email':          raw.get('email', ''),
                'display_name':   raw.get('name', ''),
                'avatar_url':     raw.get('picture', ''),
                'email_verified': bool(raw.get('email_verified', False)),
            }
        else:
            return Response(
                {'detail': 'access_token or code required'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # SECURITY: email_verified gates email linking / storage.
        profile = _get_or_create_user(
            provider='google',
            provider_id=info['provider_id'],
            email=info.get('email'),
            display_name=info.get('display_name'),
            avatar_url=info.get('avatar_url'),
            email_verified=bool(info.get('email_verified', False)),
        )
        logger.info('Google login: user=%s', profile.pk)

        # NOTIF-INAPP-1: new-device login detection (mirrors PasswordLoginView).
        try:
            record_device_and_maybe_notify(profile, request.META.get('HTTP_USER_AGENT', ''))
        except Exception:
            logger.exception('record_device_and_maybe_notify failed profile=%s', profile.pk)

        return Response(_make_token_response(profile))


# -- Kakao -----------------------------------------------------------------

def _exchange_kakao_code(code, redirect_uri):
    """Exchange a Kakao auth code for user info dict (module-level for monkeypatching).

    Returns {provider_id, email, email_verified, display_name, avatar_url}.
    Raises ValueError on any failure. Never logs tokens/secrets.
    """
    data = {
        'grant_type': 'authorization_code',
        'client_id': settings.KAKAO_CLIENT_ID,
        'redirect_uri': redirect_uri,
        'code': code,
    }
    if settings.KAKAO_CLIENT_SECRET:
        data['client_secret'] = settings.KAKAO_CLIENT_SECRET
    try:
        token_resp = requests.post(
            'https://kauth.kakao.com/oauth/token', data=data, timeout=10,
        )
    except requests.RequestException as exc:
        raise ValueError('Kakao token exchange network error') from exc
    if token_resp.status_code != 200:
        raise ValueError(f'Kakao token exchange failed: status={token_resp.status_code}')
    try:
        access_token = token_resp.json().get('access_token')
    except ValueError as exc:
        raise ValueError('Kakao token exchange returned invalid JSON') from exc
    if not access_token:
        raise ValueError('Kakao token exchange returned no access_token')

    try:
        me_resp = requests.get(
            'https://kapi.kakao.com/v2/user/me',
            headers={'Authorization': f'Bearer {access_token}'},
            timeout=10,
        )
    except requests.RequestException as exc:
        raise ValueError('Kakao user/me network error') from exc
    if me_resp.status_code != 200:
        raise ValueError(f'Kakao user/me failed: status={me_resp.status_code}')
    try:
        info = me_resp.json()
    except ValueError as exc:
        raise ValueError('Kakao user/me returned invalid JSON') from exc
    if not info.get('id'):
        raise ValueError('Kakao user/me returned no id')
    account = info.get('kakao_account') or {}
    profile = account.get('profile') or {}
    props = info.get('properties') or {}
    return {
        'provider_id':    str(info['id']),
        'email':          account.get('email') or '',
        # SECURITY: default False so unverified addresses never link/store.
        'email_verified': bool(account.get('is_email_verified', False)),
        'display_name':   profile.get('nickname') or props.get('nickname') or '',
        'avatar_url':     profile.get('profile_image_url') or '',
    }


class KakaoLoginView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []  # Don't validate existing tokens on login endpoints

    def post(self, request):
        code = request.data.get('code')
        redirect_uri = request.data.get('redirect_uri')
        if not code or not isinstance(code, str):
            return Response({'detail': 'code required'}, status=status.HTTP_400_BAD_REQUEST)
        if redirect_uri not in settings.KAKAO_REDIRECT_URIS:
            return Response(
                {'detail': 'invalid_redirect_uri'}, status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            info = _exchange_kakao_code(code, redirect_uri)
        except ValueError as exc:
            logger.warning('Kakao login failed: %s', exc)
            return Response(
                {'detail': 'kakao_auth_failed'}, status=status.HTTP_401_UNAUTHORIZED,
            )
        profile = _get_or_create_user(
            provider='kakao',
            provider_id=info['provider_id'],
            email=info.get('email'),
            display_name=info.get('display_name'),
            avatar_url=info.get('avatar_url'),
            email_verified=bool(info.get('email_verified', False)),
        )
        logger.info('Kakao login: user=%s', profile.pk)
        try:
            record_device_and_maybe_notify(profile, request.META.get('HTTP_USER_AGENT', ''))
        except Exception:
            logger.exception('record_device_and_maybe_notify failed profile=%s', profile.pk)
        return Response(_make_token_response(profile))


# -- Onboarding (post social signup) ---------------------------------------

class OnboardingView(APIView):
    """POST /api/v1/auth/onboarding/ - complete profile after first social login."""
    permission_classes = [IsAuthenticated]

    def post(self, request):
        profile = getattr(request.user, 'profile', None)
        if profile is None:
            return Response({'detail': 'Profile not found'}, status=status.HTTP_404_NOT_FOUND)
        if profile.consent_accepted_at is not None:
            return Response({'detail': 'already_onboarded'}, status=status.HTTP_409_CONFLICT)
        data = request.data
        if data.get('consent_accepted') is not True:
            return Response({'detail': 'consent_required'}, status=status.HTTP_400_BAD_REQUEST)
        role = data.get('onboarding_role')
        if role not in VALID_ONBOARDING_ROLES:
            return Response({'detail': 'role_invalid'}, status=status.HTTP_400_BAD_REQUEST)
        handle = data.get('handle')
        if not isinstance(handle, str):
            return Response(
                {'detail': 'handle_invalid', 'message': 'ID is required.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            validated = validate_handle_value(handle.strip(), instance=profile)
        except DRFValidationError as exc:
            detail = exc.detail
            msg = ' '.join(str(m) for m in detail) if isinstance(detail, list) else str(detail)
            return Response(
                {'detail': 'handle_invalid', 'message': msg},
                status=status.HTTP_400_BAD_REQUEST,
            )
        policy_version = data.get('consent_policy_version', '1.0')
        if not isinstance(policy_version, str) or not policy_version or len(policy_version) > 10:
            policy_version = '1.0'

        profile.handle = validated
        profile.display_name = validated
        profile.affiliation = _clean_guest_optional_text(data.get('affiliation'), 100)
        profile.onboarding_role = role
        profile.consent_accepted_at = timezone.now()
        profile.consent_policy_version = policy_version
        try:
            with transaction.atomic():
                profile.save()
        except IntegrityError:
            return Response(
                {'detail': 'handle_invalid', 'message': 'ID already taken.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        invalidate_user_cache(request.user.id)
        return Response(UserSerializer(profile).data)


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
        # SECURITY: Naver's /nid/me API exposes no email-verified field.
        # We conservatively treat ALL Naver emails as unverified (email_verified=False)
        # so they never trigger account-linking.  The email is also not stored on
        # the new account to prevent the reverse-takeover vector.
        profile = _get_or_create_user(
            provider='naver',
            provider_id=info['id'],
            email=info.get('email'),
            display_name=info.get('name') or info.get('nickname'),
            avatar_url=info.get('profile_image'),
            email_verified=False,
        )
        # LOGIN-ONBOARD-1: social login no longer creates accounts.
        if profile is None:
            return Response(
                {'detail': 'signup_required', 'reason': 'no_account'},
                status=status.HTTP_404_NOT_FOUND,
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

        # Keyed on username (unique), not email: linking Google on the test
        # account rewrites its email, and an email lookup then misses and
        # re-creates the username -> IntegrityError 500.
        user, _ = User.objects.get_or_create(
            username='test_architinder',
            defaults={'email': 'test@architinder.dev'},
        )
        profile, created = UserProfile.objects.get_or_create(
            user=user, defaults={'display_name': 'TestUser'},
        )
        # Unified ID: display_name == handle. Assign a handle only when missing
        # (never rename an existing one), then keep display_name in sync.
        ensure_unified_identity(profile, 'TestUser')
        profile.save(update_fields=['handle', 'display_name'])
        return Response(_make_token_response(profile), status=status.HTTP_200_OK)


# -- Handle + Password Auth (AUTH-LOGIN-1) ---------------------------------

class RegisterView(APIView):
    """POST /api/v1/auth/register/

    Create a new id+password account (the primary signup path).

    LOGIN-ONBOARD-1: unified ID strategy. The `id` field is the single
    user-facing ID (= display name = login id = @handle). Both UserProfile.handle
    and UserProfile.display_name are set to the NFC-normalized validated id.
    is_guest=True on creation (unverified account; flips to False on Google link).

    Body: {id, password, affiliation? (optional), onboarding_role, consent_accepted: true}
    Returns {access, refresh, user} on success.

    Security:
    - id validated by shared validate_handle_value (Hangul + ASCII, 2-20 chars).
    - password validated by Django AUTH_PASSWORD_VALIDATORS.
    - consent_accepted must be boolean true (PIPA requirement).
    - User.username = stable internal key f'local_{uuid4().hex}' (NOT the id,
      since handle is editable and must not be coupled to the auth key).
    - Wrapped in transaction.atomic() — handle uniqueness race condition is
      prevented by DB unique constraint on UserProfile.handle.
    """
    permission_classes    = [AllowAny]
    authentication_classes = []
    throttle_classes       = [RegisterThrottle]

    def post(self, request):
        # -- PIPA consent gate --
        if request.data.get('consent_accepted') is not True:
            return Response(
                {'detail': 'consent_required',
                 'reason': 'PIPA consent must be explicitly accepted'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Accept both 'id' (new) and 'handle' (legacy) as the ID field.
        # Strip leading/trailing whitespace so check-handle and register agree
        # on whitespace handling (CheckHandleView also strips before validation).
        id_value = (request.data.get('id') or request.data.get('handle', '')).strip()
        password = request.data.get('password', '')
        affiliation = request.data.get('affiliation', '')
        onboarding_role = request.data.get('onboarding_role', '')

        # -- Validate id --
        if not id_value:
            return Response({'id': ['This field is required.']},
                            status=status.HTTP_400_BAD_REQUEST)
        from rest_framework import serializers as _drf_serializers
        try:
            validated_id = validate_handle_value(id_value)
        except _drf_serializers.ValidationError as exc:
            return Response({'id': exc.detail},
                            status=status.HTTP_400_BAD_REQUEST)

        # -- Validate password --
        if not password:
            return Response({'password': ['This field is required.']},
                            status=status.HTTP_400_BAD_REQUEST)
        try:
            validate_password(password)
        except DjangoValidationError as exc:
            return Response({'password': list(exc.messages)},
                            status=status.HTTP_400_BAD_REQUEST)

        # -- Validate onboarding_role --
        if onboarding_role and onboarding_role not in VALID_ONBOARDING_ROLES:
            return Response(
                {'onboarding_role': ['Invalid onboarding role.']},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # -- Sanitize optional free-text fields --
        clean_affiliation = _clean_guest_optional_text(affiliation, 100)

        policy_version = request.data.get('consent_policy_version', '1.0')
        if not isinstance(policy_version, str) or len(policy_version) > 10:
            policy_version = '1.0'

        # -- Create user + profile (atomic, DB unique on handle protects races) --
        # LOGIN-ONBOARD-1: handle == display_name == NFC-normalized validated id.
        # is_guest=True (unverified; flips to False when Google email is linked).
        try:
            with transaction.atomic():
                django_user = User(
                    username=f'local_{_uuid.uuid4().hex}',
                    email='',
                )
                django_user.set_password(password)
                django_user.save()
                profile = UserProfile.objects.create(
                    user=django_user,
                    handle=validated_id,
                    display_name=validated_id,
                    is_guest=True,
                    affiliation=clean_affiliation,
                    onboarding_role=onboarding_role or '',
                    consent_accepted_at=timezone.now(),
                    consent_policy_version=policy_version,
                )
        except Exception:
            # Handle uniqueness race: another request won the unique constraint.
            if UserProfile.objects.filter(handle__iexact=validated_id).exists():
                return Response({'id': ['ID already taken.']},
                                status=status.HTTP_400_BAD_REQUEST)
            raise

        logger.info('RegisterView: new user created profile=%s', profile.pk)
        return Response(_make_token_response(profile), status=status.HTTP_201_CREATED)


class PasswordLoginView(APIView):
    """POST /api/v1/auth/login/

    Authenticate with handle + password.

    Body: {handle, password}
    Returns {access, refresh, user} on success.

    Security:
    - Generic 400 for ALL failure modes (no user enumeration via message).
    - Dummy-hash run when user not found / no usable password to equalise timing.
    - Throttled by PasswordLoginThrottle (10/min per IP, brute-force guard).
    """
    permission_classes    = [AllowAny]
    authentication_classes = []
    throttle_classes       = [PasswordLoginThrottle]

    _GENERIC_ERROR = 'Invalid handle or password.'

    def post(self, request):
        handle   = request.data.get('handle', '') or request.data.get('id', '')
        password = request.data.get('password', '')

        # LOGIN-ONBOARD-1: NFC-normalize incoming handle so Hangul IDs match
        # the stored NFC form regardless of how the client decomposed the string.
        if handle:
            handle = unicodedata.normalize('NFC', handle)

        profile  = None
        django_user = None

        if handle:
            # Use .filter().first() not .get() to avoid MultipleObjectsReturned
            # from legacy case-variant handles (new handles are unique by DB
            # constraint; this is a defensive guard for any existing stale rows).
            p = (
                UserProfile.objects
                .select_related('user')
                .filter(handle__iexact=handle)
                .first()
            )
            if p is not None:
                profile = p
                django_user = p.user

        # Timing equalisation: always run one password hash regardless of
        # lookup outcome.  This prevents timing-based user enumeration where
        # a missing-handle response is measurably faster than a wrong-password
        # response.
        if django_user is not None and django_user.has_usable_password():
            ok = django_user.check_password(password)
        else:
            # No user found, or user has no usable password (OAuth-only / guest).
            # Run a dummy hash so timing is indistinguishable from a real check.
            User().set_password(password)
            ok = False

        if not ok:
            return Response({'detail': self._GENERIC_ERROR},
                            status=status.HTTP_400_BAD_REQUEST)

        logger.info('PasswordLoginView: login profile=%s', profile.pk)

        # NOTIF-INAPP-1: new-device login detection. First-ever device is
        # recorded silently; subsequent new ua_hash notifies. Must never
        # break login on failure (wrapped inside the helper itself too).
        try:
            record_device_and_maybe_notify(profile, request.META.get('HTTP_USER_AGENT', ''))
        except Exception:
            logger.exception('record_device_and_maybe_notify failed profile=%s', profile.pk)

        return Response(_make_token_response(profile), status=status.HTTP_200_OK)


class SetPasswordView(APIView):
    """POST /api/v1/auth/set-password/

    Set or change the handle+password credential for the authenticated user.

    Body: {password, current_password? (required only when changing an existing password)}

    Rules:
    - If user ALREADY has a usable password → require correct current_password (change).
    - If user has NO usable password yet (OAuth/guest, first-set) → allow without
      current_password.
    - Validates new password with Django AUTH_PASSWORD_VALIDATORS.
    - After updating, ALL outstanding refresh tokens for the user are blacklisted
      (evicting other sessions), then a fresh token pair is issued to the acting
      client — so the password-changer stays logged in but all other devices are
      logged out.  Response shape: {access, refresh, user} (same as _make_token_response).
    """
    permission_classes  = [IsAuthenticated]
    throttle_classes    = [SetPasswordThrottle]

    def post(self, request):
        user     = request.user
        password = request.data.get('password', '')

        if not password:
            return Response({'password': ['This field is required.']},
                            status=status.HTTP_400_BAD_REQUEST)

        # Determine change vs first-set.
        if user.has_usable_password():
            # CHANGE — must verify current_password.
            current_password = request.data.get('current_password', '')
            if not current_password:
                return Response(
                    {'current_password': ['current_password is required to change an existing password.']},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            if not user.check_password(current_password):
                return Response(
                    {'current_password': ['Incorrect password.']},
                    status=status.HTTP_400_BAD_REQUEST,
                )
        # FIRST-SET — no current_password required.

        # Validate new password strength.
        try:
            validate_password(password, user=user)
        except DjangoValidationError as exc:
            return Response({'password': list(exc.messages)},
                            status=status.HTTP_400_BAD_REQUEST)

        user.set_password(password)
        user.save(update_fields=['password'])

        # SECURITY (AUTH-CRITICAL): blacklist ALL outstanding refresh tokens so
        # other sessions (holding the old password's tokens) are immediately
        # invalidated.  Do this BEFORE issuing a fresh pair so the new token is
        # not swept up by the filter.  Option (b): return a fresh pair in the
        # response so the acting device stays logged in without interruption.
        try:
            from rest_framework_simplejwt.token_blacklist.models import (
                OutstandingToken, BlacklistedToken,
            )
            for outstanding in OutstandingToken.objects.filter(user=user):
                BlacklistedToken.objects.get_or_create(token=outstanding)
        except ImportError:
            pass  # token_blacklist not installed — skip silently

        # Evict user cache so the next /auth/me/ returns has_password=True
        # without waiting for TTL expiry (matches link-email pattern).
        invalidate_user_cache(user.id)
        logger.info('SetPasswordView: password updated user=%s', user.pk)

        # NOTIF-INAPP-1: password_changed always notifies — security category,
        # prefs are locked always-on. Must never break this request.
        try:
            notify_security(user.profile, 'password_changed')
        except Exception:
            logger.exception('notify_security(password_changed) failed user=%s', user.pk)

        # Issue a fresh token pair for the acting client (all other sessions are
        # now blacklisted above).  This keeps the password-changer logged in
        # while evicting every other device.
        return Response(_make_token_response(user.profile), status=status.HTTP_200_OK)


class LinkEmailView(APIView):
    """POST /api/v1/auth/link-email/

    Link a verified OAuth provider email to the authenticated user's account.

    Body: {provider: 'google', code}

    On success: sets User.email, creates SocialAccount(google), sets
    UserProfile.email_verified_at.  Returns updated UserSerializer data.

    Collision policy (REJECT, not merge):
    - SocialAccount(google, provider_id) on a DIFFERENT user → 400 email_already_linked.
    - DIFFERENT UserProfile with user.email__iexact == email → 400 email_already_linked.
    - Re-linking own already-linked Google account is idempotent (self-excluded).
    - email_verified=False from provider → 400 unverified_email.

    Only Google is supported for now.
    """
    permission_classes = [IsAuthenticated]
    throttle_classes   = [LinkEmailThrottle]

    def post(self, request):
        provider = request.data.get('provider', 'google')
        if provider != 'google':
            return Response(
                {'detail': 'unsupported_provider', 'supported': ['google']},
                status=status.HTTP_400_BAD_REQUEST,
            )

        code = request.data.get('code')
        if not code:
            return Response({'detail': 'code required'},
                            status=status.HTTP_400_BAD_REQUEST)

        try:
            google_data = _exchange_google_code(code)
        except ValueError as exc:
            logger.warning('LinkEmailView google exchange failed: %s', exc)
            return Response({'detail': str(exc)},
                            status=status.HTTP_400_BAD_REQUEST)

        if not google_data.get('email_verified', False):
            return Response({'detail': 'unverified_email'},
                            status=status.HTTP_400_BAD_REQUEST)

        email       = google_data['email']
        provider_id = google_data['provider_id']

        # guard: verified but empty email (should not happen with Google, but be safe)
        if not email:
            return Response({'detail': 'unverified_email'},
                            status=status.HTTP_400_BAD_REQUEST)

        try:
            profile = request.user.profile
        except UserProfile.DoesNotExist:
            return Response({'detail': 'profile_not_found'},
                            status=status.HTTP_400_BAD_REQUEST)

        with transaction.atomic():
            # Collision check 1: provider_id already on a DIFFERENT user.
            existing_social = SocialAccount.objects.filter(
                provider='google',
                provider_id=provider_id,
            ).exclude(user=profile).first()
            if existing_social:
                return Response({'detail': 'email_already_linked'},
                                status=status.HTTP_400_BAD_REQUEST)

            # Collision check 2: email already on a DIFFERENT user row.
            existing_email = (
                UserProfile.objects.filter(user__email__iexact=email)
                .exclude(pk=profile.pk)
                .exists()
            )
            if existing_email:
                return Response({'detail': 'email_already_linked'},
                                status=status.HTTP_400_BAD_REQUEST)

            # All clear — link the account.
            user = request.user
            user.email = email
            user.save(update_fields=['email'])

            SocialAccount.objects.get_or_create(
                provider='google',
                provider_id=provider_id,
                defaults={'user': profile},
            )

            profile.email_verified_at = timezone.now()
            # LOGIN-ONBOARD-1: linking a verified Google email = verification.
            # Flip is_guest=False so the account is no longer subject to guest
            # limits (3-board cap, 50-like cap). Consistent with GuestPromoteView.
            profile.is_guest = False
            profile.save(update_fields=['email_verified_at', 'is_guest'])

        invalidate_user_cache(user.id)
        logger.info('LinkEmailView: email linked profile=%s email=%s', profile.pk, email)
        return Response(UserSerializer(profile).data, status=status.HTTP_200_OK)


# -- Check Handle (LOGIN-ONBOARD-1) ----------------------------------------

class CheckHandleView(APIView):
    """GET /api/v1/auth/check-handle/?id=<value>

    LOGIN-ONBOARD-1: real-time duplicate-check for the unified ID during signup.
    Runs the same validate_handle_value() as RegisterView so the result agrees
    with the actual register validation.

    Returns 200 always (error shape uses available=False + reason):
      {available: true, reason: null}
      {available: false, reason: "<human-readable reason>"}

    SECURITY: exposes username enumeration — rate-limited via CheckHandleThrottle
    (20/min per IP) to limit the enumeration surface.
    """
    permission_classes    = [AllowAny]
    authentication_classes = []
    throttle_classes       = [CheckHandleThrottle]

    def get(self, request):
        from rest_framework import serializers as _drf_serializers

        id_value = request.query_params.get('id', '').strip()

        if not id_value:
            return Response(
                {'available': False, 'reason': 'ID is required.'},
                status=status.HTTP_200_OK,
            )

        try:
            validate_handle_value(id_value)
        except _drf_serializers.ValidationError as exc:
            # Flatten DRF's detail (may be list or string).
            detail = exc.detail
            if isinstance(detail, list):
                reason = str(detail[0]) if detail else 'Invalid ID.'
            else:
                reason = str(detail)
            return Response(
                {'available': False, 'reason': reason},
                status=status.HTTP_200_OK,
            )

        return Response({'available': True, 'reason': None}, status=status.HTTP_200_OK)


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
        payload = dict(UserSerializer(profile).data)
        # D12: runtime feature flags — backend is the single source of truth.
        payload['features'] = {'messaging': bool(getattr(settings, 'MESSAGING_ENABLED', False))}
        return Response(payload)


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
