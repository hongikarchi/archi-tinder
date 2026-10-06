"""apps.messaging models — contact requests, 1:1 conversations, blocks, reports.

Design: docs/decisions/2026-10-02-contact-messaging-design.md (D1-D13).

All user FKs point at accounts.UserProfile (its PK is the auto `id`; the auth
User id exposed by the API is `UserProfile.user_id`). Only the 'default' DB is
used — never the 'buildings' alias.

Schema is independent of the MESSAGING_ENABLED flag: tables always exist, the
flag only gates the HTTP surface.
"""
from django.db import models
from django.db.models import F, Q
from django.utils import timezone


class ContactRequest(models.Model):
    STATUS_PENDING = 'pending'
    STATUS_ACCEPTED = 'accepted'
    STATUS_IGNORED = 'ignored'
    STATUS_CHOICES = [
        (STATUS_PENDING, 'Pending'),
        (STATUS_ACCEPTED, 'Accepted'),
        (STATUS_IGNORED, 'Ignored'),
    ]

    sender = models.ForeignKey(
        'accounts.UserProfile', on_delete=models.CASCADE, related_name='sent_contact_requests',
    )
    recipient = models.ForeignKey(
        'accounts.UserProfile', on_delete=models.CASCADE, related_name='received_contact_requests',
    )
    greeting = models.CharField(max_length=100, blank=True, default='')
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default=STATUS_PENDING)
    created_at = models.DateTimeField(default=timezone.now)
    responded_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['sender', 'recipient'],
                condition=Q(status='pending'),
                name='uniq_pending_contact_request',
            ),
            models.CheckConstraint(
                check=~Q(sender=F('recipient')),
                name='contact_request_not_self',
            ),
        ]
        indexes = [
            models.Index(fields=['recipient', 'status'], name='contactreq_rcpt_status_idx'),
        ]

    def __str__(self):
        return f'{self.sender_id}->{self.recipient_id}:{self.status}'


class Conversation(models.Model):
    # Normalized pair: user_a_id < user_b_id (enforced by CheckConstraint).
    user_a = models.ForeignKey(
        'accounts.UserProfile', on_delete=models.CASCADE, related_name='conversations_as_a',
    )
    user_b = models.ForeignKey(
        'accounts.UserProfile', on_delete=models.CASCADE, related_name='conversations_as_b',
    )
    last_message_at = models.DateTimeField(null=True, blank=True, db_index=True)
    a_last_read_at = models.DateTimeField(null=True, blank=True)
    b_last_read_at = models.DateTimeField(null=True, blank=True)
    closed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['user_a', 'user_b'], name='uniq_conversation_pair'),
            models.CheckConstraint(
                check=Q(user_a__lt=F('user_b')),
                name='conversation_pair_normalized',
            ),
        ]

    def __str__(self):
        return f'conv {self.pk}: {self.user_a_id}<->{self.user_b_id}'

    def is_participant(self, profile):
        return profile.pk in (self.user_a_id, self.user_b_id)

    def other_id(self, profile):
        return self.user_b_id if profile.pk == self.user_a_id else self.user_a_id

    def last_read_field(self, profile):
        return 'a_last_read_at' if profile.pk == self.user_a_id else 'b_last_read_at'


class Message(models.Model):
    KIND_USER = 'user'
    KIND_SYSTEM = 'system'
    KIND_CHOICES = [(KIND_USER, 'User'), (KIND_SYSTEM, 'System')]

    SYSTEM_CONNECTED = 'connected'

    conversation = models.ForeignKey(
        Conversation, on_delete=models.CASCADE, related_name='messages',
    )
    # NULL for system messages (and for messages whose author was deleted).
    sender = models.ForeignKey(
        'accounts.UserProfile', null=True, blank=True,
        on_delete=models.SET_NULL, related_name='sent_messages',
    )
    kind = models.CharField(max_length=10, choices=KIND_CHOICES, default=KIND_USER)
    # 'connected' for system messages, blank for user messages. The UI renders
    # copy from this key via i18n — NO Korean/English text is stored in `body`.
    system_type = models.CharField(max_length=20, blank=True, default='')
    body = models.TextField(max_length=1000, blank=True, default='')
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        indexes = [
            models.Index(fields=['conversation', 'id'], name='message_conv_id_idx'),
        ]

    def __str__(self):
        return f'msg {self.pk} in conv {self.conversation_id}'


class Block(models.Model):
    blocker = models.ForeignKey(
        'accounts.UserProfile', on_delete=models.CASCADE, related_name='blocks_made',
    )
    blocked = models.ForeignKey(
        'accounts.UserProfile', on_delete=models.CASCADE, related_name='blocks_received',
    )
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['blocker', 'blocked'], name='uniq_block_pair'),
            models.CheckConstraint(check=~Q(blocker=F('blocked')), name='block_not_self'),
        ]

    def __str__(self):
        return f'{self.blocker_id} blocks {self.blocked_id}'


class Report(models.Model):
    TARGET_USER = 'user'
    TARGET_MESSAGE = 'message'
    TARGET_PROFILE = 'profile'
    TARGET_CHOICES = [
        (TARGET_USER, 'User'),
        (TARGET_MESSAGE, 'Message'),
        (TARGET_PROFILE, 'Profile'),
    ]

    reporter = models.ForeignKey(
        'accounts.UserProfile', on_delete=models.CASCADE, related_name='reports_made',
    )
    target_type = models.CharField(max_length=10, choices=TARGET_CHOICES)
    # user/profile -> auth user id (as exposed by the API); message -> Message pk.
    target_id = models.CharField(max_length=64)
    reason = models.CharField(max_length=500, blank=True, default='')
    created_at = models.DateTimeField(default=timezone.now)

    def __str__(self):
        return f'report {self.target_type}:{self.target_id} by {self.reporter_id}'
