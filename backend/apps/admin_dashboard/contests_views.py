"""Admin contest management (FULL-CONTEST-2): list / create / patch, audit-logged.

Replaces the removed `contest_status` / `contest_poster` management commands.

Every view reuses AdminDashboardView (IsAdminOperator + AdminThrottle): anonymous ->
401, authenticated non-admin -> 403, exactly like the rest of the dashboard.

The publish rule ("published needs an official, non-listing-site source_url") lives in
the MODEL layer (apps.contests.models / validators), so the future collector obeys it
too. This module only catches the model's ValidationError and renders it as a 400.
There is deliberately no DELETE: hide a contest instead.
"""
from zoneinfo import ZoneInfo

from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import transaction
from django.utils import timezone
from rest_framework import serializers
from rest_framework import status as http_status
from rest_framework.response import Response

from apps.contests.models import Contest

from .audit import log_admin_action
from .views import _DEFAULT_PAGE_SIZE, _MAX_PAGE_SIZE, AdminDashboardView, _int_param

KST = ZoneInfo('Asia/Seoul')

ADMIN_CONTEST_FIELDS = [
    'id', 'title', 'organizer', 'organizer_type', 'status',
    'submission_deadline', 'apply_deadline', 'notice_date',
    'theme', 'summary', 'eligibility', 'team_size',
    'source_url', 'listing_source', 'listing_url',
    'poster_url', 'poster_credit',
    'interest_count', 'import_key',
    'created_at', 'updated_at', 'last_verified_at', 'is_closed',
]
READ_ONLY_FIELDS = [
    'id', 'interest_count', 'import_key', 'created_at', 'updated_at',
    'last_verified_at', 'is_closed',
]
# Fields compared before/after a PATCH to report what changed (everything the admin can edit).
EDITABLE_FIELDS = [f for f in ADMIN_CONTEST_FIELDS if f not in READ_ONLY_FIELDS]


class KstDateTimeField(serializers.DateTimeField):
    """A datetime WITHOUT an offset (e.g. '2026-10-28T18:00' from <input type=datetime-local>)
    is interpreted as Asia/Seoul; a value WITH an offset is accepted as given. Always stored
    tz-aware. Date-only strings are rejected (ambiguous time of day). Output is ISO 8601 in
    +09:00 (same instant as the stored UTC value).
    """

    def __init__(self, **kwargs):
        kwargs.setdefault('default_timezone', KST)
        super().__init__(**kwargs)

    def to_internal_value(self, value):
        if isinstance(value, str) and 'T' not in value.upper() and ' ' not in value.strip():
            self.fail('invalid', format='YYYY-MM-DDThh:mm[:ss][+09:00]')
        return super().to_internal_value(value)


class AdminContestSerializer(serializers.ModelSerializer):
    submission_deadline = KstDateTimeField()
    apply_deadline = KstDateTimeField(required=False, allow_null=True)
    is_closed = serializers.SerializerMethodField()

    class Meta:
        model = Contest
        fields = ADMIN_CONTEST_FIELDS
        read_only_fields = READ_ONLY_FIELDS

    def get_is_closed(self, obj):
        return obj.submission_deadline < timezone.now()


def _validation_error_body(exc):
    """Django ValidationError (raised by the model layer) -> DRF-style 400 body.

    Shape: `{<field>: [message, ...], "error_codes": {<field>: [code, ...]}}` where
    `non_field_errors` is the key for errors not tied to a field. `error_codes[field][i]`
    is the stable machine code of `<field>[i]` (e.g. source_url_required,
    source_url_listing_site, invalid_url_scheme, poster_host_blocked) -- the frontend
    maps codes to Korean copy instead of showing the English message.
    """
    if hasattr(exc, 'error_dict'):
        pairs = exc.error_dict.items()
    else:
        pairs = [('non_field_errors', exc.error_list)]
    body, codes = {}, {}
    for field, errors in pairs:
        body[field] = [m for e in errors for m in e.messages]
        codes[field] = [e.code or 'invalid' for e in errors for _ in e.messages]
    body['error_codes'] = codes
    return body


def _drf_error_body(exc):
    """DRF serializers.ValidationError -> the same body shape as _validation_error_body."""
    details = exc.get_full_details()
    if not isinstance(details, dict):
        details = {'non_field_errors': details}
    body, codes = {}, {}
    for field, items in details.items():
        if not isinstance(items, list):
            items = [items]
        body[field] = [
            str(i['message']) if isinstance(i, dict) and 'message' in i else str(i) for i in items
        ]
        codes[field] = [
            i.get('code', 'invalid') if isinstance(i, dict) else 'invalid' for i in items
        ]
    body['error_codes'] = codes
    return body


