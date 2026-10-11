"""
signals.py -- apps/contests

Single source of truth for Contest.interest_count (mirrors the Reaction
counter in apps/social/models.py). CASCADE deletes of a user also fire
post_delete, so the counter cannot drift.
"""
from django.db.models import F
from django.db.models.functions import Greatest
from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

from .models import Contest, ContestInterest


@receiver(post_save, sender=ContestInterest)
def _interest_post_save(sender, instance, created, **kwargs):
    if not created:
        return
    Contest.objects.filter(pk=instance.contest_id).update(
        interest_count=F('interest_count') + 1,
    )


@receiver(post_delete, sender=ContestInterest)
def _interest_post_delete(sender, instance, **kwargs):
    # Greatest(..., 0) keeps the counter non-negative under drift / races.
    Contest.objects.filter(pk=instance.contest_id).update(
        interest_count=Greatest(F('interest_count') - 1, 0),
    )
