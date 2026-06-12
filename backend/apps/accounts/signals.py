"""User cache invalidation safety net via Django ORM signals.

Any code path that mutates User via ``User.save()`` or ``User.objects.create()``
triggers ``post_save``. We hook ``post_save`` to auto-invalidate the JWT user
cache, ensuring out-of-band User mutations (e.g., Django admin UI toggling
``is_active``) reflect in the next authenticated request without TTL delay.

``post_delete`` handles User deletion so the orphaned cache key is cleaned up
promptly rather than expiring on its own TTL.

IMPORTANT: ``User.objects.filter(...).update(...)`` does NOT fire ``post_save``
signals. This backstop does NOT cover queryset ``.update()`` paths. Any code
that performs a bulk ``UPDATE`` on auth-relevant User fields must call
``invalidate_user_cache(user_id)`` explicitly (see authentication.py docstring).

This is a BACKSTOP for explicit ``invalidate_user_cache()`` calls — the explicit
calls in views.py give synchronous semantics that don't depend on signal
ordering or third-party signal-skipping.
"""

from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from django.contrib.auth import get_user_model

from .authentication import invalidate_user_cache
from .models import UserProfile

User = get_user_model()


@receiver(post_save, sender=User)
def _invalidate_user_cache_on_save(sender, instance, **kwargs):
    invalidate_user_cache(instance.id)


@receiver(post_delete, sender=User)
def _invalidate_user_cache_on_delete(sender, instance, **kwargs):
    invalidate_user_cache(instance.id)


@receiver(post_delete, sender=UserProfile)
def _gc_avatar_on_profile_delete(sender, instance, **kwargs):
    """GC the stored avatar when a UserProfile is deleted (BACK-AVATAR-2).

    Fires on UserProfile's own post_delete — which is triggered both by direct
    profile deletion AND by User.delete() cascading (Django's collector fires
    post_delete for each cascade-deleted row with instance still in memory,
    so instance.avatar_url is accessible).

    We hook UserProfile (NOT User) because at User post_delete time the profile
    row is already gone from the DB; Django fires UserProfile post_delete
    *before* the parent User row is removed, so the instance is still available.

    Best-effort: delete_avatar swallows all exceptions internally.
    """
    from .storage import delete_avatar
    delete_avatar(instance.avatar_url or '')
