"""Domain helpers for apps.messaging (no HTTP concerns)."""
from django.db import transaction
from django.db.models import F, Q
from django.utils import timezone

from apps.accounts.models import UserProfile
from .models import Block, Conversation, Message


# -- Id bounds --------------------------------------------------------------
# An integer from the URL / query / body that exceeds its column type reaches
# Postgres as a DataError ("integer out of range") -> HTTP 500. Bound it first so
# the caller answers 404 / 400 instead. auth_user.id is int4; this app's own
# BigAutoField pks (Conversation, Message, ...) are int8.
AUTH_USER_ID_MAX = 2**31 - 1
BIGINT_ID_MAX = 2**63 - 1


def id_in_range(value, max_value=BIGINT_ID_MAX):
    """True when `value` is an int that fits a positive id column of max `max_value`.

    Defaults to BigAutoField bounds; pass AUTH_USER_ID_MAX for auth_user.id.
    bool is rejected (True == 1 would otherwise slip through).
    """
    return isinstance(value, int) and not isinstance(value, bool) and 1 <= value <= max_value


# -- Lookups ----------------------------------------------------------------

def get_profile_by_auth_id(auth_user_id):
    """API ids are auth User ids (== UserProfile.user_id); resolve to a UserProfile.

    None for an id that cannot exist (out of int4 range) without querying.
    """
    if not id_in_range(auth_user_id, AUTH_USER_ID_MAX):
        return None
    return UserProfile.objects.filter(user_id=auth_user_id).first()


def blocked_profile_ids(profile):
    """UserProfile pks blocked by OR blocking `profile` (either direction)."""
    ids = set()
    for blocker_id, blocked_id in Block.objects.filter(
        Q(blocker=profile) | Q(blocked=profile)
    ).values_list('blocker_id', 'blocked_id'):
        ids.add(blocked_id if blocker_id == profile.pk else blocker_id)
    return ids


def is_blocked_between(a, b):
    return Block.objects.filter(
        Q(blocker=a, blocked=b) | Q(blocker=b, blocked=a)
    ).exists()


def has_blocked(blocker, blocked):
    """One direction only: did `blocker` block `blocked`? (never the reverse)"""
    return Block.objects.filter(blocker=blocker, blocked=blocked).exists()


def pair(a, b):
    """Normalized (user_a, user_b) with user_a.pk < user_b.pk."""
    return (a, b) if a.pk < b.pk else (b, a)


def find_conversation(a, b):
    lo, hi = pair(a, b)
    return Conversation.objects.filter(user_a=lo, user_b=hi).first()


# -- Open conversation -------------------------------------------------------

def open_conversation(actor, peer, now=None):
    """Open (or reuse) the 1:1 conversation between `actor` and `peer`.

    Returns (conversation, created). The caller has already checked the gate
    (actor follows peer, no block either way); this opens its own transaction.
    Normalized pair + select_for_update get_or_create (the
    unique pair constraint makes a concurrent create IntegrityError-safe).

    An existing conversation that was closed by a block is reopened: the caller
    only gets here when no block exists. No system message is emitted. On create
    the actor's last_read is set to now.
    """
    now = now or timezone.now()
    lo, hi = pair(actor, peer)
    with transaction.atomic():
        conv, created = Conversation.objects.select_for_update().get_or_create(
            user_a=lo, user_b=hi, defaults={'created_at': now},
        )
        if created:
            setattr(conv, conv.last_read_field(actor), now)
            conv.save(update_fields=[conv.last_read_field(actor)])
        elif conv.closed_at is not None:
            conv.closed_at = None
            conv.save(update_fields=['closed_at'])
    return conv, created


# -- Unread -----------------------------------------------------------------

def unread_message_count(profile):
    """User messages after my last_read_at (all if null) NOT authored by me.

    Legacy system rows are hidden in the UI, so they are excluded (#506).

    Closed (blocked) conversations are excluded. One COUNT over the
    (conversation, id) index + conversation participant lookup.
    """
    mine = (
        Q(conversation__user_a=profile) & (
            Q(conversation__a_last_read_at__isnull=True)
            | Q(created_at__gt=F('conversation__a_last_read_at'))
        )
    ) | (
        Q(conversation__user_b=profile) & (
            Q(conversation__b_last_read_at__isnull=True)
            | Q(created_at__gt=F('conversation__b_last_read_at'))
        )
    )
    return (
        Message.objects
        .filter(conversation__closed_at__isnull=True)
        .filter(mine)
        .filter(kind=Message.KIND_USER)  # legacy system rows are hidden in the UI (#506)
        .filter(~Q(sender=profile))
        .count()
    )
