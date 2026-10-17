"""Taste-start feedback endpoints (TASTE-FEEDBACK-1). All IsAuthenticated + throttled.

POST feedback/card-reports/           upsert a report on one card (user, round_key, building)
POST feedback/card-reports/cancel/    mark it user_canceled (row kept)
POST feedback/query-reports/          upsert a report on a recognised sentence (user, round_key)
POST feedback/query-reports/cancel/   mark it user_canceled (row kept)
"""
import logging

from django.db import IntegrityError, connections, transaction
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.recommendation.taste_start import matching

from .models import CardReport, QueryReport
from .throttling import FeedbackThrottle
from .validation import (
    ValidationFail, check_card_fields, check_comment, check_common,
    check_wrong_tags_in_tags,
)

logger = logging.getLogger('apps.feedback')

_BUILDING_COLUMNS = (
    'program', 'typology_primary', 'style', 'atmosphere', 'color_tone',
    'location_country', 'location_city', 'project_year', 'material_visual',
    'architectural_elements', 'visual_description',
)
_SNAPSHOT_EXCLUDE = ('visual_description',)


def _bad(detail):
    return Response({'detail': detail}, status=status.HTTP_400_BAD_REQUEST)


def _fetch_building(bld_id):
    """One publishable building row as a dict, or None. Raw SQL on the buildings DB."""
    sql = (f"SELECT {', '.join(_BUILDING_COLUMNS)} FROM canonical_v2_buildings "
           "WHERE canonical_bld_id = %s AND is_publishable = true")
    with connections['buildings'].cursor() as cur:
        cur.execute(sql, [bld_id])
        row = cur.fetchone()
    if row is None:
        return None
    return dict(zip(_BUILDING_COLUMNS, row))


def _upsert(model, lookup, defaults, compare):
    """Create or update one report row. Returns (obj, created).

    Status goes back to `unreviewed` only when a field in `compare` changed or the
    row was `user_canceled`; re-sending identical content keeps the owner's verdict.
    A concurrent identical create (IntegrityError) is retried as an update.
    """
    for attempt in (0, 1):
        try:
            with transaction.atomic():
                obj = model.objects.select_for_update().filter(**lookup).first()
                if obj is None:
                    return model.objects.create(**lookup, **defaults, status='unreviewed'), True
                changed = obj.status == 'user_canceled' or any(
                    getattr(obj, f) != defaults[f] for f in compare)
                for k, v in defaults.items():
                    setattr(obj, k, v)
                if changed:
                    obj.status = 'unreviewed'
                obj.save()
                return obj, False
        except IntegrityError:
            if attempt:
                raise


def _profile(request):
    return getattr(request.user, 'profile', None)


def _explain_wrong_tags(wrong, tags, row):
    """Attach server-side matched / matched_via / direction to each wrong tag."""
    by_key = {(t.axis, repr(t.to_dict()['value'])): t for t in tags}
    out = []
    for w in wrong:
        tag = by_key[(w['axis'], repr(w['value']))]
        matched, via = matching.explain_tag(tag, row)
        out.append({
            'axis': w['axis'], 'value': w['value'], 'polarity': tag.polarity,
            'matched': matched, 'matched_via': via,
            'direction': 'not_actually_present' if matched else 'actually_present',
        })
    return out


class CardReportView(APIView):
    permission_classes = [IsAuthenticated]
    throttle_classes = [FeedbackThrottle]

    def post(self, request):
        profile = _profile(request)
        if profile is None:
            return _bad('profile required')
        data = request.data
        try:
            common = check_common(data)
            card = check_card_fields(data)
            comment = check_comment(data)
            if card['reason'] is None and not comment.strip():
                raise ValidationFail('reason or comment is required')
            wrong = check_wrong_tags_in_tags(
                data.get('wrong_tags'), common['parsed_tags'], allowed=card['reason'] == 'tag')
        except ValidationFail as exc:
            return _bad(str(exc))

        row = _fetch_building(card['canonical_bld_id'])
        if row is None:
            return _bad('unknown building')
        snapshot = {k: v for k, v in row.items() if k not in _SNAPSHOT_EXCLUDE}

        obj, created = _upsert(
            CardReport,
            {'user': profile, 'round_key': common['round_key'],
             'canonical_bld_id': card['canonical_bld_id']},
            {
                'query_text': common['query_text'], 'tags': common['tags'],
                'source': common['source'], 'language': common['language'],
                'comment': comment, 'card_rank': card['card_rank'],
                'hit': card['hit'], 'total': card['total'],
                'reason': card['reason'], 'sub_reasons': card['sub_reasons'],
                'wrong_tags': _explain_wrong_tags(wrong, common['parsed_tags'], row),
                'building_snapshot': snapshot,
            },
            ('reason', 'sub_reasons', 'wrong_tags', 'comment', 'tags'),
        )
        return Response({'id': obj.id, 'status': obj.status},
                        status=status.HTTP_201_CREATED if created else status.HTTP_200_OK)


class CardReportCancelView(APIView):
    permission_classes = [IsAuthenticated]
    throttle_classes = [FeedbackThrottle]

    def post(self, request):
        profile = _profile(request)
        if profile is None:
            return _bad('profile required')
        round_key = request.data.get('round_key')
        bld_id = request.data.get('canonical_bld_id')
        if not isinstance(round_key, str) or not round_key or not isinstance(bld_id, str) or not bld_id:
            return _bad('round_key and canonical_bld_id are required')
        n = CardReport.objects.filter(
            user=profile, round_key=round_key, canonical_bld_id=bld_id,
        ).update(status='user_canceled')
        if not n:
            return Response({'detail': 'not found'}, status=status.HTTP_404_NOT_FOUND)
        return Response(status=status.HTTP_204_NO_CONTENT)


class QueryReportView(APIView):
    permission_classes = [IsAuthenticated]
    throttle_classes = [FeedbackThrottle]

    def post(self, request):
        profile = _profile(request)
        if profile is None:
            return _bad('profile required')
        data = request.data
        try:
            common = check_common(data)
            comment = check_comment(data)
            wrong = check_wrong_tags_in_tags(
                data.get('wrong_tags'), common['parsed_tags'], allowed=True)
            if not wrong and not comment.strip():
                raise ValidationFail('wrong_tags or comment is required')
        except ValidationFail as exc:
            return _bad(str(exc))

        obj, created = _upsert(
            QueryReport,
            {'user': profile, 'round_key': common['round_key']},
            {
                'query_text': common['query_text'], 'tags': common['tags'],
                'source': common['source'], 'language': common['language'],
                'comment': comment,
                'wrong_tags': wrong,
            },
            ('wrong_tags', 'comment', 'tags'),
        )
        return Response({'id': obj.id, 'status': obj.status},
                        status=status.HTTP_201_CREATED if created else status.HTTP_200_OK)


class QueryReportCancelView(APIView):
    permission_classes = [IsAuthenticated]
    throttle_classes = [FeedbackThrottle]

    def post(self, request):
        profile = _profile(request)
        if profile is None:
            return _bad('profile required')
        round_key = request.data.get('round_key')
        if not isinstance(round_key, str) or not round_key:
            return _bad('round_key is required')
        n = QueryReport.objects.filter(
            user=profile, round_key=round_key,
        ).update(status='user_canceled')
        if not n:
            return Response({'detail': 'not found'}, status=status.HTTP_404_NOT_FOUND)
        return Response(status=status.HTTP_204_NO_CONTENT)
