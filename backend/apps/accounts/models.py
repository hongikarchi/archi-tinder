from django.db import models
from django.contrib.auth.models import User


class UserProfile(models.Model):
    THEME_CHOICES = [
        ('github-light', 'GitHub Light'),
        ('github-dark', 'GitHub Dark'),
        ('ayu-light', 'Ayu Light'),
        ('synthwave-84', "SynthWave '84"),
    ]
    FONT_CHOICES = [
        ('plex', 'IBM Plex Sans KR'),
        ('noto-serif', 'Noto Serif KR'),
    ]
    LANGUAGE_CHOICES = [
        ('ko', 'Korean'),
        ('en', 'English'),
    ]
    ONBOARDING_ROLE_CHOICES = [
        ('student',    'Student'),
        ('architect',  'Architect'),
        ('designer',   'Designer'),
        ('enthusiast', 'Architecture Enthusiast'),
        ('other',      'Other'),
    ]

    # -- Existing fields (PROF1 baseline) --
    user         = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    display_name = models.CharField(max_length=100)
    avatar_url   = models.URLField(null=True, blank=True)
    created_at   = models.DateTimeField(auto_now_add=True)
    updated_at   = models.DateTimeField(auto_now=True)

    # -- Phase 13 PROF2 extensions --
    bio = models.TextField(
        blank=True,
        max_length=500,
        # Short prose self-description (~100-200 chars typical, 500 hard cap).
        # NOT required at signup. NOT required for public profile.
    )
    mbti = models.CharField(
        max_length=4,
        blank=True,
        # Opt-in personality marker (e.g. "INTJ"). Hidden when blank.
        # Privacy-sensitive — NEVER auto-populated; user must affirmatively set.
    )
    external_links = models.JSONField(
        default=dict,
        blank=True,
        # {"instagram": "@handle", "email": "user@example.com", "website": "https://..."}
        # email visibility gate UX deferred to post-Phase 17 designer dialogue.
    )
    persona_summary = models.JSONField(
        default=dict,
        blank=True,
        # {persona_type, one_liner, styles[], programs[]} — Phase 17 LLM-derived (future).
        # Empty dict at PROF2 v0; populated by Phase 17 reverse-Q classifier later.
    )
    # -- App-preference fields (design-system PR2) --
    theme = models.CharField(max_length=20, choices=THEME_CHOICES, default='github-light')
    font = models.CharField(max_length=20, choices=FONT_CHOICES, default='plex')
    language = models.CharField(max_length=5, choices=LANGUAGE_CHOICES, default='ko')

    # -- Guest-first auth / terminal onboarding (FULL-LOGIN-REDESIGN-1) --
    is_guest = models.BooleanField(default=False)
    onboarding_role = models.CharField(
        max_length=20,
        choices=ONBOARDING_ROLE_CHOICES,
        blank=True,
        default='',
    )
    consent_accepted_at = models.DateTimeField(null=True, blank=True)
    consent_policy_version = models.CharField(max_length=10, default='1.0')

    # -- Discovery right-swipe liked buildings (SNS-LIKED-PROJECTS) --
    liked_building_ids = models.JSONField(
        default=list,
        blank=True,
        # list[str] — canonical_bld_id strings from Discovery right-swipe.
        # Ordered newest-first (prepend on add). Deduped. Capped at 200 in view.
    )

    # -- Profile IA redesign (SETTINGS-2) --
    role = models.CharField(
        max_length=50,
        blank=True,
        default='',
        # Free-text job role / title (e.g. "Architecture Student").
        # NOT the onboarding_role enum. Never auto-populated; user sets explicitly.
    )
    affiliation = models.CharField(
        max_length=100,
        blank=True,
        default='',
        # Free-text affiliation / institution (e.g. "Korea University").
        # Displayed as the secondary line in the profile hero.
    )

    # -- AUTH-LOGIN-1: handle+password auth + email verify via OAuth linking --
    email_verified_at = models.DateTimeField(
        null=True,
        blank=True,
        # Set when the user successfully completes link-email (E2) with a
        # verified OAuth provider email.  Null = email not yet verified.
    )

    # -- Settings harvest (SETTINGS-1) --
    handle = models.CharField(
        max_length=30,
        unique=True,
        null=True,
        blank=True,
        # Public @handle (e.g. 'dain_architect'). LOGIN-ONBOARD-1: unified with display_name
        # (handle == display_name, written together at every write path).
        # null until the user sets one. Postgres unique allows multiple NULLs.
        # Validated by validate_handle_value(): NFC-normalized, Hangul+ASCII letters/digits/underscore, 2-20 chars.
    )
    notifications = models.JSONField(
        default=dict,
        blank=True,
        # {category: {push: bool, email: bool}} — per-category notification prefs.
        # No DB-level schema; serializer validates dict shape (≤50 keys, values are dicts).
    )

    def __str__(self):
        return self.display_name


class SocialAccount(models.Model):
    PROVIDER_CHOICES = [
        ('google', 'Google'),
        ('kakao',  'Kakao'),
        ('naver',  'Naver'),
    ]
    user        = models.ForeignKey(UserProfile, on_delete=models.CASCADE, related_name='social_accounts')
    provider    = models.CharField(max_length=20, choices=PROVIDER_CHOICES)
    provider_id = models.CharField(max_length=200)
    created_at  = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('provider', 'provider_id')

    def __str__(self):
        return f'{self.provider}:{self.provider_id}'
