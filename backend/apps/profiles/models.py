import uuid
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models


class Office(models.Model):
    office_id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.TextField()                               # canonical display name
    aliases = models.JSONField(default=list)                # ["OMA", "Office for Metropolitan Architecture", ...]
    # Using JSONField instead of ArrayField for SQLite test compat; semantics identical (list of strings).
    verified = models.BooleanField(default=False)           # blue-mark

    CLAIM_CHOICES = [
        ('unclaimed', 'Unclaimed'),
        ('pending', 'Pending Verification'),
        ('verified', 'Verified'),
        ('rejected', 'Rejected'),
    ]
    claim_status = models.CharField(max_length=20, choices=CLAIM_CHOICES, default='unclaimed')

    contact_email = models.EmailField(blank=True)
    website = models.URLField(blank=True)
    logo_url = models.URLField(blank=True)
    description = models.TextField(blank=True)    # company description (matches MOCK_OFFICE.description)
    location = models.TextField(blank=True)       # "Rotterdam, Netherlands" (matches MOCK_OFFICE.location)
    founded_year = models.IntegerField(null=True, blank=True)  # matches MOCK_OFFICE.founded_year

    # Make DB integration — primary join key per B1 refinement (Inv 19 §3 + infra/03 §6)
    canonical_id = models.IntegerField(null=True, blank=True, db_index=True)
    # mirrors architecture_vectors.architect_canonical_ids[] when matched.
    # Sparse today (Divisare-only); populated by Make DB cleanup.

    # Phase 15 SOC1 placeholders (counter caches; Follow events will update)
    follower_count = models.IntegerField(default=0)
    following_count = models.IntegerField(default=0)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(fields=['name']),
            models.Index(fields=['claim_status']),
        ]

    def __str__(self):
        return f'{self.name} ({"verified" if self.verified else self.claim_status})'


class OfficeProjectLink(models.Model):
    """Links Office to a building in architecture_vectors (Make DB owned).

    Per B1 refinement: 4-tier resolution priority:
      1. canonical_fk: Office.canonical_id matches architecture_vectors.architect_canonical_ids[]
      2. manual: user claimed; admin verified
      3. string_match: Levenshtein + token-set similarity vs Office.name + aliases
      4. (unmatched buildings have no row in this table)
    """
    SOURCE_CHOICES = [
        ('manual', 'Manual Claim'),           # user submitted, admin verified, confidence 1.0
        ('canonical_fk', 'Canonical FK'),     # Make DB architect_canonical_ids match, confidence 1.0
        ('string_match', 'String Match'),     # Levenshtein + token similarity, confidence 0-0.99
        ('admin_assigned', 'Admin Assigned'),  # admin override, confidence 1.0
    ]

    link_id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    office = models.ForeignKey(Office, on_delete=models.CASCADE, related_name='project_links')
    building_id = models.TextField(db_index=True)   # -> architecture_vectors.building_id (TEXT, 'B00042' format)
    confidence = models.FloatField(
        validators=[MinValueValidator(0.0), MaxValueValidator(1.0)],
    )                                               # 1.0 for manual/canonical_fk/admin; 0-0.99 for string_match
    source = models.CharField(max_length=20, choices=SOURCE_CHOICES)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = [('office', 'building_id')]
        indexes = [
            models.Index(fields=['building_id']),
            models.Index(fields=['source']),
        ]

    def __str__(self):
        return f'{self.office.name} -> {self.building_id} ({self.source} {self.confidence:.2f})'
