"""Domain helpers for the user-to-user follow (SNS-FOLLOW-1). No HTTP concerns.

`is_guest_account` is the ONLY place in the follow / messaging code that reads
`UserProfile.is_guest` (issue #443 may remove the guest path; then only that
function changes). Every follow decision goes through `can_follow`.
"""
from apps.accounts.models import PersonalityProfile
from apps.messaging.services import is_blocked_between

from .models import UserFollow


def is_guest_account(profile):
    """True for an unverified guest account. The single reader of `is_guest`."""
    return bool(profile.is_guest)


def accepts_new_followers(profile):
    """May `profile` be newly followed?

    False for guests and for users who opted out of discovery
    (PersonalityProfile.discovery_opt_in=False). A user with NO PersonalityProfile
    (assessment not done) CAN be followed. Existing follows are not affected by
    this rule — it only gates creating new ones.
    """
    if is_guest_account(profile):
        return False
    return not PersonalityProfile.objects.filter(user=profile, discovery_opt_in=False).exists()


def can_follow(me, target):
    """The single follow-creation decision (GET status, POST follow, migrations mirror it)."""
    if me.pk == target.pk:
        return False
    if is_blocked_between(me, target):
        return False
    return accepts_new_followers(target)


def is_following(a, b):
    """Does `a` follow `b`? (one direction)"""
    return UserFollow.objects.filter(follower=a, following=b).exists()


def follower_count(profile):
    return UserFollow.objects.filter(following=profile).count()


def following_count(profile):
    return UserFollow.objects.filter(follower=profile).count()


def evict_follow_counts_cache(*profiles):
    """Profile-detail payloads embed follower/following counts: drop them for these users."""
    from apps.recommendation.caches import evict_user_profile_detail
    for profile in profiles:
        evict_user_profile_detail(profile.user_id)
