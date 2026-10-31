"""
models.py -- apps/contests

Real-contest data for the /competitions screen (replaces the frontend mock).
Design record: docs/decisions/2026-10-09-contest-real-data.md (D7-D9, §4-1).

Only the 'default' DB is used. The Make-DB building DB is never touched.
interest_count is a denormalized column maintained by signals on ContestInterest
(apps/contests/signals.py, BACK-CONTEST-2).
"""
import contextvars

from django.core.exceptions import ValidationError
from django.db import models, transaction
from django.db.models import Q

from .validators import validate_http_url, validate_poster_url, validate_publishable

URL_FIELDS = ('source_url', 'listing_url', 'poster_url')
# DB-level scheme check (case-insensitive, matching validators.is_http_url which
# lower-cases the scheme). The constraint checks the scheme prefix only; the
# validator additionally requires a host and no surrounding whitespace.
_HTTP_RE = r'^https?://'


def _validate_url_value(name, value):
    """Same semantics as Contest.save(): blank source/listing_url, null poster_url OK."""
    if value in (None, ''):
        return
    try:
        if name == 'poster_url':
            validate_poster_url(value)
        else:
            validate_http_url(value)
    except ValidationError as exc:
        # Field-keyed so API callers see {"<field>": [...]} instead of non_field_errors.
        raise ValidationError({name: exc.messages}, code=getattr(exc, 'code', None))


# Django's bulk_update() issues an internal queryset.update() with Case/When
# expressions; bulk_update() already validated every object, so that inner call
# must skip the update() expression guard.
_IN_BULK_UPDATE = contextvars.ContextVar('contest_in_bulk_update', default=False)


class ContestQuerySet(models.QuerySet):
    """Applies the URL guard and the publish rule to bulk paths that skip Contest.save().

    Publish rule (validators.validate_publishable): a 'published' contest needs a
    non-empty official http(s) source_url that is not a listing-site domain.
    All errors are field-keyed; publish-rule errors are keyed to 'source_url' (the
    field the operator must fix), not 'status'.
    """

    def bulk_create(self, objs, *args, **kwargs):
        objs = list(objs)
        for obj in objs:
            for name in URL_FIELDS:
                _validate_url_value(name, getattr(obj, name))
            validate_publishable(obj.status, obj.source_url)
        return super().bulk_create(objs, *args, **kwargs)

    def bulk_update(self, objs, fields, *args, **kwargs):
        objs = list(objs)
        fields = list(fields)
        for name in URL_FIELDS:
            if name in fields:
                for obj in objs:
                    _validate_url_value(name, getattr(obj, name))
        if 'status' in fields or 'source_url' in fields:
            for obj in objs:
                validate_publishable(obj.status, obj.source_url)
        token = _IN_BULK_UPDATE.set(True)
        try:
            return super().bulk_update(objs, fields, *args, **kwargs)
        finally:
            _IN_BULK_UPDATE.reset(token)

    def update(self, **kwargs):
        for name in URL_FIELDS:
            if name in kwargs:
                value = kwargs[name]
                # Expressions (F(), Value(), ...) cannot be checked here; the
                # DB CheckConstraint still covers them. (status/source_url
                # expressions are rejected outright below.)
                if value is None or isinstance(value, str):
                    _validate_url_value(name, value)
        if _IN_BULK_UPDATE.get() or ('status' not in kwargs and 'source_url' not in kwargs):
            return super().update(**kwargs)
        for name in ('status', 'source_url'):
            if name in kwargs and not (kwargs[name] is None or isinstance(kwargs[name], str)):
                raise ValidationError(
                    {name: 'Expressions are not supported when updating %s through '
                           'Contest.objects.update(); use a plain value.' % name},
                    code='unsupported_expression',
                )
        # Check + write in one transaction so the checked rows are the written rows
        # (the DB CHECK constraint backstops the blank-source case under races).
        with transaction.atomic(using=self.db):
            self._check_publish_rule_for_update(kwargs)
            return super().update(**kwargs)

    def _check_publish_rule_for_update(self, kwargs):
        new_status = kwargs.get('status')
        if 'status' in kwargs:
            if new_status != Contest.STATUS_PUBLISHED:
                return  # nothing is published afterwards -> no requirement
            if 'source_url' in kwargs:
                validate_publishable(new_status, kwargs['source_url'] or '')
            else:
                # Every targeted row becomes published with its CURRENT source_url.
                for value in self.values_list('source_url', flat=True).distinct():
                    validate_publishable(new_status, value)
            return
        # Only source_url changes: rows that are currently published must stay valid.
        if self.filter(status=Contest.STATUS_PUBLISHED).exists():
            validate_publishable(Contest.STATUS_PUBLISHED, kwargs['source_url'] or '')


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

    # Stable identifier a collector can use as an idempotent de-dup key (title/URL
    # can change); NULL for rows created otherwise.
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

    source_url = models.URLField(
        max_length=500, blank=True, default='', validators=[validate_http_url],
    )
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
                condition=Q(source_url='') | Q(source_url__iregex=_HTTP_RE),
                name='contest_source_url_http',
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
            # Published needs a source URL. Only the blank case can live in the DB;
            # the "not a listing-site domain" half of the publish rule is ORM-level
            # (validators.validate_publishable) because a host list does not belong
            # in a CHECK constraint.
            models.CheckConstraint(
                condition=~Q(status='published', source_url=''),
                name='contest_published_has_source',
            ),
        ]

    def __str__(self):
        return self.title

    def save(self, *args, **kwargs):
        # Django validators do not run on save(); enforce http/https here so
        # update_or_create / commands / importers cannot store a bad URL.
        # Blank source_url / listing_url and null poster_url stay allowed.
        for name in URL_FIELDS:
            _validate_url_value(name, getattr(self, name))
        validate_publishable(self.status, self.source_url)
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
