"""log_admin_action -- write one AdminAuditLog row for an ADMITTED admin request."""
import ipaddress
import logging

from .models import AdminAuditLog

logger = logging.getLogger('apps.admin_dashboard')


def _client_ip(request):
    xff = request.META.get('HTTP_X_FORWARDED_FOR', '')
    raw = xff.split(',')[0].strip() if xff else request.META.get('REMOTE_ADDR', '')
    try:
        return str(ipaddress.ip_address(raw))
    except ValueError:
        return None


def log_admin_action(request, action, target_type='', target_id='', payload=None):
    """Best-effort: an audit-write failure must never break the admin read itself."""
    try:
        return AdminAuditLog.objects.create(
            actor=request.user,
            action=action,
            target_type=target_type or '',
            target_id=str(target_id) if target_id != '' else '',
            payload=payload or {},
            ip=_client_ip(request),
        )
    except Exception:
        logger.exception('log_admin_action failed: action=%s', action)
        return None
