import logging
import os
import requests
from django.contrib.auth.models import User
from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import AnonRateThrottle
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken
from django.conf import settings

from .models import UserProfile, SocialAccount
from .serializers import UserSerializer, UserProfileSerializer, UserProfileSelfUpdateSerializer

logger = logging.getLogger('apps.accounts')


class DevLoginThrottle(AnonRateThrottle):
    rate = '5/minute'


def _get_or_create_user(provider, provider_id, email, display_name, avatar_url):
    """Find or create a UserProfile, linking by email for account merging."""
    social = SocialAccount.objects.filter(provider=provider, provider_id=provider_id).first()
    if social:
        return social.user

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
        # Update display name / avatar if blank
        if not profile.display_name and display_name:
            profile.display_name = display_name
            profile.save(update_fields=['display_name'])

    SocialAccount.objects.get_or_create(
        provider=provider,
        provider_id=provider_id,
        defaults={'user': profile},
    )
    return profile


def _make_token_response(profile):
    refresh = RefreshToken.for_user(profile.user)
    return {
        'access':  str(refresh.access_token),
        'refresh': str(refresh),
        'user':    UserSerializer(profile).data,
    }


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
            if settings.SIMPLE_JWT.get('ROTATE_REFRESH_TOKENS'):
                refresh.set_jti()
                refresh.set_exp()
                refresh.set_iat()
                data['refresh'] = str(refresh)
            return Response(data)
        except Exception:
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
        return Response(status=status.HTTP_204_NO_CONTENT)


# -- User Profile (Phase 13 PROF2 + BOARD1) --------------------------------

def _build_boards_field(target_profile, is_owner):
    """Build boards[] list for UserProfileDetailView response.

    Each card contains: project_id, name, date (created_at), visibility,
    building_count, cover_image_url, thumbnails (up to 6).

    Cover derivation: first liked_ids building → first saved_ids building → ''.
    Batches all image lookups in a single DB query to avoid N+1.
    """
    from apps.recommendation.models import Project
    from apps.recommendation import engine

    qs = Project.objects.filter(user=target_profile).order_by('-created_at')
    if not is_owner:
        qs = qs.filter(visibility='public')

    projects = list(qs)
    if not projects:
        return []

    # Collect all building_ids needed for image resolution (cover + thumbnails).
    # Per project: take first 6 unique ids from liked_ids + saved_ids combined.
    def _extract_ids(project):
        liked = [
            (entry if isinstance(entry, str) else entry.get('id', ''))
            for entry in (project.liked_ids or [])
        ]
        saved = [
            (entry if isinstance(entry, str) else entry.get('id', ''))
            for entry in (project.saved_ids or [])
        ]
        # De-dup while preserving order; take first 7 to have cover + 6 thumbs
        seen, result = set(), []
        for bid in liked + saved:
            if bid and bid not in seen:
                seen.add(bid)
                result.append(bid)
                if len(result) == 7:
                    break
        return result

    project_bid_lists = {p.project_id: _extract_ids(p) for p in projects}
    all_bids = list({bid for bids in project_bid_lists.values() for bid in bids})

    # Single batch query for all building images
    image_map = {}  # building_id → image_url
    if all_bids:
        cards = engine.get_buildings_by_ids(all_bids)
        image_map = {c['building_id']: c.get('image_url', '') for c in cards}

    boards = []
    for p in projects:
        bids = project_bid_lists[p.project_id]
        cover_url = next((image_map.get(bid, '') for bid in bids if image_map.get(bid)), '')
        thumbnails = [image_map[bid] for bid in bids if image_map.get(bid)][:6]
        building_count = (
            len(p.liked_ids or []) + len(p.saved_ids or [])
        )
        boards.append({
            'project_id':     str(p.project_id),
            'name':           p.name,
            'date':           p.created_at.isoformat(),
            'visibility':     p.visibility,
            'building_count': building_count,
            'cover_image_url': cover_url,
            'thumbnails':     thumbnails,
        })
    return boards


class UserProfileDetailView(APIView):
    """GET /api/v1/users/{user_id}/ — public UserProfile detail.

    Per spec §1.3: profile data is public-readable. Privacy of individual fields
    (e.g. email visibility) is a UI presentation concern, NOT API gating, in v0.

    boards[] — BOARD1: non-owner sees public projects only; owner sees all.
    is_following — SOC1 territory (Phase 15), excluded here.
    """
    permission_classes = [AllowAny]

    def get(self, request, user_id):
        profile = get_object_or_404(UserProfile, user__id=user_id)
        requester_profile = getattr(request.user, 'profile', None) if request.user.is_authenticated else None
        is_owner = requester_profile and requester_profile.pk == profile.pk
        data = UserProfileSerializer(profile).data
        data['boards'] = _build_boards_field(profile, is_owner)
        return Response(data)


class UserProfileSelfUpdateView(APIView):
    """PATCH /api/v1/users/me/ — owner updates own UserProfile editable fields.

    Returns the full UserProfileSerializer shape for consistency with GET.
    """
    permission_classes = [IsAuthenticated]

    def patch(self, request):
        try:
            profile = request.user.profile
        except UserProfile.DoesNotExist:
            return Response(
                {'detail': 'UserProfile not found for current user.'},
                status=status.HTTP_404_NOT_FOUND,
            )
        serializer = UserProfileSelfUpdateSerializer(profile, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        # Return full UserProfileSerializer shape (consistent with GET)
        return Response(UserProfileSerializer(profile).data)
