from rest_framework import serializers
from .models import UserProfile


class UserSerializer(serializers.ModelSerializer):
    """Login / auth-token response serializer. Used by _make_token_response() and MeView.
    Shape is a stable contract with the frontend login flow — do NOT add PROF2 fields here.
    """
    user_id   = serializers.IntegerField(source='id', read_only=True)
    providers = serializers.SerializerMethodField()

    class Meta:
        model  = UserProfile
        fields = ['user_id', 'display_name', 'avatar_url', 'providers']

    def get_providers(self, obj):
        return list(obj.social_accounts.values_list('provider', flat=True))


class UserMiniSerializer(serializers.ModelSerializer):
    """Minimal public user shape for Project/Board nested `user` field.

    Exposes ONLY: user_id, display_name, avatar_url — deliberately omits
    `providers` (OAuth provider is private metadata, not a public-facing field).

    Used by ProjectSerializer; keeps provider info off public Project responses.
    No per-row Python method calls; callers must supply `select_related('user')` on the queryset to avoid FK traversal queries.
    """
    user_id = serializers.IntegerField(source='user.id', read_only=True)

    class Meta:
        model  = UserProfile
        fields = ['user_id', 'display_name', 'avatar_url']


class UserProfileSerializer(serializers.ModelSerializer):
    """Public UserProfile — matches designer's MOCK_USER shape (Phase 13 PROF2 scope).

    Excludes:
        - is_following: Phase 15 SOC1 — computed by SOC1 view via Follow table
        - boards[]:     BOARD1 territory — view-injected when wired with Project visibility
    """
    user_id = serializers.IntegerField(source='user.id', read_only=True)

    class Meta:
        model = UserProfile
        fields = [
            'user_id',
            'display_name',
            'avatar_url',
            'bio',
            'mbti',
            'external_links',
            'persona_summary',
            'follower_count',
            'following_count',
        ]
        read_only_fields = ['user_id', 'follower_count', 'following_count', 'persona_summary']


class UserProfileSelfUpdateSerializer(serializers.ModelSerializer):
    """PATCH /api/v1/users/me/ — owner updates editable fields only.

    Excludes counter caches (auto-managed) and avatar_url (separate upload flow,
    future commit). persona_summary is Phase 17 LLM-derived — not user-editable.
    """
    class Meta:
        model = UserProfile
        fields = ['display_name', 'bio', 'mbti', 'external_links']

    def validate_mbti(self, value):
        """MBTI must be exactly 4 letters or empty."""
        if value and (len(value) != 4 or not value.isalpha()):
            raise serializers.ValidationError('MBTI must be exactly 4 letters or empty.')
        return value.upper() if value else value

    def validate_external_links(self, value):
        """external_links must be a dict with string keys and string values."""
        if not isinstance(value, dict):
            raise serializers.ValidationError('external_links must be an object.')
        for k, v in value.items():
            if not isinstance(k, str) or not isinstance(v, str):
                raise serializers.ValidationError(
                    'external_links keys and values must be strings.'
                )
            if len(v) > 500:
                raise serializers.ValidationError(
                    f'external_links["{k}"] exceeds 500 chars.'
                )
        return value
