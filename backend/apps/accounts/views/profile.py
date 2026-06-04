import logging
import re
from django.db import connections as _dj_connections
from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from django.core.cache import cache

from ..models import UserProfile
from ..serializers import UserProfileSerializer, UserProfileSelfUpdateSerializer

logger = logging.getLogger('apps.accounts')


# -- User Profile (Phase 13 PROF2 + BOARD1) --------------------------------

def _build_boards_field(target_profile, is_owner, page=1, page_size=12):
    """Build boards pagination dict for UserProfileDetailView response.

    Returns a dict with items + pagination metadata:
      {
        "items": [...],       # list of board dicts (same shape as before)
        "page": <int>,
        "page_size": <int>,
        "total_count": <int>,
        "has_more": <bool>,
        "next_page": <int|null>,
      }

    Each board card contains: project_id, name, date (created_at), visibility,
    building_count, cover_image_url, thumbnails (up to 6).

    Cover derivation: first liked_ids building → first saved_ids building → ''.
    Image batch lookup is performed only for the paged slice to avoid N+1 at
    scale. The image_focus echo in card payloads enables frontend objectFit
    decisions.
    """
    from apps.recommendation.models import Project
    from apps.recommendation import engine

    # Clamp pagination params
    page_size = min(max(1, page_size), 50)
    page = max(1, page)

    # v3.2: discovery draft boards (name prefix 'discovery_') are now visible on
    # the profile — they are normal boards and must appear in the board list.
    qs = Project.objects.filter(user=target_profile).order_by('-created_at')
    if not is_owner:
        qs = qs.filter(visibility='public')

    total_count = qs.count()
    offset = (page - 1) * page_size
    paged_qs = qs[offset: offset + page_size]
    projects = list(paged_qs)

    has_more = offset + page_size < total_count
    next_page = page + 1 if has_more else None

    if not projects:
        return {
            'items': [],
            'page': page,
            'page_size': page_size,
            'total_count': total_count,
            'has_more': has_more,
            'next_page': next_page,
        }

    # Collect all building_ids needed for image resolution (cover + thumbnails).
    # Per project: take first 7 unique ids from liked_ids + saved_ids combined
    # (cover uses first; thumbnails use up to 6 from the rest).
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

    # Single batch query for the paged slice's buildings only.
    # Use thumbnail-only fetch (2 columns) instead of full card (17 columns)
    # to avoid transferring heavy text/JSONB fields we don't use here.
    image_map = {}  # canonical_bld_id → image_url
    if all_bids:
        thumbs = engine.get_building_thumbnails(all_bids)
        image_map = {t['canonical_bld_id']: t['image_url'] for t in thumbs}

    items = []
    for p in projects:
        bids = project_bid_lists[p.project_id]
        cover_url = next((image_map.get(bid, '') for bid in bids if image_map.get(bid)), '')
        thumbnails = [image_map[bid] for bid in bids if image_map.get(bid)][:6]
        building_count = (
            len(p.liked_ids or []) + len(p.saved_ids or [])
        )
        items.append({
            'project_id':     str(p.project_id),
            'name':           p.name,
            'date':           p.created_at.isoformat(),
            'visibility':     p.visibility,
            'building_count': building_count,
            'cover_image_url': cover_url,
            'thumbnails':     thumbnails,
        })

    return {
        'items': items,
        'page': page,
        'page_size': page_size,
        'total_count': total_count,
        'has_more': has_more,
        'next_page': next_page,
    }


