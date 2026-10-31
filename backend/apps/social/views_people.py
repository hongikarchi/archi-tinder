"""apps.social.views_people — Social feed (per-BOARD) + per-board report image.

GET /api/v1/people/

A feed of BOARDS (Projects), not people. Each item is one public board with
its persona report image, plus its owner's identity/type and the requester's
reaction state.

Query params:
  filter    — absent (newest first) | 'inspired' (owner closest to me) |
              'opposite' (owner furthest from me) | a 4-letter type code
              (e.g. 'CLON') = only owners of that type, newest first.
  cursor    — opaque string from the previous response's `next_cursor`.
  page_size — default 20, max 30.

Candidate pool (every condition is a hard requirement):
  * Project.visibility='public', is_temp=False, report_image non-empty (the
    card's front face IS that image; public keeps private reports private).
  * owner has a PersonalityProfile with discovery_opt_in=True (the user's own
    hide-me switch; also what supplies the vector / type_code).
  * owner is not blocked by / blocking the requester (blocked_profile_ids,
    both directions, independent of MESSAGING_ENABLED).
  * The requester's own boards are INCLUDED, except under the 'inspired' and
    'opposite' filters where they are EXCLUDED (distance 0 to self would pin
    them first / last). Own boards stay in the no-filter feed and appear in a
    type-code filter only when the owner's type matches.

Ordering (ties are broken deterministically, project_id last):
  absent / type code : updated_at DESC, project_id
  inspired           : owner distance ASC,  updated_at DESC, project_id
  opposite           : owner distance DESC, updated_at DESC, project_id
  Distance = 5-D Euclidean between the requester's and the owner's vectors,
  rounded to 4 dp (the same rounded value is sorted on and returned, so the
  cursor comparison is exact). It is computed for every row and every filter.
  No top-N cap, no shuffle.

Pagination — keyset cursor over the sort key of the last returned row
(base64url JSON). It is stable under ties and does not skip/duplicate rows
when the feed is unchanged between requests.

SAFETY CAP: the DB fetch is limited to the _CANDIDATE_CAP most recently updated
matching boards (newest first), because distance sorting happens in Python and
the pool must stay bounded. Everything — sorting, cursors, has_more — operates
on that capped set, so has_more is honest about THAT set: boards older than the
cap are simply not part of the feed (for 'inspired'/'opposite' that means the
oldest boards can never surface). Only metadata columns are fetched (never the
base64 image), so the cap is cheap.

CACHING: the sorted candidate list is cached _FEED_CACHE_TTL seconds per
(requester, filter); cursor pages slice it. The cache holds ONLY ordering data
per entry: (sort_key, project_id, distance) -- no names, avatars or vectors.
Each page is re-validated with one query (still public/non-temp/imaged/opted-in,
owner not blocked) that also fetches every displayed field fresh (board name,
reaction_count, updated_at, owner user_id/display_name/handle/avatar_url/
type_code) plus is_reacted, so owner edits show immediately and a page may
return fewer than page_size rows when boards were hidden inside the TTL.

Response: {results, has_more, next_cursor, me_discoverable, me_hint}. The last
two describe ONLY the requester, independent of filter / cursor / page:
  me_discoverable — discovery_opt_in is True AND the requester owns a public,
                    confirmed (is_temp=False) board with a report image.
  me_hint         — None when discoverable; else 'opted_out' (discovery_opt_in
                    False) | 'unsaved_board' (opted in, only imaged public
                    boards are unconfirmed is_temp) | 'no_public_report_image'.

Errors: 404 no UserProfile, 403 {detail:'assessment_required'} when the
requester has no PersonalityProfile, 400 on bad params / cursor.

GET /api/v1/people/boards/<project_id>/report-image/

Serves one board's persona image. Split off the feed on purpose:
Project.report_image is base64 TEXT, and inlining a page of them would make the
feed megabytes wide; the client lazy-fetches per card. Only public, non-temp
boards that actually have an image are served — everything else is a uniform
404 so the endpoint never confirms that a private board exists.
"""
import base64
import json
import logging
import math
from datetime import datetime, timedelta, timezone as dt_timezone

from django.core.cache import cache
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import UserRateThrottle
from rest_framework.views import APIView

from apps.accounts.models import PersonalityProfile, UserProfile
from apps.messaging.services import blocked_profile_ids
from apps.recommendation.models import Project

