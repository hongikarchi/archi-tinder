from django.db import models
from django.db.models import F
from django.db.models.functions import Greatest
from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver


class ArchitectFollow(models.Model):
    """Asymmetric user-to-architect follow using architect_id text (arch_XXXXXX).

    Uses text FK-free approach so follows work before Office sync runs.
    follower_count is derived from COUNT(*) queries — no counter cache.
    """
    follower = models.ForeignKey(
        'accounts.UserProfile',
        on_delete=models.CASCADE,
        related_name='architect_following_set',
    )
    architect_id = models.TextField(db_index=True)  # arch_XXXXXX format
    followed_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = [('follower', 'architect_id')]
        indexes = [
            models.Index(fields=['follower', '-followed_at']),
        ]

    def __str__(self):
        return f'{self.follower_id} -> arch:{self.architect_id}'


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
            models.Index(fields=['project', '-created_at'], name='social_reac_project_idx'),
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
