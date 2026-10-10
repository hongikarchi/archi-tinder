"""
models.py -- apps/contests

Real-contest data for the /competitions screen (replaces the frontend mock).
Design record: docs/decisions/2026-10-09-contest-real-data.md (D7-D9, §4-1).

Only the 'default' DB is used. The Make-DB building DB is never touched.
interest_count is a denormalized column maintained by the interest API (PR 2);
in this PR it is just a column.
"""
from django.db import models


def compute_next_deadline(apply_deadline, submission_deadline, now):
    """D9: nearest remaining deadline.

    Returns ('apply', apply_deadline) when apply_deadline is set and still in
    the future, otherwise ('submission', submission_deadline). Pure function
    (takes `now`) so it is unit-testable without freezing the clock.
    """
    if apply_deadline is not None and apply_deadline > now:
        return 'apply', apply_deadline
    return 'submission', submission_deadline


class Contest(models.Model):
    ORGANIZER_PUBLIC_AGENCY = 'public_agency'
    ORGANIZER_ASSOCIATION = 'association'
    ORGANIZER_LOCAL_GOV = 'local_gov'
    ORGANIZER_PRIVATE_GROUP = 'private_group'
    ORGANIZER_UNKNOWN = 'unknown'
    ORGANIZER_TYPE_CHOICES = [
        (ORGANIZER_PUBLIC_AGENCY, 'public_agency'),
        (ORGANIZER_ASSOCIATION, 'association'),
        (ORGANIZER_LOCAL_GOV, 'local_gov'),
        (ORGANIZER_PRIVATE_GROUP, 'private_group'),
        (ORGANIZER_UNKNOWN, 'unknown'),
    ]

    POSTER_ALLOWED = 'allowed'
    POSTER_UNVERIFIED = 'unverified'
    POSTER_NONE = 'none'
    POSTER_STATUS_CHOICES = [
        (POSTER_ALLOWED, 'allowed'),
        (POSTER_UNVERIFIED, 'unverified'),
        (POSTER_NONE, 'none'),
    ]

    STATUS_PUBLISHED = 'published'
    STATUS_HIDDEN = 'hidden'
    STATUS_PENDING = 'pending'
    STATUS_CHOICES = [
        (STATUS_PUBLISHED, 'published'),
        (STATUS_HIDDEN, 'hidden'),
        (STATUS_PENDING, 'pending'),
    ]

    title = models.CharField(max_length=200)
    organizer = models.CharField(max_length=120)
    organizer_type = models.CharField(
        max_length=20, choices=ORGANIZER_TYPE_CHOICES, default=ORGANIZER_UNKNOWN,
    )

    # Final work submission deadline (list cut-off).
    submission_deadline = models.DateTimeField(db_index=True)
    # Only when the participation-application deadline differs from submission.
    apply_deadline = models.DateTimeField(null=True, blank=True)
    notice_date = models.DateField(null=True, blank=True)

    theme = models.CharField(max_length=200, blank=True)
    summary = models.CharField(max_length=300, blank=True)
    eligibility = models.CharField(max_length=120, blank=True)
    team_size = models.CharField(max_length=60, null=True, blank=True)

    source_url = models.URLField(max_length=500)
    listing_source = models.CharField(max_length=40, blank=True)
    listing_url = models.URLField(max_length=500, blank=True)

    poster_url = models.URLField(max_length=1000, null=True, blank=True)
    poster_credit = models.CharField(max_length=120, blank=True)
    poster_status = models.CharField(
        max_length=12, choices=POSTER_STATUS_CHOICES, default=POSTER_UNVERIFIED,
    )

    status = models.CharField(
        max_length=10, choices=STATUS_CHOICES, default=STATUS_HIDDEN, db_index=True,
    )
    interest_count = models.PositiveIntegerField(default=0)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    last_verified_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['submission_deadline']
        indexes = [
            models.Index(
                fields=['status', 'submission_deadline'],
                name='contest_status_deadline_idx',
            ),
        ]

    def __str__(self):
        return self.title

    def next_deadline(self, now):
        """Return (kind, datetime) per D9 for the given `now`."""
        return compute_next_deadline(self.apply_deadline, self.submission_deadline, now)
