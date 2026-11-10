"""
services.py -- apps/notifications (NOTIF-INAPP-1)

Emission-side helpers. Both entry points are wrapped by callers in
try/except so a notification failure NEVER breaks the caller's primary
request (react / login / password-change) — see call sites in
apps/social/views.py and apps/accounts/views/auth.py.
"""
import hashlib
import logging
from datetime import datetime, timezone as dt_timezone

from .models import Notification, KnownDevice

logger = logging.getLogger('apps.notifications')


def notify_reaction(reaction):
    """Emit a 'reaction' notification to the reacted Project's owner.

    Skips when:
      - actor (reaction.user) is the project owner (self-reaction)
      - recipient has opted out: UserProfile.notifications['social']['in_app'] is False
        (ABSENT key means True — opt-out default)
      - an UNREAD Notification already exists for
        (recipient, actor, type='reaction', payload.project_id) — dedupe so
        react/unreact/react cycles on the same project don't spam while unread.

    Never raises — caller (ReactionView.post) wraps this defensively too, but
    this function also swallows its own errors so a bug here can't 500 the
    react request.
    """
    try:
        project = reaction.project
        recipient = project.user
        actor = reaction.user

        if actor_id_equals_recipient(actor, recipient):
            return

        prefs = getattr(recipient, 'notifications', None) or {}
        social_prefs = prefs.get('social', {}) if isinstance(prefs, dict) else {}
        if isinstance(social_prefs, dict) and social_prefs.get('in_app', True) is False:
            return

        project_id_str = str(project.project_id)
        already_unread = Notification.objects.filter(
            recipient=recipient,
            actor=actor,
            type='reaction',
            read_at__isnull=True,
            payload__project_id=project_id_str,
        ).exists()
        if already_unread:
            return

        Notification.objects.create(
            recipient=recipient,
            actor=actor,
            type='reaction',
            category='social',
            payload={
                'project_id': project_id_str,
                'project_title': project.name,
            },
        )
    except Exception:
        logger.exception('notify_reaction failed (reaction pk=%s)', getattr(reaction, 'pk', None))


def _social_in_app_enabled(recipient):
    """False only when notifications['social']['in_app'] is explicitly False."""
    prefs = getattr(recipient, 'notifications', None) or {}
    social_prefs = prefs.get('social', {}) if isinstance(prefs, dict) else {}
    return not (isinstance(social_prefs, dict) and social_prefs.get('in_app', True) is False)


def _deadline_iso(deadline_at):
    """Canonical UTC ISO string for a deadline (datetime or already-ISO str)."""
    if isinstance(deadline_at, datetime):
        return deadline_at.astimezone(dt_timezone.utc).isoformat()
    return str(deadline_at)


def contest_deadline_notification_exists(recipient, contest_id, stage, deadline_at):
    """True when a contest_deadline Notification (read or unread) already exists
    for (recipient, contest, stage, deadline instant)."""
    return Notification.objects.filter(
        recipient=recipient,
        type='contest_deadline',
        payload__contest_id=contest_id,
        payload__stage=stage,
        payload__deadline_at=_deadline_iso(deadline_at),
    ).exists()


def would_notify_contest_deadline(recipient, contest, stage, deadline_at):
    """Dry-run twin of notify_contest_deadline: True when a row would be created."""
    return _social_in_app_enabled(recipient) and not contest_deadline_notification_exists(
        recipient, contest.pk, stage, deadline_at,
    )


def notify_contest_deadline(recipient, contest, stage, kind, deadline_at):
    """Emit a 'contest_deadline' notification (FULL-CONTEST-NOTIF-1). Returns True if created.

    stage: 7 (D-7) or 1 (D-1). kind: 'apply' (apply_deadline) or 'deadline'
    (submission_deadline fallback). actor is None, category 'social'.

    Skips (returns False) when:
      - recipient opted out: notifications['social']['in_app'] is False
        (ABSENT key means True)
      - a Notification (read OR unread) already exists for
        (recipient, contest_id, stage, deadline_at) — once per deadline instant,
        so a changed deadline is a new key.

    Never raises — logs and returns False.
    """
    try:
        if not _social_in_app_enabled(recipient):
            return False
        deadline_iso = _deadline_iso(deadline_at)
        if contest_deadline_notification_exists(recipient, contest.pk, stage, deadline_iso):
            return False
        Notification.objects.create(
            recipient=recipient,
            actor=None,
            type='contest_deadline',
            category='social',
            payload={
                'contest_id': contest.pk,
                'contest_title': contest.title,
                'stage': stage,
                'kind': kind,
                'deadline_at': deadline_iso,
            },
        )
        return True
    except Exception:
        logger.exception(
            'notify_contest_deadline failed (recipient pk=%s, contest pk=%s)',
            getattr(recipient, 'pk', None), getattr(contest, 'pk', None),
        )
        return False


def actor_id_equals_recipient(actor, recipient):
    """True when actor and recipient are the same UserProfile (self-reaction guard)."""
    return actor is not None and recipient is not None and actor.pk == recipient.pk


def notify_security(user, type, payload=None):
    """Emit a security-category notification. Prefs are IGNORED (always-on).

    `user` is a UserProfile instance. `type` must be one of the security
    Notification.TYPE_CHOICES ('password_changed', 'new_login'). actor is
    always None for security notifications.

    Never raises — callers (password-change / login views) wrap this too,
    but this function also swallows its own errors defensively.
    """
    try:
        Notification.objects.create(
            recipient=user,
            actor=None,
            type=type,
            category='security',
            payload=payload or {},
        )
    except Exception:
        logger.exception('notify_security failed (user pk=%s, type=%s)', getattr(user, 'pk', None), type)


def hash_user_agent(user_agent):
    """sha256 hexdigest of the User-Agent header, truncated to 32 chars.

    Missing/empty UA -> hash of the empty string (still a valid, stable bucket).
    """
    ua = user_agent or ''
    return hashlib.sha256(ua.encode('utf-8')).hexdigest()[:32]


def record_device_and_maybe_notify(user, user_agent):
    """Record (or touch) a KnownDevice row for `user` + `user_agent`; notify on new device.

    First-ever device for a user is recorded silently (no notification) — this
    covers registration / first login. Any SUBSEQUENT new ua_hash (the user
    already had >=1 other KnownDevice row) triggers notify_security(user, 'new_login').

    Never raises — wrapped defensively so a hashing/DB hiccup can't break login.
    """
    try:
        ua_hash = hash_user_agent(user_agent)
        had_other_device = KnownDevice.objects.filter(user=user).exclude(ua_hash=ua_hash).exists()
        _device, created = KnownDevice.objects.get_or_create(user=user, ua_hash=ua_hash)
        if created and had_other_device:
            notify_security(user, 'new_login')
    except Exception:
        logger.exception('record_device_and_maybe_notify failed (user pk=%s)', getattr(user, 'pk', None))