def _snapshot(instance):
    return {name: getattr(instance, name) for name in EDITABLE_FIELDS}


class ContestListCreateView(AdminDashboardView):
    """GET contests/?status=&page=&page_size= | POST contests/ (create).

    GET returns ALL contests (hidden / pending / past-deadline included), ordered by
    -submission_deadline then -id (stable: editing a row does not reshuffle the list).
    """

    def get(self, request):
        qs = Contest.objects.all()
        status_filter = request.query_params.get('status')
        if status_filter:
            if status_filter not in dict(Contest.STATUS_CHOICES):
                return Response(
                    {'status': ['Must be one of: %s.' % ', '.join(dict(Contest.STATUS_CHOICES))]},
                    status=http_status.HTTP_400_BAD_REQUEST,
                )
            qs = qs.filter(status=status_filter)
        qs = qs.order_by('-submission_deadline', '-id')

        page = _int_param(request.query_params.get('page'), 1, 1, 10**6)
        page_size = _int_param(
            request.query_params.get('page_size'), _DEFAULT_PAGE_SIZE, 1, _MAX_PAGE_SIZE)
        count = qs.count()
        start = (page - 1) * page_size
        rows = qs[start:start + page_size]
        return Response({'results': AdminContestSerializer(rows, many=True).data, 'count': count})

    def post(self, request):
        serializer = AdminContestSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(
                _drf_error_body(serializers.ValidationError(serializer.errors)),
                status=http_status.HTTP_400_BAD_REQUEST,
            )
        try:
            with transaction.atomic():
                contest = serializer.save(last_verified_at=timezone.now())
                log_admin_action(
                    request, 'contest_create', 'contest', contest.pk,
                    {'title': contest.title, 'status': contest.status}, strict=True,
                )
        except DjangoValidationError as exc:
            return Response(_validation_error_body(exc), status=http_status.HTTP_400_BAD_REQUEST)
        return Response(AdminContestSerializer(contest).data, status=http_status.HTTP_201_CREATED)


class ContestDetailView(AdminDashboardView):
    """PATCH contests/<pk>/ -- partial update of any editable field (incl. status and
    poster_url; null or '' clears the poster). No DELETE: set status='hidden' instead.

    Audit: a status change writes `contest_status_change` {from, to}; if other fields
    changed in the same request (or nothing changed at all = a pure re-verify) a separate
    `contest_update` {fields: [...]} row is written as well.
    """

    def patch(self, request, pk):
        try:
            contest = Contest.objects.get(pk=pk)
        except Contest.DoesNotExist:
            return Response({'detail': 'Not found.'}, status=http_status.HTTP_404_NOT_FOUND)

        before = _snapshot(contest)
        serializer = AdminContestSerializer(contest, data=request.data, partial=True)
        if not serializer.is_valid():
            return Response(
                _drf_error_body(serializers.ValidationError(serializer.errors)),
                status=http_status.HTTP_400_BAD_REQUEST,
            )
        try:
            with transaction.atomic():
                # Write ONLY the validated fields (+ last_verified_at / updated_at):
                # a full save() would write back the stale interest_count read above and
                # clobber a concurrent ContestInterest signal update (lost update).
                validated = serializer.validated_data
                for attr, value in validated.items():
                    setattr(contest, attr, value)
                contest.last_verified_at = timezone.now()
                contest.save(update_fields=[*validated.keys(), 'last_verified_at', 'updated_at'])
                after = _snapshot(contest)
                changed = [name for name in EDITABLE_FIELDS if before[name] != after[name]]
                status_changed = 'status' in changed
                other_changed = [name for name in changed if name != 'status']
                # Audit rows share the mutation's transaction: strict, so a failed
                # audit write rolls the change back (500) instead of going unrecorded.
                if status_changed:
                    log_admin_action(
                        request, 'contest_status_change', 'contest', contest.pk,
                        {'from': before['status'], 'to': after['status']}, strict=True,
                    )
                if other_changed or not status_changed:
                    log_admin_action(
                        request, 'contest_update', 'contest', contest.pk,
                        {'fields': other_changed}, strict=True,
                    )
        except DjangoValidationError as exc:
            return Response(_validation_error_body(exc), status=http_status.HTTP_400_BAD_REQUEST)
        # interest_count is signal-maintained and was not written; report the live value.
        contest.refresh_from_db(fields=['interest_count'])
        return Response(AdminContestSerializer(contest).data)
