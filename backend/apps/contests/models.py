"""
models.py -- apps/contests

Real-contest data for the /competitions screen (replaces the frontend mock).
Design record: docs/decisions/2026-10-09-contest-real-data.md (D7-D9, §4-1).

Only the 'default' DB is used. The Make-DB building DB is never touched.
interest_count is a denormalized column maintained by signals on ContestInterest
(apps/contests/signals.py, BACK-CONTEST-2).
"""
from django.db import models
from django.db.models import Q

from .validators import validate_http_url, validate_poster_url

URL_FIELDS = ('source_url', 'listing_url', 'poster_url')
# DB-level scheme check (case-insensitive, matching validators.is_http_url which
# lower-cases the scheme). The constraint checks the scheme prefix only; the
# validator additionally requires a host and no surrounding whitespace.
_HTTP_RE = r'^https?://'


def _validate_url_value(name, value):
    """Same semantics as Contest.save(): blank listing_url / null poster_url OK."""
    if value in (None, '') and name != 'source_url':
        return
    if name == 'poster_url':
        validate_poster_url(value)
        return
    validate_http_url(value)


class ContestQuerySet(models.QuerySet):
    """Applies the http(s)-only URL guard to bulk paths that skip Contest.save()."""

    def bulk_create(self, objs, *args, **kwargs):
        objs = list(objs)
        for obj in objs:
            for name in URL_FIELDS:
                _validate_url_value(name, getattr(obj, name))
        return super().bulk_create(objs, *args, **kwargs)

    def bulk_update(self, objs, fields, *args, **kwargs):
        objs = list(objs)
        fields = list(fields)
        for name in URL_FIELDS:
            if name in fields:
                for obj in objs:
                    _validate_url_value(name, getattr(obj, name))
        return super().bulk_update(objs, fields, *args, **kwargs)

    def update(self, **kwargs):
        for name in URL_FIELDS:
            if name in kwargs:
                value = kwargs[name]
                # Expressions (F(), Value(), ...) cannot be checked here; the
                # DB CheckConstraint still covers them.
                if value is None or isinstance(value, str):
                    _validate_url_value(name, value)
        return super().update(**kwargs)


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

    STATUS_PUBLISHED = 'published'
    STATUS_HIDDEN = 'hidden'
    STATUS_PENDING = 'pending'
    STATUS_CHOICES = [
        (STATUS_PUBLISHED, 'published'),
        (STATUS_HIDDEN, 'hidden'),
        (STATUS_PENDING, 'pending'),
    ]

    # Stable identifier used by the upcoming `import_contests` command to upsert
    # rows idempotently (title/URL can change); NULL for rows created otherwise.
    # NULLs do not collide under the unique constraint.
    import_key = models.CharField(max_length=80, unique=True, null=True, blank=True)

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

    source_url = models.URLField(max_length=500, validators=[validate_http_url])
    listing_source = models.CharField(max_length=40, blank=True)
    listing_url = models.URLField(max_length=500, blank=True, validators=[validate_http_url])

    poster_url = models.URLField(
        max_length=1000, null=True, blank=True, validators=[validate_poster_url],
    )
    poster_credit = models.CharField(max_length=120, blank=True)

    status = models.CharField(
        max_length=10, choices=STATUS_CHOICES, default=STATUS_HIDDEN, db_index=True,
    )
    interest_count = models.PositiveIntegerField(default=0)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    last_verified_at = models.DateTimeField(null=True, blank=True)

    objects = ContestQuerySet.as_manager()

    class Meta:
        ordering = ['submission_deadline']
        indexes = [
            models.Index(
                fields=['status', 'submission_deadline'],
                name='contest_status_deadline_idx',
            ),
        ]
        constraints = [
            models.CheckConstraint(
                condition=Q(source_url__iregex=_HTTP_RE), name='contest_source_url_http',
            ),
            models.CheckConstraint(
                condition=Q(listing_url='') | Q(listing_url__iregex=_HTTP_RE),
                name='contest_listing_url_http',
            ),
            models.CheckConstraint(
                condition=(
                    Q(poster_url__isnull=True) | Q(poster_url='')
                    | Q(poster_url__iregex=_HTTP_RE)
                ),
                name='contest_poster_url_http',
            ),
        ]

    def __str__(self):
        return self.title

    def save(self, *args, **kwargs):
        # Django validators do not run on save(); enforce http/https here so
        # update_or_create / commands / importers cannot store a bad URL.
        # Blank listing_url and null poster_url stay allowed.
        for name in URL_FIELDS:
            _validate_url_value(name, getattr(self, name))
        super().save(*args, **kwargs)

    def next_deadline(self, now):
        """Return (kind, datetime) per D9 for the given `now`."""
        return compute_next_deadline(self.apply_deadline, self.submission_deadline, now)


class ContestInterest(models.Model):
    """A user's "interested" mark on a contest. Mirrors social.Reaction.

    Contest.interest_count is maintained by signals (apps/contests/signals.py).
    """
    user = models.ForeignKey(
        'accounts.UserProfile',
        on_delete=models.CASCADE,
        related_name='contest_interests',
    )
    contest = models.ForeignKey(
        Contest,
        on_delete=models.CASCADE,
        related_name='interests',
    )
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        unique_together = [('user', 'contest')]
        indexes = [
            models.Index(fields=['contest', '-created_at'], name='contest_int_contest_idx'),
        ]

    def __str__(self):
        return f'{self.user_id} -> contest:{self.contest_id}'
