from django.db import models


class Notification(models.Model):
    """In-app notification (NOTIF-INAPP-1 v1).

    Two categories:
      - 'social'   — user-facing reactions, prefs-gated per UserProfile.notifications
      - 'security' — password change / new-device login, ALWAYS emitted regardless
        of prefs (see apps.notifications.services.notify_security).

    payload shape by type:
      reaction:          {project_id: str(uuid), project_title: str}
      password_changed:  {}
      new_login:         {}
    """
    TYPE_CHOICES = [
        ('reaction', 'Reaction'),
        ('password_changed', 'Password Changed'),
        ('new_login', 'New Login'),
    ]
    CATEGORY_CHOICES = [
        ('social', 'Social'),
        ('security', 'Security'),
    ]

    recipient = models.ForeignKey(
        'accounts.UserProfile',
        on_delete=models.CASCADE,
        related_name='inbox',
    )
    # Nullable + SET_NULL: security notifications have no actor; if the actor's
    # profile is later deleted, keep the notification row (actor becomes null)
    # rather than cascading it away.
    actor = models.ForeignKey(
        'accounts.UserProfile',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='+',
    )
    type = models.CharField(max_length=20, choices=TYPE_CHOICES)
    category = models.CharField(max_length=10, choices=CATEGORY_CHOICES)
    payload = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    read_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        indexes = [
            models.Index(fields=['recipient', '-created_at'], name='notif_recip_created_idx'),
            models.Index(fields=['recipient', 'read_at'], name='notif_recip_readat_idx'),
        ]

    def __str__(self):
        return f'{self.type} -> recipient:{self.recipient_id}'


class KnownDevice(models.Model):
    """Tracks previously-seen User-Agent hashes per user for new-device login detection.

    First-ever device row (registration / very first login) is recorded
    silently — no notification. Any SUBSEQENT new ua_hash triggers
    notify_security(user, 'new_login').
    """
    user = models.ForeignKey(
        'accounts.UserProfile',
        on_delete=models.CASCADE,
        related_name='known_devices',
    )
    # sha256 hexdigest of the User-Agent header, truncated to 32 chars — ample
    # collision resistance for a device-fingerprint bucket, not a security secret.
    ua_hash = models.CharField(max_length=64)
    created_at = models.DateTimeField(auto_now_add=True)
    last_seen = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = [('user', 'ua_hash')]

    def __str__(self):
        return f'{self.user_id}:{self.ua_hash[:8]}'
