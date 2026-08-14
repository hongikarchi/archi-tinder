"""apps.works.models — Work model (user-uploaded architectural works).

FULL-WORKS-1: each Work is a portfolio entry uploaded by a UserProfile.
upload_id follows the 'usr_NNNNNN' format; it is generated once at creation
and never changes.
"""
from django.db import models

from apps.accounts.models import UserProfile

# 14 canonical programs — identical to canonical_v2_buildings.program vocabulary.
PROGRAM_CHOICES = [
    ('residential',    'Residential'),
    ('commercial',     'Commercial'),
    ('cultural',       'Cultural'),
    ('educational',    'Educational'),
    ('healthcare',     'Healthcare'),
    ('hospitality',    'Hospitality'),
    ('industrial',     'Industrial'),
    ('infrastructure', 'Infrastructure'),
    ('landscape',      'Landscape'),
    ('mixed_use',      'Mixed Use'),
    ('office',         'Office'),
    ('public',         'Public'),
    ('religious',      'Religious'),
    ('sports',         'Sports'),
]


class Work(models.Model):
    owner = models.ForeignKey(
        UserProfile,
        on_delete=models.CASCADE,
        related_name='works',
    )
    # 'usr_000001' format — generated once at creation, never mutated.
    upload_id = models.CharField(max_length=20, unique=True)
    title = models.CharField(max_length=200)
    program = models.CharField(max_length=20, choices=PROGRAM_CHOICES)
    location_city = models.CharField(max_length=100, blank=True)
    location_country = models.CharField(max_length=100, blank=True)
    project_year = models.IntegerField(null=True, blank=True)
    # list[str] — Cloudflare R2 object keys for this work's images.
    r2_keys = models.JSONField(default=list)
    # Optional explicit cover key. When set, cover_url uses this key instead
    # of r2_keys[0]. Empty string means "use r2_keys[0]" (backwards compat).
    cover_r2_key = models.CharField(max_length=512, blank=True, default='')
    is_copyright_confirmed = models.BooleanField(default=False)
    # Publishable gate: set True by _process_work after Gemini validation.
    is_publishable = models.BooleanField(default=False)
    # Reason for gate failure (empty string when published).
    gate_reason = models.CharField(max_length=500, blank=True)
    report_count = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['owner', 'is_publishable']),
        ]

    def __str__(self):
        return f'{self.upload_id}: {self.title}'

    @classmethod
    def generate_upload_id(cls):
        """Return a unique 'usr_<hex10>' upload ID.

        Uses uuid4 hex suffix instead of a count-based integer to avoid the
        TOCTOU race where two concurrent requests read the same count and
        collide on the unique=True constraint (FULL-WORKS-1 fix).
        """
        from uuid import uuid4
        return 'usr_' + uuid4().hex[:10]
