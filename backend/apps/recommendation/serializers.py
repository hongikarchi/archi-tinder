from rest_framework import serializers
from .models import Project


class ProjectSerializer(serializers.ModelSerializer):
    project_id = serializers.UUIDField(read_only=True)

    class Meta:
        model  = Project
        fields = [
            'project_id', 'name', 'filters',
            'liked_ids', 'disliked_ids', 'saved_ids',
            'analysis_report', 'final_report', 'report_image',
            'created_at', 'updated_at',
        ]
        read_only_fields = [
            'project_id', 'liked_ids', 'disliked_ids', 'saved_ids',
            'analysis_report', 'final_report', 'report_image',
            'created_at', 'updated_at',
        ]