logger = logging.getLogger('apps.social')

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Max boards pulled from the DB per request (newest first). See module docstring.
_CANDIDATE_CAP = 1000
_PAGE_SIZE_DEFAULT = 20
_PAGE_SIZE_MAX = 30

# Valid explicit type codes (16 types from 4 binary axes).
_VALID_TYPE_CODES = frozenset({
    'CLON', 'CLOT', 'CLDN', 'CLDT',
    'CSON', 'CSOT', 'CSDN', 'CSDT',
    'RLON', 'RLOT', 'RLDN', 'RLDT',
    'RSON', 'RSOT', 'RSDN', 'RSDT',
})

_EPOCH = datetime(1970, 1, 1, tzinfo=dt_timezone.utc)

# The sorted candidate list is cached per (requester, filter) for this long so
# cursor pages do not re-query + re-sort up to _CANDIDATE_CAP rows. Staleness
# window: a board published / re-ordered / newly opted-in appears up to this
# many seconds late; a board made private, deleted, opted-out or whose owner is
# blocked is dropped immediately by the per-page re-validation query.
_FEED_CACHE_TTL = 40


class PeopleFeedThrottle(UserRateThrottle):
    scope = 'people_feed'


class PeopleBoardImageThrottle(UserRateThrottle):
    scope = 'people_board_image'

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _get_vector(p):
    """Return the 5-D personality vector for a PersonalityProfile instance."""
    return [p.axis_1, p.axis_2, p.axis_3, p.axis_4, p.axis_5]


def _euclidean(v1, v2):
    """5-D Euclidean distance between two vectors."""
    return math.sqrt(sum((a - b) ** 2 for a, b in zip(v1, v2)))


def _micros(dt):
    """Exact integer microseconds since epoch (no float precision loss)."""
    return (dt - _EPOCH) // timedelta(microseconds=1)


def _encode_cursor(key):
    raw = json.dumps(list(key), separators=(',', ':')).encode()
    return base64.urlsafe_b64encode(raw).decode().rstrip('=')


def _decode_cursor(token, key_len):
    """Return the sort-key tuple encoded in `token`, or None when malformed."""
    try:
        raw = base64.urlsafe_b64decode(token + '=' * (-len(token) % 4))
        key = json.loads(raw)
    except Exception:
        return None
    if not isinstance(key, list) or len(key) != key_len:
        return None
    *nums, pid = key
    if not isinstance(pid, str):
        return None
    for n in nums:
        if isinstance(n, bool) or not isinstance(n, (int, float)):
            return None
    return tuple(key)


def _cache_key(profile_pk, filter_param, type_code_filter):
    return f'people_feed:v3:{profile_pk}:{filter_param or type_code_filter or "-"}'


def _load_sorted_entries(my_vec, filter_param, type_code_filter, blocked_ids,
                         requester_pk=None):
    """Fetch up to _CANDIDATE_CAP candidate rows and return them sorted as
    [(sort_key, project_id_str, distance), ...]. This is the expensive part that
    is cached per (requester, filter) for _FEED_CACHE_TTL seconds; display fields
    are deliberately NOT kept (they are re-read fresh per page).

    For 'inspired' / 'opposite' the requester's OWN boards are excluded here
    (distance 0 to self would always sort first / last), so the cached list
    never contains them. No-filter and type-code feeds keep own boards."""
    qs = (
        Project.objects
        .filter(
            visibility='public',
            is_temp=False,
            user__personality__discovery_opt_in=True,
        )
        .exclude(report_image__isnull=True)
        .exclude(report_image='')
    )
    if blocked_ids:
        qs = qs.exclude(user_id__in=blocked_ids)
    if requester_pk is not None and filter_param in ('inspired', 'opposite'):
        qs = qs.exclude(user_id=requester_pk)
    if type_code_filter is not None:
        qs = qs.filter(user__personality__type_code=type_code_filter)

    # values() = no model hydration and, crucially, never loads the base64
    # report_image column.
    rows = list(
        qs.order_by('-updated_at', '-project_id')
        .values(
            'project_id', 'updated_at',
            'user__personality__axis_1', 'user__personality__axis_2',
            'user__personality__axis_3', 'user__personality__axis_4',
            'user__personality__axis_5',
        )[:_CANDIDATE_CAP]
    )

    entries = []
    for r in rows:
        their_vec = [r[f'user__personality__axis_{i}'] for i in range(1, 6)]
        dist = round(_euclidean(my_vec, their_vec), 4)
        neg_ts = -_micros(r['updated_at'])
        pid = str(r['project_id'])
        if filter_param == 'inspired':
            key = (dist, neg_ts, pid)
        elif filter_param == 'opposite':
            key = (-dist, neg_ts, pid)
        else:
            key = (neg_ts, pid)
        entries.append((key, pid, dist))
    entries.sort(key=lambda e: e[0])
    return entries


