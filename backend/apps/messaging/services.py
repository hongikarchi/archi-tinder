"""Domain helpers for apps.messaging (no HTTP concerns)."""
from datetime import timedelta

from django.db.models import F, Q
from django.utils import timezone

from apps.accounts.models import PersonalityProfile, UserProfile
from .models import Block, ContactRequest, Conversation, Message

CONTACT_COOLDOWN_DAYS = 30


# -- Lookups ----------------------------------------------------------------

def get_profile_by_auth_id(auth_user_id):
    """API ids are auth User ids (== UserProfile.user_id); resolve to a UserProfile."""
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


def recipient_eligible(profile):
    """D11: PersonalityProfile exists AND discovery_opt_in is True.

    Guests are excluded too: IsVerifiedUser blocks them from accept/ignore/
    block, so a request to a guest would stay pending forever.
    """
    if profile.is_guest:
        return False
    return PersonalityProfile.objects.filter(user=profile, discovery_opt_in=True).exists()


def pair(a, b):
    """Normalized (user_a, user_b) with user_a.pk < user_b.pk."""
    return (a, b) if a.pk < b.pk else (b, a)


def find_conversation(a, b):
    lo, hi = pair(a, b)
    return Conversation.objects.filter(user_a=lo, user_b=hi).first()


def recent_ignore_exists(sender, recipient, now=None):
    now = now or timezone.now()
    cutoff = now - timedelta(days=CONTACT_COOLDOWN_DAYS)
    return ContactRequest.objects.filter(
        sender=sender, recipient=recipient,
        status=ContactRequest.STATUS_IGNORED, responded_at__gt=cutoff,
    ).exists()


# -- Connect (accept) -------------------------------------------------------

def connect(requests, actor, now=None):
    """Open (or reuse) the conversation for accepted request(s). Caller wraps in a transaction.

    `requests` — 1 request (normal accept) or 2 (mutual interest), already marked accepted.
    Message order: greetings chronologically (sender = the requester), then ONE
    kind=system/connected message (no text stored, D13).

    Read state: the actor sees everything (last_read = now). The other side keeps
    last_read at (at most) their view of the greetings, so the connected system
    message counts as 1 unread for them — the only way the earlier requester can
    learn of the accept, since no Notification row is created (D9).
    """
    now = now or timezone.now()
    requests = sorted(requests, key=lambda r: r.created_at)
    first = requests[0]
    lo, hi = pair(first.sender, first.recipient)
    conv, created = Conversation.objects.select_for_update().get_or_create(
        user_a=lo, user_b=hi, defaults={'created_at': now},
    )
    # Sweep any other pending request between the pair (simultaneous A->B / B->A race).
    ContactRequest.objects.filter(
        status=ContactRequest.STATUS_PENDING,
    ).filter(
        Q(sender=lo, recipient=hi) | Q(sender=hi, recipient=lo)
    ).update(status=ContactRequest.STATUS_ACCEPTED, responded_at=now)

    if not created and conv.closed_at is None and conv.messages.filter(
        kind=Message.KIND_SYSTEM, system_type=Message.SYSTEM_CONNECTED,
    ).exists():
        return conv  # already connected and open: idempotent, no duplicate messages

    if conv.closed_at is not None:
        conv.closed_at = None  # re-connect after block/unblock

    for r in requests:
        if r.greeting:
            Message.objects.create(
                conversation=conv, sender=r.sender, kind=Message.KIND_USER,
                body=r.greeting, created_at=r.created_at,
            )
    Message.objects.create(
        conversation=conv, sender=None, kind=Message.KIND_SYSTEM,
        system_type=Message.SYSTEM_CONNECTED, body='', created_at=now,
    )

    actor_field = conv.last_read_field(actor)
    setattr(conv, actor_field, now)
    other_field = 'b_last_read_at' if actor_field == 'a_last_read_at' else 'a_last_read_at'
    greeting_times = [r.created_at for r in requests if r.greeting]
    if greeting_times:
        current = getattr(conv, other_field)
        seen = max(greeting_times)
        setattr(conv, other_field, seen if current is None else max(current, seen))
    conv.last_message_at = now
    conv.save()
    return conv


# -- Unread -----------------------------------------------------------------

def unread_message_count(profile):
    """Messages after my last_read_at (all if null) NOT authored by me (system included).

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
        .filter(Q(sender__isnull=True) | ~Q(sender=profile))
        .count()
    )


def pending_received_count(profile):
    qs = ContactRequest.objects.filter(recipient=profile, status=ContactRequest.STATUS_PENDING)
    blocked = blocked_profile_ids(profile)
    if blocked:
        qs = qs.exclude(sender_id__in=blocked)
    return qs.count()
