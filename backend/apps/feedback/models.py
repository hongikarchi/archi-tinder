"""Taste-start feedback reports (TASTE-FEEDBACK-1).

Rows are written by the API and reviewed by the DB owner with SQL; there is no
admin UI and no user-facing status. `status` is the owner's review state.
"""
from django.db import models

from apps.accounts.models import UserProfile

STATUS_CHOICES = [
    ('unreviewed', 'Unreviewed'),
    ('fixed', 'Fixed'),
    ('not_fixed', 'Not fixed'),
    ('user_canceled', 'User canceled'),
]


class FeedbackReportBase(models.Model):
    user = models.ForeignKey(
        UserProfile, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='%(class)ss',
    )
    round_key = models.CharField(max_length=64)       # client round id, e.g. r1760340000000
    query_text = models.TextField()
    tags = models.JSONField(default=list)             # canonical tag dicts (+ client prob)
    source = models.CharField(max_length=16, choices=[('jev', 'JEV'), ('dictionary', 'Dictionary')])
    comment = models.TextField(blank=True, default='')
    language = models.CharField(max_length=8, choices=[('ko', 'Korean'), ('en', 'English')])
    status = models.CharField(max_length=16, choices=STATUS_CHOICES, default='unreviewed', db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class CardReport(FeedbackReportBase):
    REASON_CHOICES = [('tag', 'Tag'), ('photo', 'Photo'), ('info', 'Info'), ('etc', 'Etc')]

    canonical_bld_id = models.CharField(max_length=20)
    card_rank = models.PositiveSmallIntegerField()    # 1-3
    hit = models.PositiveSmallIntegerField()
    total = models.PositiveSmallIntegerField()
    reason = models.CharField(max_length=8, choices=REASON_CHOICES, null=True, blank=True)
    sub_reasons = models.JSONField(default=list)
    wrong_tags = models.JSONField(default=list)       # [{axis, value, matched, matched_via, direction}]
    building_snapshot = models.JSONField(default=dict)

    class Meta:
        db_table = 'feedback_card_report'
        constraints = [
            models.UniqueConstraint(
                fields=['user', 'round_key', 'canonical_bld_id'],
                name='uniq_card_report_user_round_bld'),
        ]


class QueryReport(FeedbackReportBase):
    wrong_tags = models.JSONField(default=list)       # [{axis, value}]

    class Meta:
        db_table = 'feedback_query_report'
        constraints = [
            models.UniqueConstraint(
                fields=['user', 'round_key'],
                name='uniq_query_report_user_round'),
        ]
