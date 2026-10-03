"""Input validators + output shapers for apps.messaging."""
from rest_framework import serializers

from .models import Report


class ContactRequestCreateSerializer(serializers.Serializer):
    recipient_id = serializers.IntegerField()
    greeting = serializers.CharField(
        max_length=100, required=False, allow_blank=True, default='',
    )


class MessageCreateSerializer(serializers.Serializer):
    # trim_whitespace (default True) strips; blank after strip -> 400.
    body = serializers.CharField(min_length=1, max_length=1000)


class ReportCreateSerializer(serializers.Serializer):
    target_type = serializers.ChoiceField(choices=[c[0] for c in Report.TARGET_CHOICES])
    target_id = serializers.CharField(max_length=64)
    reason = serializers.CharField(max_length=500, required=False, allow_blank=True, default='')


def user_summary(profile):
    """Public summary of a UserProfile. `user_id` is the auth User id (API-wide id)."""
    return {
        'user_id': profile.user_id,
        'display_name': profile.display_name,
        'handle': profile.handle,
        'avatar_url': profile.avatar_url,
    }


def message_dict(message, viewer=None):
    data = {
        'id': message.id,
        'sender_id': message.sender.user_id if message.sender_id else None,
        'kind': message.kind,
        'system_type': message.system_type,
        'body': message.body,
        'created_at': message.created_at,
    }
    if viewer is not None:
        data['is_mine'] = message.sender_id == viewer.pk
    return data


def last_message_dict(message):
    return {
        'id': message.id,
        'kind': message.kind,
        'system_type': message.system_type,
        'body': message.body,
        'created_at': message.created_at,
    }
