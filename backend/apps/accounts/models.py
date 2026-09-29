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
    # SETTINGS-POLISH-1: single source of truth for the role list's Korean
    # labels. Keys MUST mirror ONBOARDING_ROLE_CHOICES keys — adding a new
    # role + its ko label here is the ONLY edit needed to propagate a new
    # role everywhere (GET /api/v1/meta/roles/ derives from both).
    ONBOARDING_ROLE_LABELS_KO = {
        'student': '학생',
        'architect': '건축가',
        'designer': '디자이너',
        'enthusiast': '건축 애호가',
        'other': '기타',
    }

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


class PersonalityProfile(models.Model):
    """Personality assessment result for a UserProfile.

    Stores 5 axis scores (each -1.0 to +1.0) derived from a 20-question
    Likert assessment (-2 to +2 per question, 4 questions per axis).
    type_code is a 4-letter code from axes 1-4 (axis_5 is a bonus dimension
    that does not affect type_code).

    Axis semantics:
      axis_1: C(Conceptual) > 0.0, R(Real) <= 0.0
      axis_2: L(Leader)     > 0.0, S(Supporter) <= 0.0
      axis_3: O(cOllaborative) > 0.0, D(inDependent) <= 0.0
      axis_4: N(iNnovative) > 0.0, T(Traditional) <= 0.0
      axis_5: bonus — P(Prudent/신중) > 0.0, I(Improvisational/즉흥) <= 0.0

    discovery_opt_in controls visibility in the people-discovery feed.
    """
    user = models.OneToOneField(
        UserProfile, on_delete=models.CASCADE, related_name='personality'
    )
    axis_1 = models.FloatField()   # 개념(+) / 실무(-)
    axis_2 = models.FloatField()   # 리더(+) / 서포터(-)
    axis_3 = models.FloatField()   # 협업(+) / 독립(-)
    axis_4 = models.FloatField()   # 혁신(+) / 전통(-)
    axis_5 = models.FloatField()   # 신중(+) / 즉흥(-) [보너스 — type_code 미영향]
    type_code = models.CharField(max_length=4)
    discovery_opt_in = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(fields=['discovery_opt_in'], name='personality_optin_idx'),
        ]

    def __str__(self):
        return f'{self.user_id}:{self.type_code}'


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
