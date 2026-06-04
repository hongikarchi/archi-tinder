import re

from django.core.exceptions import ValidationError as DjangoValidationError
from django.core.validators import EmailValidator, URLValidator
from rest_framework import serializers

from .models import UserProfile


class UserSerializer(serializers.ModelSerializer):
    """Login / auth-token response serializer. Used by _make_token_response() and MeView.

    theme and font are intentionally included as bootstrap-critical app preferences —
    the frontend must know the correct theme/font immediately on login to avoid a flash
    of the wrong design system. PROF2 *profile-content* fields (bio, mbti,
    external_links, persona_summary) must stay out of this serializer.

    FULL-LOGIN-REDESIGN-1: added is_guest, onboarding_role, consent_accepted_at
    so the frontend can gate the verify-gate modal without a separate /auth/me/ call.
    """
    user_id   = serializers.IntegerField(source='user.id', read_only=True)
    providers = serializers.SerializerMethodField()

    class Meta:
        model  = UserProfile
        fields = [
            'user_id', 'display_name', 'avatar_url', 'providers', 'theme', 'font',
            'is_guest', 'onboarding_role', 'consent_accepted_at',
        ]

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
    saved_studios_count = serializers.SerializerMethodField()

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
            'saved_studios_count',
        ]
        read_only_fields = ['user_id', 'follower_count', 'following_count', 'persona_summary']

    def get_saved_studios_count(self, obj):
        # Local import avoids circular dependency:
        # apps.social.serializers already imports from apps.accounts.serializers
        # at module level, so a top-level import here would form a cycle.
        from apps.social.models import ArchitectFollow
        return ArchitectFollow.objects.filter(follower=obj).count()


class UserProfileSelfUpdateSerializer(serializers.ModelSerializer):
    """PATCH /api/v1/users/me/ — owner updates editable fields only.

    Excludes counter caches (auto-managed) and avatar_url (separate upload flow,
    future commit). persona_summary is Phase 17 LLM-derived — not user-editable.
    """
    # Override DRF CharField defaults so our validate_<field> methods see the
    # raw user-supplied string (DRF would otherwise strip whitespace + reject
    # empty strings before our validator runs, making the whitespace-only
    # branch dead code).
    display_name = serializers.CharField(
        trim_whitespace=False, allow_blank=True, required=False, max_length=30,
    )
    bio = serializers.CharField(
        trim_whitespace=False,
        allow_blank=True,
        required=False,
        max_length=500,
    )

    class Meta:
        model = UserProfile
        fields = ['display_name', 'bio', 'mbti', 'external_links', 'theme', 'font', 'onboarding_role']

    def validate_display_name(self, value):
        """display_name: 1-30 chars after .strip(); reject whitespace-only."""
        if value is None:
            return value
        stripped = value.strip()
        if len(stripped) == 0:
            raise serializers.ValidationError(
                'display_name cannot be whitespace-only.'
            )
        if len(stripped) > 30:
            raise serializers.ValidationError(
                'display_name must be 30 characters or fewer.'
            )
        return stripped

    def validate_bio(self, value):
        """bio: max 500 chars; whitespace-only -> empty string (cleared)."""
        if value is None:
            return value
        stripped = value.strip()
        if len(stripped) > 500:
            raise serializers.ValidationError(
                'bio must be 500 characters or fewer.'
            )
        # Whitespace-only is treated as "clear the bio" rather than rejected,
        # so users can wipe their bio by submitting a space (or just empty).
        return stripped

    def validate_mbti(self, value):
        """MBTI must be exactly 4 letters or empty."""
        if value and (len(value) != 4 or not value.isalpha()):
            raise serializers.ValidationError('MBTI must be exactly 4 letters or empty.')
        return value.upper() if value else value

    def validate_external_links(self, value):
        """Validate and normalise external_links.

        Accepted keys: instagram, email, website (forward-compat: unknown keys
        pass through with generic checks).

        Per-key rules (empty string = "not set", skip format check):
          instagram — strip a single leading '@', then require
                      ^[A-Za-z0-9._]{1,30}$ (fullmatch, no trailing-newline
                      bypass). Stored without the '@'.
          email     — validated by Django's EmailValidator.
          website   — validated by URLValidator(schemes=['http','https']);
                      blocks javascript:, data:, ftp: etc.
          unknown   — generic: string, ≤500 chars, no control characters.

        Control characters (\\n, \\r, \\0) are rejected on ALL keys to block
        CRLF / header-injection.
        """
        if not isinstance(value, dict):
            raise serializers.ValidationError('external_links must be an object.')

        _CONTROL_RE = re.compile(r'[\n\r\x00]')
        _INSTAGRAM_RE = re.compile(r'^[A-Za-z0-9._]{1,30}$')
        _email_validator = EmailValidator()
        _url_validator = URLValidator(schemes=['http', 'https'])

        normalized = {}

        for k, v in value.items():
            if not isinstance(k, str) or not isinstance(v, str):
                raise serializers.ValidationError(
                    'external_links keys and values must be strings.'
                )
            if len(v) > 500:
                raise serializers.ValidationError(
                    f'external_links["{k}"] exceeds 500 chars.'
                )

            # Control-character check applies to ALL keys.
            if _CONTROL_RE.search(v):
                raise serializers.ValidationError(
                    f'external_links["{k}"] contains invalid control characters.'
                )

            if v == '':
                # Empty means "not set" — store as-is, skip format check.
                normalized[k] = v
                continue

            if k == 'instagram':
                # Strip exactly one leading '@' (not lstrip — that eats '@@foo').
                handle = v[1:] if v.startswith('@') else v
                if not _INSTAGRAM_RE.fullmatch(handle):
                    raise serializers.ValidationError(
                        'Instagram handle may only contain letters, numbers, '
                        '"." and "_" (max 30).'
                    )
                normalized[k] = handle

            elif k == 'email':
                try:
                    _email_validator(v)
                except DjangoValidationError:
                    raise serializers.ValidationError(
                        'external_links["email"] is not a valid email address.'
                    )
                # EmailValidator (RFC 5321) permits ?,&,= in the local-part;
                # those are RFC 6068 mailto: header-field delimiters, so a value
                # like "user?cc=evil@x.com" would inject cc/subject into the
                # frontend's mailto:${email} link. Reject them.
                if '?' in v or '&' in v:
                    raise serializers.ValidationError(
                        'external_links["email"] may not contain "?" or "&".'
                    )
                normalized[k] = v

            elif k == 'website':
                try:
                    _url_validator(v)
                except DjangoValidationError:
                    raise serializers.ValidationError(
                        'external_links["website"] must be a valid http(s) URL.'
                    )
                normalized[k] = v

            else:
                # Unknown key — generic pass-through (forward-compat).
                normalized[k] = v

        return normalized
