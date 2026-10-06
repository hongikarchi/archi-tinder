from django.conf import settings
from django.db import models
from django.utils import timezone


class AdminAuditLog(models.Model):
    """Append-only record of admitted admin actions (never written on denials)."""
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True,
        on_delete=models.SET_NULL, related_name='admin_audit_logs',
    )
    action = models.CharField(max_length=100)
    target_type = models.CharField(max_length=50, blank=True, default='')
    target_id = models.CharField(max_length=100, blank=True, default='')
    payload = models.JSONField(default=dict, blank=True)
    ip = models.GenericIPAddressField(null=True, blank=True)
    created_at = models.DateTimeField(default=timezone.now, db_index=True)

    class Meta:
        ordering = ['-created_at', '-id']

    def __str__(self):
        return f'{self.action} by {self.actor_id} at {self.created_at:%Y-%m-%d %H:%M}'


class ProviderNote(models.Model):
    """Admin-edited memo per external provider (e.g. which login/account we use there)."""
    provider = models.CharField(max_length=32, unique=True)
    login_note = models.CharField(max_length=200, blank=True, default='')
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True,
        on_delete=models.SET_NULL, related_name='+',
    )
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f'ProviderNote({self.provider})'