class UserProfileDetailView(APIView):
    """GET /api/v1/users/{user_id}/ — public UserProfile detail.

    Per spec §1.3: profile data is public-readable. Privacy of individual fields
    (e.g. email visibility) is a UI presentation concern, NOT API gating, in v0.

    boards[] — BOARD1: non-owner sees public projects only; owner sees all.
    is_following — SOC1 (Phase 15): injected here from Follow table.
      - Unauthenticated: false
      - Own profile: false
      - Authenticated + Follow row exists: true
      - Authenticated + no Follow row: false
    """
    permission_classes = [AllowAny]

    def get(self, request, user_id):
        from apps.recommendation.caches import (
            get_user_profile_detail_cache_key,
            PROFILE_DETAIL_TTL,
        )

        profile = get_object_or_404(UserProfile, user__id=user_id)
        requester_profile = getattr(request.user, 'profile', None) if request.user.is_authenticated else None
        is_owner = requester_profile and requester_profile.pk == profile.pk
        try:
            page = int(request.query_params.get("boards_page", 1))
        except (TypeError, ValueError):
            page = 1
        try:
            page_size = int(request.query_params.get("boards_page_size", 12))
        except (TypeError, ValueError):
            page_size = 12

        # Response-level cache: key includes viewer identity + pagination params
        # so owner/non-owner payloads (boards visibility) and pagination state
        # are never mixed. Version-based invalidation bumps the version key on
        # any profile mutation, rendering old entries unreachable without explicit
        # delete_pattern (which LocMemCache doesn't support).
        requester_id_for_cache = str(requester_profile.id) if requester_profile else 'anon'
        cache_key = get_user_profile_detail_cache_key(
            user_id, requester_id_for_cache, page, page_size
        )
        cached_payload = cache.get(cache_key)
        if cached_payload is not None:
            return Response(cached_payload)

        data = UserProfileSerializer(profile).data
        data['boards'] = _build_boards_field(profile, is_owner, page=page, page_size=page_size)

        # is_following injection (SOC1)
        if requester_profile and not is_owner:
            from apps.social.models import Follow
            data['is_following'] = Follow.objects.filter(
                follower=requester_profile,
                followee=profile,
            ).exists()
        else:
            data['is_following'] = False

        # Serialiser returns OrderedDict; cast to plain dict for cache storage
        # so it round-trips cleanly through pickle / JSON.
        cache.set(cache_key, dict(data), PROFILE_DETAIL_TTL)
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
        # Invalidate all profile-detail cache entries for this user so the next
        # GET sees updated display_name / avatar_url / bio / etc.
        from apps.recommendation.caches import evict_user_profile_detail
        evict_user_profile_detail(profile.user.id)
        # Return full UserProfileSerializer shape (consistent with GET)
        return Response(UserProfileSerializer(profile).data)


# -- Liked Buildings (SNS-LIKED-PROJECTS) ----------------------------------

_LIKED_BUILDINGS_CAP = 200
_BLD_ID_MAX_LEN = 20
_BLD_ID_RE = re.compile(r'^bld_\d{6}$')


class LikedBuildingsView(APIView):
    """POST/GET /api/v1/liked-buildings/

    POST — add a building to the authenticated user's liked list.
      Body:   {"canonical_bld_id": "bld_000123"}
      200:    {"liked_count": N}
      400:    {"detail": "<reason>"}

    GET — return the user's liked buildings as full card objects.
      200:    {"buildings": [...], "total": N}

    Ordering: newest first (prepend on POST). Deduped. Capped at
    _LIKED_BUILDINGS_CAP entries; the cap is silently enforced on write.
    get_building_card gates on is_publishable=true and returns None for
    unpublished / missing buildings — those are silently filtered from GET.
    """
    permission_classes = [IsAuthenticated]

    def post(self, request):
        bld_id = request.data.get('canonical_bld_id', '')
        if not bld_id or not isinstance(bld_id, str):
            return Response(
                {'detail': 'canonical_bld_id required'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        bld_id = bld_id.strip()
        if not bld_id:
            return Response(
                {'detail': 'canonical_bld_id required'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if len(bld_id) > _BLD_ID_MAX_LEN:
            return Response(
                {'detail': 'canonical_bld_id too long'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if not _BLD_ID_RE.match(bld_id):
            return Response(
                {'detail': 'invalid canonical_bld_id format'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        with _dj_connections['buildings'].cursor() as cur:
            cur.execute(
                'SELECT 1 FROM canonical_v2_buildings'
                ' WHERE canonical_bld_id = %s AND is_publishable = true',
                [bld_id],
            )
            if not cur.fetchone():
                return Response(
                    {'detail': 'building not found'},
                    status=status.HTTP_404_NOT_FOUND,
                )

        try:
            profile = request.user.profile
        except UserProfile.DoesNotExist:
            return Response(
                {'detail': 'Profile not found'},
                status=status.HTTP_404_NOT_FOUND,
            )

        current = list(profile.liked_building_ids or [])
        if bld_id not in current:
            current.insert(0, bld_id)
            # Enforce cap silently
            current = current[:_LIKED_BUILDINGS_CAP]
            profile.liked_building_ids = current
            profile.save(update_fields=['liked_building_ids'])

        return Response({'liked_count': len(profile.liked_building_ids)})

    def get(self, request):
        try:
            profile = request.user.profile
        except UserProfile.DoesNotExist:
            return Response(
                {'detail': 'Profile not found'},
                status=status.HTTP_404_NOT_FOUND,
            )

        from apps.recommendation import engine

        bld_ids = list(profile.liked_building_ids or [])[:_LIKED_BUILDINGS_CAP]
        cards = engine.get_buildings_by_ids(bld_ids)
        return Response({'buildings': cards, 'total': len(cards)})
