from rest_framework import serializers
from .models import UserProfile


class UserSerializer(serializers.ModelSerializer):
    user_id   = serializers.IntegerField(source='id', read_only=True)
    providers = serializers.SerializerMethodField()

    class Meta:
        model  = UserProfile
        fields = ['user_id', 'display_name', 'avatar_url', 'providers']

    def get_providers(self, obj):
        return list(obj.social_accounts.values_list('provider', flat=True))
