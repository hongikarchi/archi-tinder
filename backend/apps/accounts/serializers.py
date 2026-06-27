import re
import unicodedata

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

    AUTH-LOGIN-1: added email (self-only), email_verified_at (self-only),
    has_password (self-only, derived bool) so Account screen can show email +
    verified status + "set"/"change" password UI.

    SELF-ONLY RULE: email, email_verified_at, has_password are private — this
    serializer is only used in _make_token_response() (own login) and MeView (GET
    /auth/me/).  Do NOT use this serializer on public-facing profile endpoints.
    """
    user_id      = serializers.IntegerField(source='user.id', read_only=True)
    providers    = serializers.SerializerMethodField()
    email        = serializers.SerializerMethodField()
    has_password = serializers.SerializerMethodField()

    class Meta:
        model  = UserProfile
        fields = [
            'user_id', 'display_name', 'avatar_url', 'providers', 'theme', 'font',
            'language', 'is_guest', 'onboarding_role', 'consent_accepted_at', 'handle',
            'notifications', 'role', 'affiliation',
            # AUTH-LOGIN-1 self-only fields
            'email', 'email_verified_at', 'has_password',
        ]

    def get_providers(self, obj):
        return list(obj.social_accounts.values_list('provider', flat=True))

    def get_email(self, obj):
        """Return the authenticated user's email from the underlying User row."""
        return obj.user.email

    def get_has_password(self, obj):
        """Return True if the user has a usable (hashed) password set.

        False for OAuth-only and guest accounts (set_unusable_password was called).
        Frontend uses this to show "Set Password" vs "Change Password" UI.
        """
        return obj.user.has_usable_password()


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
        - is_following: removed with user-to-user follow (SNS-FOLLOW-REMOVE)
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
            'saved_studios_count',
            'handle',
            'role',
            'affiliation',
        ]
        read_only_fields = ['user_id', 'persona_summary']

    def get_saved_studios_count(self, obj):
        # Local import avoids circular dependency:
        # apps.social.serializers already imports from apps.accounts.serializers
        # at module level, so a top-level import here would form a cycle.
        from apps.social.models import ArchitectFollow
        return ArchitectFollow.objects.filter(follower=obj).count()


_HANDLE_RESERVED = frozenset({
    'me', 'admin', 'administrator', 'settings', 'api', 'root', 'support',
    'help', 'null', 'undefined', 'profile', 'user', 'users', 'login',
    'logout', 'auth',
})

# Unified ID regex: Hangul syllables (AC00-D7A3) + Hangul Jamo (1100-11FF, A960-A97F, D7B0-D7FF)
# + ASCII letters (A-Za-z) + digits (0-9) + underscore. No spaces/whitespace.
# Length 2-20 enforced in the body (after NFC normalization).
_HANDLE_RE = re.compile(
    r'^[가-힣ᄀ-ᇿꥠ-꥿ힰ-퟿a-zA-Z0-9_]+$'
)


def validate_handle_value(value, instance=None):
    """Shared handle/unified-ID validation (reused by register + serializer).

    Validates a non-null, non-empty ID string:
      1. NFC-normalize (prevents visually-identical Hangul duplicates).
      2. Regex format check (Hangul + ASCII letters + digits + underscore; NO whitespace).
      3. Length check: 2-20 characters (measured AFTER NFC normalization).
      4. Reserved word check (case-insensitive).
      5. Case-insensitive uniqueness via handle__iexact (exclude `instance` if supplied).

    Raises serializers.ValidationError on any violation.
    Returns the NFC-normalized value on success so callers store the canonical form.

    NOTE: does NOT handle the null/empty case — callers decide whether null
    or empty is acceptable (register: required, serializer: nullable/clearable).

    LOGIN-ONBOARD-1: extended from ASCII-only (^[a-z0-9_]{3,30}$) to
    Hangul + ASCII, length 2-20, NFC-normalized.
    """
    # NFC normalization first — prevents two visually-identical Hangul strings
    # from being treated as different IDs (e.g. composed vs. decomposed Jamo).
    value = unicodedata.normalize('NFC', value)

    # Format regex — no whitespace, only allowed character classes.
    # fullmatch required: re.match with $ accepts a trailing newline, which
    # would allow CRLF injection into URLs/cards.
    if not _HANDLE_RE.fullmatch(value):
        raise serializers.ValidationError(
            'ID may only contain Korean characters, letters, digits, or underscore. '
            'Spaces are not allowed.'
        )

    # Length check after NFC normalization.
    if len(value) < 2 or len(value) > 20:
        raise serializers.ValidationError(
            'ID must be 2-20 characters.'
        )

    # Reserved word check (case-insensitive; Hangul has no case, but ASCII reserved
    # words should still be blocked regardless of case).
    if value.lower() in _HANDLE_RESERVED:
        raise serializers.ValidationError(
            f'"{value}" is a reserved ID.'
        )

    # Case-insensitive uniqueness, excluding the current user so re-saving
    # the same handle doesn't conflict against themselves.
    qs = UserProfile.objects.filter(handle__iexact=value)
    if instance is not None:
        qs = qs.exclude(pk=instance.pk)
    if qs.exists():
        raise serializers.ValidationError('ID already taken.')

    return value


