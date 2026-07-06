"""
views.py -- apps/notifications (NOTIF-INAPP-1)

3 endpoints, all self-only (recipient=request.user's profile), JWT auth
(project default DEFAULT_AUTHENTICATION_CLASSES):

  GET  /api/v1/notifications/                -- paginated list, own inbox only
  GET  /api/v1/notifications/unread-count/   -- {count} cheap COUNT
  POST /api/v1/notifications/mark-read/      -- {ids: [...]} or {all: true} -> {updated}
"""
from django.utils import timezone
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Notification
from .serializers import NotificationSerializer

_PAGE_SIZE_DEFAULT = 20
_PAGE_SIZE_MAX = 50
_MARK_READ_IDS_MAX = 500


def _paginate_queryset(qs, request):
    """Minimal inline pagination: page (1-indexed), page_size (default 20, cap 50).

    Mirrors apps.social.views._paginate_queryset (getProjectReactors pattern).
    Returns (items, meta_dict).
    """
    try:
        page = max(1, int(request.query_params.get('page', 1)))
    except (ValueError, TypeError):
        page = 1
    try:
        page_size = min(_PAGE_SIZE_MAX, max(1, int(request.query_params.get('page_size', _PAGE_SIZE_DEFAULT))))
    except (ValueError, TypeError):
        page_size = _PAGE_SIZE_DEFAULT

    total = qs.count()
    offset = (page - 1) * page_size
    items = list(qs[offset: offset + page_size])
    has_more = (offset + page_size) < total
    return items, {'page': page, 'page_size': page_size, 'has_more': has_more, 'total': total}


def _requester_profile(request):
    """Return the caller's UserProfile, or None if it doesn't exist."""
    return getattr(request.user, 'profile', None)


class NotificationListView(APIView):
    """GET /api/v1/notifications/

    recipient always filtered to request.user's own profile — never exposes
    another user's notifications. Ordered -created_at.

    Response 200:
      {results: [NotificationSerializer...], page, page_size, has_more, total}
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        profile = _requester_profile(request)
        if profile is None:
            return Response({'detail': 'Profile not found.'}, status=status.HTTP_403_FORBIDDEN)

        qs = (
            Notification.objects
            .filter(recipient=profile)
            .select_related('actor__user')
            .order_by('-created_at')
        )
        items, meta = _paginate_queryset(qs, request)
        return Response({
            'results': NotificationSerializer(items, many=True).data,
            **meta,
        })


class UnreadCountView(APIView):
    """GET /api/v1/notifications/unread-count/

    Cheap COUNT-only query — self-only.

    Response 200: {count: int}
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        profile = _requester_profile(request)
        if profile is None:
            return Response({'detail': 'Profile not found.'}, status=status.HTTP_403_FORBIDDEN)

        count = Notification.objects.filter(recipient=profile, read_at__isnull=True).count()
        return Response({'count': count})


class MarkReadView(APIView):
    """POST /api/v1/notifications/mark-read/

    Body: {ids: [int, ...]} or {all: true}. Sets read_at=now() on the
    caller's own UNREAD rows only (idempotent — already-read rows are
    simply not re-touched, still counted... no: only rows actually
    transitioned are counted in `updated`).

    Validates ids list length <= 500 (400 if exceeded).

    Response 200: {updated: int}
    """
    permission_classes = [IsAuthenticated]

    def post(self, request):
        profile = _requester_profile(request)
        if profile is None:
            return Response({'detail': 'Profile not found.'}, status=status.HTTP_403_FORBIDDEN)

        mark_all = request.data.get('all') is True
        ids = request.data.get('ids')

        if not mark_all:
            if not isinstance(ids, list):
                return Response(
                    {'detail': 'ids must be a list, or pass {"all": true}.'},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            if len(ids) > _MARK_READ_IDS_MAX:
                return Response(
                    {'detail': f'ids must have {_MARK_READ_IDS_MAX} entries or fewer.'},
                    status=status.HTTP_400_BAD_REQUEST,
                )

        qs = Notification.objects.filter(recipient=profile, read_at__isnull=True)
        if not mark_all:
            # Filter out any non-int entries defensively rather than 500ing on
            # a malformed payload element.
            clean_ids = [i for i in ids if isinstance(i, int)]
            qs = qs.filter(pk__in=clean_ids)

        updated = qs.update(read_at=timezone.now())
        return Response({'updated': updated})
