"""
views.py -- apps/contests

  GET /api/v1/contests/       -- published, not past submission deadline, soonest first (cap 100)
  GET /api/v1/contests/<id>/  -- detail; opens past-deadline rows; hidden/pending -> 404

Design record: docs/decisions/2026-10-09-contest-real-data.md (§4-2).
"""
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Contest
from .serializers import ContestSerializer

_LIST_CAP = 100


class ContestListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        now = timezone.now()
        qs = (
            Contest.objects
            .filter(status=Contest.STATUS_PUBLISHED, submission_deadline__gte=now)
            .order_by('submission_deadline', 'id')[:_LIST_CAP]
        )
        data = ContestSerializer(qs, many=True, context={'now': now}).data
        return Response({'results': data})


class ContestDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        contest = get_object_or_404(Contest, pk=pk, status=Contest.STATUS_PUBLISHED)
        return Response(ContestSerializer(contest, context={'now': timezone.now()}).data)
