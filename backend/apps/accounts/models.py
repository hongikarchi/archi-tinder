from django.db import models
from django.contrib.auth.models import User


class UserProfile(models.Model):
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
    follower_count = models.IntegerField(
        default=0,
        # Counter cache; Phase 15 SOC1 Follow events will increment/decrement.
    )
    following_count = models.IntegerField(
        default=0,
        # Counter cache; mirror of follower_count (opposite direction).
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
