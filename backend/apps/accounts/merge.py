"""merge.py — Guest-into-verified merge helper.

Called by GuestPromoteView (Branch 1 — cross-device collision).
All FK reassignments happen inside a single atomic block; the caller's
transaction.atomic() in GuestPromoteView provides the outer savepoint.

Relationships handled:
  - Follow (follower role): guest outgoing follows → target, dedup + self-follow guard
  - Follow (followee role): incoming follows on guest → target, dedup + self-follow guard
  - Follow counters: recomputed from DB after bulk ops (signals not fired by .update())
  - ArchitectFollow: guest studio follows → target, dedup
  - Reaction: guest project reactions → target, dedup
  - Project / AnalysisSession / SessionEvent: no per-user unique constraint, safe bulk update
  - liked_building_ids: guest-first union, deduped, capped at 200
"""

import logging

from django.db import transaction

logger = logging.getLogger('apps.accounts')

# Maximum rows migrated per table in a single merge to prevent abusive guests
# with huge row counts from blowing memory or hammering the DB.
_MERGE_ROW_CAP = 1000


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _dedup_union(guest_ids, target_ids, cap=200):
    """Return guest-first deduplicated list capped at `cap`.

    Guest items are prepended (newest-first convention) so recently seen
    buildings from the guest session survive. Items already in target_ids
    that also appear in guest_ids are represented once (at guest position).
    """
    g = list(guest_ids or [])
    t = list(target_ids or [])
    seen = set()
    merged = []
    for bld_id in g + t:
        if bld_id not in seen:
            seen.add(bld_id)
            merged.append(bld_id)
    return merged[:cap]


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def merge_guest_into_target(guest_profile, target_profile):
    """Merge all relational data from `guest_profile` into `target_profile`.

    Both arguments are UserProfile instances.
    The caller (GuestPromoteView) owns the outer transaction.atomic(); this
    function adds a nested atomic (savepoint) for safety so a partial failure
    rolls back everything this helper touched without collapsing the outer
    transaction unnecessarily.

    After this call the guest_profile has no remaining FK relations; the caller
    must delete guest_profile and its User row.
    """
    from apps.social.models import Follow, ArchitectFollow, Reaction
    from apps.recommendation.models import Project, AnalysisSession, SessionEvent

    with transaction.atomic():
        # ------------------------------------------------------------------
        # 1. Follow — follower role (guest's outgoing follows)
        #    Snapshot target's followee set BEFORE any mutation.
        # ------------------------------------------------------------------
        target_followee_ids = set(
            Follow.objects.filter(follower=target_profile)
            .values_list('followee_id', flat=True)
        )

        guest_following_qs = Follow.objects.filter(follower=guest_profile)

        # IDs to delete: already followed by target OR would create self-follow
        followee_ids_to_delete = set()
        followee_ids_to_reassign = set()
        _guest_followee_ids = list(guest_following_qs.values_list('followee_id', flat=True))
        _follow_total = len(_guest_followee_ids)
        if _follow_total > _MERGE_ROW_CAP:
            logger.warning(
                'merge_guest_into_target: guest=%s Follow(follower) count=%d exceeds cap=%d; %d rows dropped',
                guest_profile.pk, _follow_total, _MERGE_ROW_CAP, _follow_total - _MERGE_ROW_CAP,
            )
        for followee_id in _guest_followee_ids[:_MERGE_ROW_CAP]:
            if followee_id in target_followee_ids or followee_id == target_profile.pk:
                followee_ids_to_delete.add(followee_id)
            else:
                followee_ids_to_reassign.add(followee_id)

        if followee_ids_to_delete:
            Follow.objects.filter(
                follower=guest_profile,
                followee_id__in=followee_ids_to_delete,
            ).delete()

        if followee_ids_to_reassign:
            Follow.objects.filter(
                follower=guest_profile,
                followee_id__in=followee_ids_to_reassign,
            ).update(follower=target_profile)

        # ------------------------------------------------------------------
        # 2. Follow — followee role (others following the guest)
        #    Snapshot target's follower set BEFORE mutation.
        # ------------------------------------------------------------------
        target_follower_ids = set(
            Follow.objects.filter(followee=target_profile)
            .values_list('follower_id', flat=True)
        )

        guest_followers_qs = Follow.objects.filter(followee=guest_profile)

        follower_ids_to_delete = set()
        follower_ids_to_reassign = set()
        _guest_follower_ids = list(guest_followers_qs.values_list('follower_id', flat=True))
        _followers_total = len(_guest_follower_ids)
        if _followers_total > _MERGE_ROW_CAP:
            logger.warning(
                'merge_guest_into_target: guest=%s Follow(followee) count=%d exceeds cap=%d; %d rows dropped',
                guest_profile.pk, _followers_total, _MERGE_ROW_CAP, _followers_total - _MERGE_ROW_CAP,
            )
        for follower_id in _guest_follower_ids[:_MERGE_ROW_CAP]:
            if follower_id in target_follower_ids or follower_id == target_profile.pk:
                follower_ids_to_delete.add(follower_id)
            else:
                follower_ids_to_reassign.add(follower_id)

        if follower_ids_to_delete:
            Follow.objects.filter(
                followee=guest_profile,
                follower_id__in=follower_ids_to_delete,
            ).delete()

        if follower_ids_to_reassign:
            Follow.objects.filter(
                followee=guest_profile,
                follower_id__in=follower_ids_to_reassign,
            ).update(followee=target_profile)

        # ------------------------------------------------------------------
        # 3. Follow counter-cache recompute
        #    .update() does not fire post_save signals, so the target's
        #    follower_count / following_count would be stale. Recompute from
        #    ground truth now that all Follow rows are settled.
        # ------------------------------------------------------------------
        target_profile.follower_count = Follow.objects.filter(followee=target_profile).count()
        target_profile.following_count = Follow.objects.filter(follower=target_profile).count()
        # Save is deferred — combined with liked_building_ids save below.

        # ------------------------------------------------------------------
        # 4. ArchitectFollow (was entirely missing from the original merge)
        # ------------------------------------------------------------------
        target_arch_ids = set(
            ArchitectFollow.objects.filter(follower=target_profile)
            .values_list('architect_id', flat=True)
        )

        guest_arch_qs = ArchitectFollow.objects.filter(follower=guest_profile)
        arch_ids_to_delete = set()
        arch_ids_to_reassign = set()
        _guest_arch_ids = list(guest_arch_qs.values_list('architect_id', flat=True))
        _arch_total = len(_guest_arch_ids)
        if _arch_total > _MERGE_ROW_CAP:
            logger.warning(
                'merge_guest_into_target: guest=%s ArchitectFollow count=%d exceeds cap=%d; %d rows dropped',
                guest_profile.pk, _arch_total, _MERGE_ROW_CAP, _arch_total - _MERGE_ROW_CAP,
            )
        for arch_id in _guest_arch_ids[:_MERGE_ROW_CAP]:
            if arch_id in target_arch_ids:
                arch_ids_to_delete.add(arch_id)
            else:
                arch_ids_to_reassign.add(arch_id)

        if arch_ids_to_delete:
            ArchitectFollow.objects.filter(
                follower=guest_profile,
                architect_id__in=arch_ids_to_delete,
            ).delete()

        if arch_ids_to_reassign:
            ArchitectFollow.objects.filter(
                follower=guest_profile,
                architect_id__in=arch_ids_to_reassign,
            ).update(follower=target_profile)

        # ------------------------------------------------------------------
        # 5. Reaction (unique_together: user, project)
        # ------------------------------------------------------------------
        target_reacted_project_ids = set(
            Reaction.objects.filter(user=target_profile)
            .values_list('project_id', flat=True)
        )

        guest_reaction_qs = Reaction.objects.filter(user=guest_profile)
        reaction_project_ids_to_delete = set()
        reaction_project_ids_to_reassign = set()
        _guest_reaction_ids = list(guest_reaction_qs.values_list('project_id', flat=True))
        _reaction_total = len(_guest_reaction_ids)
        if _reaction_total > _MERGE_ROW_CAP:
            logger.warning(
                'merge_guest_into_target: guest=%s Reaction count=%d exceeds cap=%d; %d rows dropped',
                guest_profile.pk, _reaction_total, _MERGE_ROW_CAP, _reaction_total - _MERGE_ROW_CAP,
            )
        for project_id in _guest_reaction_ids[:_MERGE_ROW_CAP]:
            if project_id in target_reacted_project_ids:
                reaction_project_ids_to_delete.add(project_id)
            else:
                reaction_project_ids_to_reassign.add(project_id)

        if reaction_project_ids_to_delete:
            Reaction.objects.filter(
                user=guest_profile,
                project_id__in=reaction_project_ids_to_delete,
            ).delete()

        if reaction_project_ids_to_reassign:
            Reaction.objects.filter(
                user=guest_profile,
                project_id__in=reaction_project_ids_to_reassign,
            ).update(user=target_profile)

        # ------------------------------------------------------------------
        # 6. Project — no per-user unique constraint; safe bulk update
        # ------------------------------------------------------------------
        _project_qs = Project.objects.filter(user=guest_profile)
        _project_total = _project_qs.count()
        if _project_total > _MERGE_ROW_CAP:
            logger.warning(
                'merge_guest_into_target: guest=%s Project count=%d exceeds cap=%d; %d rows dropped',
                guest_profile.pk, _project_total, _MERGE_ROW_CAP, _project_total - _MERGE_ROW_CAP,
            )
        Project.objects.filter(
            pk__in=list(_project_qs.values_list('pk', flat=True)[:_MERGE_ROW_CAP])
        ).update(user=target_profile)

        # ------------------------------------------------------------------
        # 7. AnalysisSession — no per-user unique constraint; safe bulk update
        # ------------------------------------------------------------------
        _session_qs = AnalysisSession.objects.filter(user=guest_profile)
        _session_total = _session_qs.count()
        if _session_total > _MERGE_ROW_CAP:
            logger.warning(
                'merge_guest_into_target: guest=%s AnalysisSession count=%d exceeds cap=%d; %d rows dropped',
                guest_profile.pk, _session_total, _MERGE_ROW_CAP, _session_total - _MERGE_ROW_CAP,
            )
        AnalysisSession.objects.filter(
            pk__in=list(_session_qs.values_list('pk', flat=True)[:_MERGE_ROW_CAP])
        ).update(user=target_profile)

        # ------------------------------------------------------------------
        # 8. SessionEvent — user FK is nullable (SET_NULL on delete); reassign
        #    guest rows so they don't become orphaned when guest user is deleted.
        # ------------------------------------------------------------------
        _event_qs = SessionEvent.objects.filter(user=guest_profile)
        _event_total = _event_qs.count()
        if _event_total > _MERGE_ROW_CAP:
            logger.warning(
                'merge_guest_into_target: guest=%s SessionEvent count=%d exceeds cap=%d; %d rows dropped',
                guest_profile.pk, _event_total, _MERGE_ROW_CAP, _event_total - _MERGE_ROW_CAP,
            )
        SessionEvent.objects.filter(
            pk__in=list(_event_qs.values_list('pk', flat=True)[:_MERGE_ROW_CAP])
        ).update(user=target_profile)

        # ------------------------------------------------------------------
        # 9. liked_building_ids — guest-first union, deduped, capped at 200
        # ------------------------------------------------------------------
        target_profile.liked_building_ids = _dedup_union(
            guest_profile.liked_building_ids,
            target_profile.liked_building_ids,
        )

        # Single save for counter-cache recompute + liked_building_ids
        target_profile.save(update_fields=[
            'follower_count',
            'following_count',
            'liked_building_ids',
        ])

    logger.info(
        'merge_guest_into_target: guest=%s merged into target=%s',
        guest_profile.pk,
        target_profile.pk,
    )
