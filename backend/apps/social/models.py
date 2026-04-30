from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import F, Q
from django.db.models.functions import Greatest
from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver


class Follow(models.Model):
    """Asymmetric user-to-user follow relationship (Phase 15 SOC1).

    follower follows followee.
    Counter caches (UserProfile.follower_count / following_count) are updated
    via Django signals (post_save / post_delete) — single source of truth that
    also covers CASCADE deletes without any additional view-layer plumbing.
    """
    follower = models.ForeignKey(
        'accounts.UserProfile',
        on_delete=models.CASCADE,
        related_name='following_set',
    )
    followee = models.ForeignKey(
        'accounts.UserProfile',
        on_delete=models.CASCADE,
        related_name='follower_set',
    )
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        unique_together = [('follower', 'followee')]
        indexes = [
            models.Index(fields=['followee', '-created_at']),
        ]
        constraints = [
            models.CheckConstraint(
                check=~Q(follower=F('followee')),
                name='social_follow_no_self_follow',
            ),
        ]

    def clean(self):
        """Application-level guard for admin form validation."""
        if self.follower_id == self.followee_id:
            raise ValidationError('Cannot follow yourself.')

    def __str__(self):
        return f'{self.follower_id} -> {self.followee_id}'


# ---------------------------------------------------------------------------
# Counter signals — single source of truth for follower_count / following_count
# ---------------------------------------------------------------------------

@receiver(post_save, sender=Follow)
def _follow_post_save(sender, instance, created, **kwargs):
    """Increment counters when a new Follow row is created."""
    if not created:
        return
    from apps.accounts.models import UserProfile
    UserProfile.objects.filter(pk=instance.follower_id).update(
        following_count=F('following_count') + 1,
    )
    UserProfile.objects.filter(pk=instance.followee_id).update(
        follower_count=F('follower_count') + 1,
    )


@receiver(post_delete, sender=Follow)
def _follow_post_delete(sender, instance, **kwargs):
    """Decrement counters when a Follow row is deleted (incl. CASCADE).

    Greatest(..., 0) prevents the counter from going negative if a concurrent
    delete races or counters are otherwise out of sync.
    """
    from apps.accounts.models import UserProfile
    UserProfile.objects.filter(pk=instance.follower_id).update(
        following_count=Greatest(F('following_count') - 1, 0),
    )
    UserProfile.objects.filter(pk=instance.followee_id).update(
        follower_count=Greatest(F('follower_count') - 1, 0),
    )


# ---------------------------------------------------------------------------
# Reaction model -- Phase 15 SOC2
# ---------------------------------------------------------------------------

class Reaction(models.Model):
    """Single-tier ❤️ reaction on a Project (Board) — Phase 15 SOC2.

    `reaction_count` on Project is maintained via post_save / post_delete signals
    (same pattern as Follow / follower_count). CASCADE handles project or user
    deletion without extra view-layer logic.
    """
    user = models.ForeignKey(
        'accounts.UserProfile',
        on_delete=models.CASCADE,
        related_name='reactions',
    )
    project = models.ForeignKey(
        'recommendation.Project',
        on_delete=models.CASCADE,
        related_name='reactions',
    )
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        unique_together = [('user', 'project')]
        indexes = [
            models.Index(fields=['project', '-created_at']),
        ]

    def __str__(self):
        return f'{self.user_id} -> project:{self.project_id}'


# ---------------------------------------------------------------------------
# Counter signals — single source of truth for Project.reaction_count
# ---------------------------------------------------------------------------

@receiver(post_save, sender=Reaction)
def _reaction_post_save(sender, instance, created, **kwargs):
    """Increment Project.reaction_count when a new Reaction row is created."""
    if not created:
        return
    from apps.recommendation.models import Project
    Project.objects.filter(pk=instance.project_id).update(
        reaction_count=F('reaction_count') + 1,
    )


@receiver(post_delete, sender=Reaction)
def _reaction_post_delete(sender, instance, **kwargs):
    """Decrement Project.reaction_count when a Reaction row is deleted (incl. CASCADE).

    Greatest(..., 0) prevents the counter going negative under concurrent deletes
    or counter drift.
    """
    from apps.recommendation.models import Project
    Project.objects.filter(pk=instance.project_id).update(
        reaction_count=Greatest(F('reaction_count') - 1, 0),
    )
