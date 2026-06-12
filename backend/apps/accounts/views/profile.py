import io
import logging
import re
from uuid import uuid4

from django.conf import settings
from django.db import connections as _dj_connections
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import status
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from django.core.cache import cache

from ..models import UserProfile
from ..serializers import UserSerializer, UserProfileSerializer, UserProfileSelfUpdateSerializer
from ..throttling import AvatarUploadThrottle

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


# -- Avatar Upload (FRONT-AVATAR-1) ----------------------------------------

class AvatarUploadView(APIView):
    """POST /api/v1/users/me/avatar/ — upload and replace the user's avatar.

    Request : multipart/form-data, field name 'avatar' (also 'file' as alias).
    Response: 200 with the same UserSerializer shape as /auth/me/ so the
              frontend can update the auth-user state in one round trip.

    Security pipeline (security-manager reviewed):
      1. Size cap: early Content-Length hint rejects obvious oversized requests before
         MultiPartParser buffers the body; the authoritative cap is file_obj.size
         (post-buffer) which STAYS as the real gate.
         # NOTE: enforce a hard body cap at the reverse proxy (Railway/nginx
         # client_max_body_size ~6m) — app-layer .size fires post-buffer.
      2. Magic-byte sniff: Pillow is the content-type authority (never headers).
      3. Decompression-bomb guard: explicit dimension check after lazy open.
      4. Pillow verify() + re-open + re-encode to WEBP strips EXIF/GPS.
      5. Center-crop to square + resize to 512px edge.
      6. Randomised object key (uuid4) — user-supplied filename never used.
      7. All Pillow/IO errors → 400 "Invalid image." (never 500).
    """
    permission_classes = [IsAuthenticated]
    throttle_classes   = [AvatarUploadThrottle]
    parser_classes     = [MultiPartParser, FormParser]

    def post(self, request):
        # ---- 0. Early Content-Length gate (advisory / defense-in-depth) -----
        # Fires BEFORE MultiPartParser buffers the body, so obvious oversized
        # requests are rejected before disk-spill. CONTENT_LENGTH may be absent
        # or non-numeric (spoofable) — fall through silently; the authoritative
        # cap is file_obj.size (post-buffer) below.
        _cl = request.META.get('CONTENT_LENGTH')
        if _cl is not None:
            try:
                if int(_cl) > settings.AVATAR_MAX_BYTES:
                    return Response(
                        {'detail': f'File too large. Maximum size is {settings.AVATAR_MAX_BYTES // (1024 * 1024)} MB.'},
                        status=status.HTTP_400_BAD_REQUEST,
                    )
            except (ValueError, TypeError):
                pass  # non-numeric — skip early gate, fall through to .size check

        # ---- 1. Extract the uploaded file -----------------------------------
        file_obj = request.FILES.get('avatar') or request.FILES.get('file')
        if file_obj is None:
            return Response(
                {'detail': 'No file provided. Use form field "avatar".'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # ---- 2. Authoritative size cap (post-buffer) ------------------------
        if file_obj.size > settings.AVATAR_MAX_BYTES:
            return Response(
                {'detail': f'File too large. Maximum size is {settings.AVATAR_MAX_BYTES // (1024 * 1024)} MB.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Read into memory now (size is within the cap).
        raw_bytes = file_obj.read()

        # ---- 3. Process via Pillow -----------------------------------------
        try:
            from PIL import Image

            # Align Pillow's built-in bomb guard with our explicit dimension cap
            # (defense-in-depth — the explicit w*h check below is the primary gate).
            Image.MAX_IMAGE_PIXELS = settings.AVATAR_MAX_PIXELS

            bio = io.BytesIO(raw_bytes)

            # Step A: lazy open to check dimensions WITHOUT full decode.
            # Image.open() is lazy — it reads the header only (bomb-safe).
            try:
                img_header = Image.open(bio)
            except Exception:
                return Response(
                    {'detail': 'Invalid image.'},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            # Step B: explicit dimension guard BEFORE verify/decode.
            # Pillow's DecompressionBombError only raises above 2x MAX_IMAGE_PIXELS;
            # images between 1x and 2x only warn. Explicit check catches both zones.
            w, h = img_header.size
            if w * h > settings.AVATAR_MAX_PIXELS:
                return Response(
                    {'detail': 'Image dimensions too large.'},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            # Step C: verify() reads/checks the full file for corruption.
            # verify() CLOSES the internal stream — must re-open afterward.
            try:
                img_header.verify()
            except Exception:
                return Response(
                    {'detail': 'Invalid image.'},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            # Step D: re-open for actual pixel decode (verify consumed stream).
            bio.seek(0)
            try:
                img = Image.open(bio)
                img.load()  # force full decode now
            except Image.DecompressionBombError:
                return Response(
                    {'detail': 'Image dimensions too large.'},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            except Exception:
                return Response(
                    {'detail': 'Invalid image.'},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            # Step E: mode normalisation — composite RGBA/P/LA onto white, then RGB.
            if img.mode in ('RGBA', 'LA', 'P'):
                background = Image.new('RGB', img.size, (255, 255, 255))
                if img.mode == 'P':
                    img = img.convert('RGBA')
                if img.mode in ('RGBA', 'LA'):
                    background.paste(img, mask=img.split()[-1])
                else:
                    background.paste(img)
                img = background
            elif img.mode != 'RGB':
                img = img.convert('RGB')

            # Step F: center-crop to square from the shorter side.
            width, height = img.size
            edge = min(width, height)
            left   = (width  - edge) // 2
            top    = (height - edge) // 2
            img    = img.crop((left, top, left + edge, top + edge))

            # Step G: resize to the fixed output edge.
            output_edge = settings.AVATAR_OUTPUT_EDGE
            img = img.resize((output_edge, output_edge), Image.LANCZOS)

            # Step H: encode to WEBP (strips EXIF/GPS/metadata).
            out_buf = io.BytesIO()
            img.save(out_buf, format='WEBP', quality=85)
            webp_bytes = out_buf.getvalue()

        except Exception:
            # Catch-all: any unexpected Pillow/IO failure must be 400, never 500.
            logger.exception('Unexpected error during avatar image processing')
            return Response(
                {'detail': 'Invalid image.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # ---- 4. Store and update profile ------------------------------------
        # Resolve the profile FIRST — a missing profile returns 404 with nothing
        # written, preventing orphaned objects in R2/disk storage.
        try:
            profile = request.user.profile
        except UserProfile.DoesNotExist:
            return Response(
                {'detail': 'UserProfile not found for current user.'},
                status=status.HTTP_404_NOT_FOUND,
            )

        # Capture old URL before overwrite so we can GC it after save (BACK-AVATAR-2).
        old_avatar_url = profile.avatar_url

        key = f'avatars/{uuid4().hex}.webp'
        from ..storage import store_avatar, delete_avatar
        try:
            avatar_url = store_avatar(webp_bytes, key, request)
        except Exception:
            logger.exception('Avatar storage error (key=%s)', key)
            return Response(
                {'detail': 'Upload failed. Please try again.'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        # Atomic compare-and-swap on avatar_url to prevent concurrent-upload orphans.
        # Two simultaneous uploads both read old=A; without the CAS the later save
        # leaves the earlier-stored object unreferenced (orphan). Only the request
        # whose read still matches the row may claim it; the loser deletes the object
        # it just stored (otherwise unreferenced) so no orphan is created either way.
        # .update() bypasses auto_now, so updated_at is set explicitly.
        swapped = UserProfile.objects.filter(
            pk=profile.pk, avatar_url=old_avatar_url,
        ).update(avatar_url=avatar_url, updated_at=timezone.now())

        if swapped:
            # We won the swap — GC the previous object (skip if first upload / unchanged).
            if old_avatar_url and old_avatar_url != avatar_url:
                delete_avatar(old_avatar_url)
        else:
            # Lost the race — a concurrent upload already replaced avatar_url. Our
            # freshly stored object is unreferenced; delete it so it does not orphan.
            delete_avatar(avatar_url)

        profile.refresh_from_db()

        # Invalidate profile-detail cache so GET /users/{id}/ reflects the new avatar.
        from apps.recommendation.caches import evict_user_profile_detail
        evict_user_profile_detail(profile.user.id)

        # Return the same UserSerializer shape as /auth/me/ so the frontend
        # can update its auth-user state in one round-trip.
        return Response(UserSerializer(profile).data)


# -- Liked Buildings (SNS-LIKED-PROJECTS) ----------------------------------

_LIKED_BUILDINGS_CAP = 200
# FULL-LOGIN-REDESIGN-1 (BACK-AUTH-3): guest users may add up to 50 liked
# buildings.  The 51st attempt triggers the verify-gate — frontend catches
# this 403 and opens VerifyGateModal to prompt Google OAuth promotion.
# Mirrors the board-gate precedent in apps/recommendation/views/projects.py.
# Gate is on the ADD path only (new bld_id not yet in the list); the remove
# path and re-liking an already-present id are unaffected.
_GUEST_LIKE_LIMIT = 50
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
            # Guest verify-gate: block the add if the guest already has
            # _GUEST_LIKE_LIMIT likes.  Verified users are not gated here.
            if profile.is_guest and len(current) >= _GUEST_LIKE_LIMIT:
                return Response(
                    {
                        'detail': 'verify_required',
                        'reason': 'liked_limit_reached',
                        'limit': _GUEST_LIKE_LIMIT,
                    },
                    status=status.HTTP_403_FORBIDDEN,
                )
            current.insert(0, bld_id)
            # Enforce cap silently
            current = current[:_LIKED_BUILDINGS_CAP]
            profile.liked_building_ids = current
            profile.save(update_fields=['liked_building_ids'])
            # BACK-RECOMMEND-4: evict taste + discovery-feed caches so the new like
            # shapes the vector and is excluded from future feed pages immediately.
            # Local import avoids accounts→recommendation circular dependency.
            from apps.recommendation.caches import evict_taste, evict_discovery_feed
            evict_taste(profile.id)
            evict_discovery_feed(profile.id)

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
