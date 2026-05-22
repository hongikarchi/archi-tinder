from rest_framework import serializers
from apps.accounts.serializers import UserMiniSerializer
from .models import Project


class ProjectSerializer(serializers.ModelSerializer):
    """Public Project (Board) serializer — Phase 13 BOARD1.

    CRITICAL: `disliked_ids` is DELIBERATELY ABSENT from every response.
    Algorithm reads the model directly; this serializer never exposes dislikes.
    Applies to owner, public, admin — all contexts.

    `user` is a nested minimal shape: user_id + display_name + avatar_url.
    """
    project_id = serializers.UUIDField(read_only=True)
    user = UserMiniSerializer(read_only=True)
    latest_session_id = serializers.SerializerMethodField()

    def get_latest_session_id(self, obj):
        if hasattr(obj, '_latest_session_id'):
            return str(obj._latest_session_id) if obj._latest_session_id else None
        session = obj.sessions.order_by('-created_at').first()
        return str(session.session_id) if session else None

    class Meta:
        model  = Project
        fields = [
            'project_id',
            'user',
            'name',
            'visibility',
            'reaction_count',
            'liked_ids',
            'saved_ids',
            'filters',
            'raw_query',
            'analysis_report',
            'final_report',
            'report_image',
            'latest_session_id',
            'created_at',
            'updated_at',
        ]
        read_only_fields = [
            'project_id',
            'user',
            'liked_ids',
            'saved_ids',
            'reaction_count',
            'analysis_report',
            'final_report',
            'report_image',
            'raw_query',
            'latest_session_id',
            'created_at',
            'updated_at',
        ]
        # `disliked_ids` intentionally excluded — never serialized to any caller


class ProjectSelfUpdateSerializer(serializers.ModelSerializer):
    """PATCH /api/v1/projects/{project_id}/ — owner updates name + visibility only.

    All other fields (liked_ids, saved_ids, filters, reaction_count, etc.)
    are managed by swipe flow or system — silently ignored on PATCH.
    """
    class Meta:
        model  = Project
        fields = ['name', 'visibility']
