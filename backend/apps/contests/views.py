"""
views.py -- apps/contests

  GET /api/v1/contests/       -- published, not past submission deadline, soonest first (cap 100)
  GET /api/v1/contests/<id>/  -- detail; opens past-deadline rows; hidden/pending -> 404

  POST   /api/v1/contests/<id>/interest/       -- 201 new / 200 existing {interest_count, interested}
  DELETE /api/v1/contests/<id>/interest/       -- 204 (idempotent)

Design record: docs/decisions/2026-10-09-contest-real-data.md (§4-2).
"""
from django.db.models import BooleanField, Exists, OuterRef, Value
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import UserRateThrottle
from rest_framework.views import APIView

from .models import Contest, ContestInterest
from .serializers import ContestSerializer

_LIST_CAP = 100


def _with_interested(qs, user):
    """Annotate `interested` for `user` as one Exists subquery (no N+1)."""
    profile = getattr(user, 'profile', None)
    if profile is None:
        return qs.annotate(interested=Value(False, output_field=BooleanField()))
    return qs.annotate(interested=Exists(
        ContestInterest.objects.filter(contest=OuterRef('pk'), user=profile)
    ))


class ContestListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        now = timezone.now()
        qs = (
            _with_interested(Contest.objects, request.user)
            .filter(status=Contest.STATUS_PUBLISHED, submission_deadline__gte=now)
            .order_by('submission_deadline', 'id')[:_LIST_CAP]
        )
        data = ContestSerializer(qs, many=True, context={'now': now}).data
        return Response({'results': data})


class ContestDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        contest = get_object_or_404(
            _with_interested(Contest.objects, request.user),
            pk=pk, status=Contest.STATUS_PUBLISHED,
        )
        return Response(ContestSerializer(contest, context={'now': timezone.now()}).data)


class ContestInterestThrottle(UserRateThrottle):
    """60 interest toggles per user per minute (rate in DEFAULT_THROTTLE_RATES)."""
    scope = 'contest_interest'


class ContestInterestView(APIView):
    """POST + DELETE /api/v1/contests/<id>/interest/ (published contests only).

    Allowed after the deadline has passed. Counter maintained by signals.
    Like ReactionView, a user without a profile gets 403; guests are treated
    like any other authenticated user (ReactionView has no guest rule).
    """

    permission_classes = [IsAuthenticated]
    throttle_classes = [ContestInterestThrottle]

    def post(self, request, pk):
        profile = getattr(request.user, 'profile', None)
        if profile is None:
            return Response({'detail': 'Profile not found.'}, status=status.HTTP_403_FORBIDDEN)
        contest = get_object_or_404(Contest, pk=pk, status=Contest.STATUS_PUBLISHED)
        _interest, created = ContestInterest.objects.get_or_create(user=profile, contest=contest)
        contest.refresh_from_db(fields=['interest_count'])
        return Response(
            {'interest_count': contest.interest_count, 'interested': True},
            status=status.HTTP_201_CREATED if created else status.HTTP_200_OK,
        )

    def delete(self, request, pk):
        profile = getattr(request.user, 'profile', None)
        if profile is None:
            return Response({'detail': 'Profile not found.'}, status=status.HTTP_403_FORBIDDEN)
        contest = get_object_or_404(Contest, pk=pk, status=Contest.STATUS_PUBLISHED)
        # Per-instance delete so post_delete signals fire; idempotent (0 rows -> still 204).
        for interest in ContestInterest.objects.filter(user=profile, contest=contest):
            interest.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)