def _parse_page_size(raw):
    if raw is None:
        return _PAGE_SIZE_DEFAULT
    try:
        n = int(raw)
    except (TypeError, ValueError):
        return None
    if n < 1:
        return None
    return min(n, _PAGE_SIZE_MAX)


def _me_discoverability(profile, personality):
    """(me_discoverable, me_hint) for the requester only: one query.

    Checks the requester's own public imaged boards (metadata only, never the
    base64 column) and whether any is confirmed (is_temp=False).
    """
    if not personality.discovery_opt_in:
        return False, 'opted_out'
    temp_flags = set(
        Project.objects
        .filter(user=profile, visibility='public')
        .exclude(report_image__isnull=True)
        .exclude(report_image='')
        .values_list('is_temp', flat=True)
        .distinct()
    )
    if False in temp_flags:
        return True, None
    if True in temp_flags:
        return False, 'unsaved_board'
    return False, 'no_public_report_image'


# ---------------------------------------------------------------------------
# Views
# ---------------------------------------------------------------------------

class PeopleDiscoveryView(APIView):
    """GET /api/v1/people/ — per-board social feed."""

    permission_classes = [IsAuthenticated]
    throttle_classes = [PeopleFeedThrottle]

    def get(self, request):
        # -- Guard: requester must have completed assessment ------------------
        try:
            requester_profile = request.user.profile
        except UserProfile.DoesNotExist:
            return Response(
                {'detail': 'UserProfile not found.'},
                status=status.HTTP_404_NOT_FOUND,
            )

        try:
            my_personality = requester_profile.personality
        except PersonalityProfile.DoesNotExist:
            return Response(
                {'detail': 'assessment_required'},
                status=status.HTTP_403_FORBIDDEN,
            )

        my_vec = _get_vector(my_personality)

        # -- Parse query params -----------------------------------------------
        filter_param = (request.query_params.get('filter') or '').strip()
        type_code_filter = None
        if filter_param and filter_param not in ('inspired', 'opposite'):
            upper_filter = filter_param.upper()
            if upper_filter not in _VALID_TYPE_CODES:
                return Response(
                    {'detail': (
                        'filter must be "inspired", "opposite", '
                        'or a valid 4-letter type code.'
                    )},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            type_code_filter = upper_filter
            filter_param = ''

        page_size = _parse_page_size(request.query_params.get('page_size'))
        if page_size is None:
            return Response(
                {'detail': 'page_size must be a positive integer.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        by_distance = filter_param in ('inspired', 'opposite')
        # Sort-key layout: distance filters -> (±dist, -updated_micros, pid);
        # otherwise -> (-updated_micros, pid). All parts sort ascending.
        key_len = 3 if by_distance else 2

        cursor_key = None
        cursor_raw = request.query_params.get('cursor')
        if cursor_raw:
            cursor_key = _decode_cursor(cursor_raw, key_len)
            if cursor_key is None:
                return Response(
                    {'detail': 'Invalid cursor.'},
                    status=status.HTTP_400_BAD_REQUEST,
                )

        # Block set (either direction) — fetched fresh on EVERY request and
        # independent of MESSAGING_ENABLED, so blocks survive the flag being OFF
        # and a new block takes effect immediately even on a cached list.
        blocked_ids = blocked_profile_ids(requester_profile)

        # -- Sorted candidate list (cached for _FEED_CACHE_TTL seconds) -------
        cache_key = _cache_key(requester_profile.pk, filter_param, type_code_filter)
        entries = cache.get(cache_key)
        if entries is None:
            entries = _load_sorted_entries(
                my_vec, filter_param, type_code_filter, blocked_ids,
                requester_pk=requester_profile.pk)
            cache.set(cache_key, entries, _FEED_CACHE_TTL)

        if cursor_key is not None:
            entries = [e for e in entries if e[0] > cursor_key]

        page = entries[:page_size]
        has_more = len(entries) > page_size
        next_cursor = _encode_cursor(page[-1][0]) if (has_more and page) else None

        # -- Re-validate the page against live data: ONE cheap query ----------
        # Drops boards that went private / temp / image-less / opted-out or
        # whose owner got blocked since the list was cached, and refreshes the
        # volatile fields (name, reaction_count). Metadata columns only.
        page_pids = [e[1] for e in page]
        fresh = {}
        if page_pids:
            fresh_qs = (
                Project.objects
                .filter(
                    project_id__in=page_pids,
                    visibility='public',
                    is_temp=False,
                    user__personality__discovery_opt_in=True,
                )
                .exclude(report_image__isnull=True)
                .exclude(report_image='')
            )
            if blocked_ids:
                fresh_qs = fresh_qs.exclude(user_id__in=blocked_ids)
            fresh = {
                str(f['project_id']): f
                for f in fresh_qs.values(
                    'project_id', 'name', 'updated_at', 'reaction_count',
                    'user_id', 'user__user_id', 'user__display_name',
                    'user__handle', 'user__avatar_url',
                    'user__personality__type_code',
                )
            }
            page = [e for e in page if e[1] in fresh]
            page_pids = [e[1] for e in page]

        # -- Reaction state: ONE query for the whole page ---------------------
        from apps.social.models import Reaction
        reacted = {
            str(pid) for pid in (
                Reaction.objects
                .filter(user=requester_profile, project_id__in=page_pids)
                .values_list('project_id', flat=True)
            )
        } if page_pids else set()

        results = []
        for _key, pid, dist in page:
            r = fresh[pid]
            results.append({
                'board_id': pid,
                'board_name': r['name'],
                'user_id': r['user__user_id'],
                'display_name': r['user__display_name'],
                'handle': r['user__handle'],
                'avatar_url': r['user__avatar_url'],
                'type_code': r['user__personality__type_code'],
                'distance': dist,
                'is_me': r['user_id'] == requester_profile.pk,
                'is_reacted': pid in reacted,
                'reaction_count': r['reaction_count'],
                'updated_at': r['updated_at'].isoformat(),
            })

        me_discoverable, me_hint = _me_discoverability(requester_profile, my_personality)

        return Response({
            'results': results,
            'has_more': has_more,
            'next_cursor': next_cursor,
            'me_discoverable': me_discoverable,
            'me_hint': me_hint,
        })


class PeopleBoardReportImageView(APIView):
    """GET /api/v1/people/boards/<project_id>/report-image/ — one board's image.

    Public + non-temp + has image, else a uniform 404 (private / missing / no
    image are indistinguishable on purpose). Mirrors the feed pool: the owner
    must be discovery-opted-in and not blocked either way with the requester;
    the requester's own board is always fetchable, even when opted out.
    Callers treat 404 as "no image"
    and fall back; they do not retry. Same {image_data, mime_type} shape and
    no server-side caching as the per-project image endpoint (the payload is a
    single DB column read; HTTP/CDN caching is the client's concern).
    """
    permission_classes = [IsAuthenticated]
    throttle_classes = [PeopleBoardImageThrottle]

    def get(self, request, project_id):
        project = (
            Project.objects
            .filter(project_id=project_id, visibility='public', is_temp=False)
            .exclude(report_image__isnull=True)
            .exclude(report_image='')
            .values('report_image', 'report_image_mime', 'user_id')
            .first()
        )
        if project is not None:
            requester_profile = getattr(request.user, 'profile', None)
            if requester_profile is None:
                project = None
            elif project['user_id'] != requester_profile.pk:
                opted_in = PersonalityProfile.objects.filter(
                    user_id=project['user_id'], discovery_opt_in=True,
                ).exists()
                if (not opted_in
                        or project['user_id'] in blocked_profile_ids(requester_profile)):
                    project = None
        if project is None:
            return Response(
                {'detail': 'No public report image for this board.'},
                status=status.HTTP_404_NOT_FOUND,
            )
        return Response({
            'image_data': project['report_image'],
            'mime_type': project['report_image_mime'] or 'image/png',
        })
