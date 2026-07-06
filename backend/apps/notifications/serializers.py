from rest_framework import serializers

from apps.accounts.serializers import UserMiniSerializer

from .models import Notification


class NotificationSerializer(serializers.ModelSerializer):
    """List-item shape for GET /api/v1/notifications/.

    actor is null for security-category notifications (actor FK is null).
    Uses a SerializerMethodField (not a nested UserMiniSerializer field
    directly) because UserMiniSerializer does not declare allow_null=True —
    passing it a None instance would raise inside DRF's to_representation.
    """
    actor = serializers.SerializerMethodField()

    class Meta:
        model = Notification
        fields = ['id', 'type', 'category', 'payload', 'created_at', 'read_at', 'actor']

    def get_actor(self, obj):
        if obj.actor is None:
            return None
        return UserMiniSerializer(obj.actor).data
