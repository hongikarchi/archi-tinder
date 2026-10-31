"""apps.social.views_liked — boards the requester has reacted to.

GET /api/v1/liked-boards/?page=1&page_size=12

Own reactions only, restricted to boards that are still visibility='public' and
is_temp=False (a board flipped private after the reaction drops out of the
list; the Reaction row itself is untouched so it reappears if re-published).
Newest reaction first (Reaction.created_at DESC). Boards whose owner is blocked
by / blocking the requester are excluded. Not cached: it is per-requester and
must reflect a react/unreact immediately.
"""
from django.db.models import Exists, OuterRef
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.messaging.services import blocked_profile_ids
from apps.recommendation.models import Project
from apps.social.models import Reaction

_PAGE_DEFAULT = 1
_PAGE_SIZE_DEFAULT = 12
_PAGE_SIZE_MAX = 50


def _int_param(request, name, default):
    try:
        return int(request.query_params.get(name, default))
    except (TypeError, ValueError):
        return default


class LikedBoardsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        from apps.accounts.views.profile import _build_board_items

        requester = getattr(request.user, 'profile', None)
        page = max(1, _int_param(request, 'page', _PAGE_DEFAULT))
        page_size = min(max(1, _int_param(request, 'page_size', _PAGE_SIZE_DEFAULT)), _PAGE_SIZE_MAX)

        empty = {
            'items': [], 'page': page, 'page_size': page_size,
            'total_count': 0, 'has_more': False, 'next_page': None,
        }
        if requester is None:
            return Response(empty)

        qs = (
            Reaction.objects
            .filter(user=requester, project__visibility='public', project__is_temp=False)
            .select_related('project', 'project__user')
            # report_image is base64 TEXT (~200KB/row); only a has-image flag is
            # needed, so compute it in SQL and never load the column.
            .defer('project__report_image')
            .annotate(_has_image=Exists(
                Project.objects
                .filter(pk=OuterRef('project_id'))
                .exclude(report_image__isnull=True)
                .exclude(report_image='')
            ))
            .order_by('-created_at', '-id')
        )
        blocked_ids = blocked_profile_ids(requester)
        if blocked_ids:
            qs = qs.exclude(project__user_id__in=blocked_ids)

        total_count = qs.count()
        offset = (page - 1) * page_size
        reactions = list(qs[offset: offset + page_size])
        has_more = offset + page_size < total_count

        projects = []
        for r in reactions:
            r.project._has_report_image = bool(r._has_image)
            projects.append(r.project)
        items = _build_board_items(projects) if projects else []
        for item, project in zip(items, projects):
            owner = project.user
            item['owner'] = {
                'user_id': owner.user_id,
                'display_name': owner.display_name,
                'handle': owner.handle,
                'avatar_url': owner.avatar_url,
            }

        return Response({
            'items': items,
            'page': page,
            'page_size': page_size,
            'total_count': total_count,
            'has_more': has_more,
            'next_page': page + 1 if has_more else None,
        })