class UserProfileSelfUpdateSerializer(serializers.ModelSerializer):
    """PATCH /api/v1/users/me/ — owner updates editable fields only.

    Excludes counter caches (auto-managed) and avatar_url (separate upload flow,
    future commit). persona_summary is Phase 17 LLM-derived — not user-editable.

    SETTINGS-1: added handle + notifications.
      handle     — public @handle; unique constraint enforced case-insensitively.
                   DRF UniqueValidator suppressed via validators=[] so our
                   validate_handle is the single authority.
      notifications — {category: {push: bool, email: bool}};
                      validated as dict, ≤50 keys, values must be dicts.

    LOGIN-ONBOARD-1: handle and display_name are unified — writing one writes both
      to the same NFC-normalized validated value. The validate_handle path runs the
      new validator (Hangul + ASCII, 2-20 chars); display_name PATCH still accepted
      as a separate field for backward compat, but routes through the same validator.
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
    # Suppress DRF's auto UniqueValidator (case-sensitive, wrong message).
    # validate_handle below handles uniqueness with case-insensitive iexact check.
    handle = serializers.CharField(
        required=False,
        allow_null=True,
        allow_blank=False,
        max_length=30,
        # trim_whitespace=False so validate_handle's fullmatch is the sole
        # authority — a trailing/leading whitespace (e.g. "x\n") must fail the
        # regex check, not get silently stripped then accepted.
        trim_whitespace=False,
        validators=[],
    )

    class Meta:
        model = UserProfile
        fields = [
            'display_name', 'bio', 'mbti', 'external_links',
            'theme', 'font', 'language', 'onboarding_role',
            'handle', 'notifications', 'role', 'affiliation',
        ]

    def validate_display_name(self, value):
        """display_name: run through unified-ID validator when non-empty.

        LOGIN-ONBOARD-1: display_name == handle (unified ID). When
        display_name is updated, it is validated as an ID and will sync to
        handle in update(). Whitespace-only / empty still rejected.
        """
        if value is None:
            return value
        stripped = value.strip()
        if len(stripped) == 0:
            raise serializers.ValidationError(
                'display_name cannot be whitespace-only.'
            )
        # Delegate to unified validator (NFC + format + length + reserved + unique).
        return validate_handle_value(stripped, instance=self.instance)

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

    def validate_handle(self, value):
        """handle: Hangul/ASCII/digits/underscore, 2-20 chars, unique, not reserved.

        Validation order:
          1. null/empty → allow (clears the handle).
          2-5. Delegated to validate_handle_value() (shared with register endpoint).
             2. NFC normalize.
             3. Regex format check (no whitespace, Hangul + ASCII + digits + _).
             4. Length check: 2-20 chars.
             5. Reserved words.
             6. Case-insensitive uniqueness, excluding the current user (self-save OK).
        """
        if value is None:
            return value

        return validate_handle_value(value, instance=self.instance)

    def update(self, instance, validated_data):
        """Sync handle == display_name on every write (LOGIN-ONBOARD-1).

        Whichever of handle/display_name was supplied, write both columns to
        the same NFC-normalized validated value. If both are supplied and
        disagree (after normalization), raise ValidationError — callers should
        send a single unified ID field.
        """
        handle = validated_data.get('handle')
        display_name = validated_data.get('display_name')

        # Determine the unified ID value to use.
        if handle is not None and display_name is not None:
            if handle != display_name:
                # Both supplied and differ — reject rather than silently pick one.
                raise serializers.ValidationError(
                    {'handle': 'handle and display_name must be equal (unified ID).'}
                )
            unified = handle
        elif handle is not None:
            unified = handle
        elif display_name is not None:
            unified = display_name
        else:
            unified = None

        if unified is not None:
            validated_data['handle'] = unified
            validated_data['display_name'] = unified

        return super().update(instance, validated_data)

    def validate_notifications(self, value):
        """notifications: {category: {push?: bool, email?: bool}}.

        Constraints:
          - Top level must be a dict, ≤50 keys.
          - Each value must be a dict containing ONLY the keys 'push' and/or
            'email'; unknown nested keys are rejected.
          - Values under 'push'/'email' must be booleans (JSON true/false).
            Integers are NOT accepted — isinstance(1, bool) is False for int
            literals, but JSON 1/0 parse to int not bool, so int values are
            correctly rejected by the isinstance(v, bool) guard.

        Returns value unchanged (no normalisation) so reload equals the input.
        """
        _ALLOWED_NESTED = frozenset({'push', 'email'})

        if not isinstance(value, dict):
            raise serializers.ValidationError(
                'notifications must be an object.'
            )
        if len(value) > 50:
            raise serializers.ValidationError(
                'notifications must have 50 keys or fewer.'
            )
        for k, v in value.items():
            if not isinstance(k, str) or len(k) > 64:
                raise serializers.ValidationError(
                    'notifications keys must be strings of 64 chars or fewer.'
                )
            if not isinstance(v, dict):
                raise serializers.ValidationError(
                    f'notifications["{k}"] must be an object.'
                )
            unknown = set(v.keys()) - _ALLOWED_NESTED
            if unknown:
                raise serializers.ValidationError(
                    f'notifications["{k}"] contains unknown keys: '
                    f'{sorted(unknown)}. Allowed: push, email.'
                )
            for nested_key, nested_val in v.items():
                if not isinstance(nested_val, bool):
                    raise serializers.ValidationError(
                        f'notifications["{k}"]["{nested_key}"] must be a boolean.'
                    )
        return value
