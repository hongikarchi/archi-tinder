"""
serializers.py -- apps/contests

Datetimes are stored tz-aware (UTC) and serialized as ISO 8601 with offset;
the frontend converts to KST.
"""
from django.conf import settings
from django.utils import timezone
from rest_framework import serializers

from .models import Contest
from .validators import is_http_url


class ContestSerializer(serializers.ModelSerializer):
    next_deadline_kind = serializers.SerializerMethodField()
    next_deadline = serializers.SerializerMethodField()
    is_closed = serializers.SerializerMethodField()
    poster_url = serializers.SerializerMethodField()
    source_url = serializers.SerializerMethodField()
    listing_url = serializers.SerializerMethodField()
    interested = serializers.SerializerMethodField()
    takedown_email = serializers.SerializerMethodField()

    class Meta:
        model = Contest
        fields = [
            'id', 'title', 'organizer', 'organizer_type',
            'submission_deadline', 'apply_deadline', 'notice_date',
            'theme', 'summary', 'eligibility', 'team_size',
            'source_url', 'listing_source', 'listing_url',
            'poster_url', 'poster_credit', 'poster_status',
            'interest_count', 'interested', 'takedown_email',
            'next_deadline_kind', 'next_deadline', 'is_closed',
        ]
        read_only_fields = fields

    def _now(self):
        # A single "now" per serialization pass, injectable via context for tests.
        return self.context.get('now') or timezone.now()

    def get_next_deadline_kind(self, obj):
        return obj.next_deadline(self._now())[0]

    def get_next_deadline(self, obj):
        value = obj.next_deadline(self._now())[1]
        return serializers.DateTimeField().to_representation(value)

    def get_is_closed(self, obj):
        return obj.submission_deadline < self._now()

    def get_poster_url(self, obj):
        # Never leak an unverified / removed poster URL to clients (D4-D6).
        # No takedown contact configured -> no poster is shown (output gating only).
        if (
            obj.poster_status == Contest.POSTER_ALLOWED
            and is_http_url(obj.poster_url)
            and settings.CONTEST_TAKEDOWN_EMAIL
        ):
            return obj.poster_url
        return None

    def get_takedown_email(self, obj):
        return settings.CONTEST_TAKEDOWN_EMAIL or ''

    # Defense in depth: never emit a non-http(s) URL even if a bad row got in
    # through queryset.update() / raw SQL (Contest.save() validates the normal path).
    def get_source_url(self, obj):
        return obj.source_url if is_http_url(obj.source_url) else ''

    def get_listing_url(self, obj):
        return obj.listing_url if is_http_url(obj.listing_url) else ''

    def get_interested(self, obj):
        # Views annotate `interested` (Exists subquery) -- no per-row query here.
        return bool(getattr(obj, 'interested', False))


class PosterReportSerializer(serializers.Serializer):
    reason = serializers.CharField(max_length=500, required=False, allow_blank=True)
    reporter_email = serializers.EmailField(required=False, allow_blank=True)
