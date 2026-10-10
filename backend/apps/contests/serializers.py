"""
serializers.py -- apps/contests

Datetimes are stored tz-aware (UTC) and serialized as ISO 8601 with offset;
the frontend converts to KST.
"""
from django.utils import timezone
from rest_framework import serializers

from .models import Contest


class ContestSerializer(serializers.ModelSerializer):
    next_deadline_kind = serializers.SerializerMethodField()
    next_deadline = serializers.SerializerMethodField()
    is_closed = serializers.SerializerMethodField()
    poster_url = serializers.SerializerMethodField()

    class Meta:
        model = Contest
        fields = [
            'id', 'title', 'organizer', 'organizer_type',
            'submission_deadline', 'apply_deadline', 'notice_date',
            'theme', 'summary', 'eligibility', 'team_size',
            'source_url', 'listing_source', 'listing_url',
            'poster_url', 'poster_credit', 'poster_status',
            'interest_count',
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
        if obj.poster_status == Contest.POSTER_ALLOWED:
            return obj.poster_url
        return None
