"""Unified-ID helpers: display_name == handle.

Kept free of view/serializer-view imports so views and management commands can
both import it without cycles.
"""
import secrets
import unicodedata

from .models import UserProfile
from .serializers import _HANDLE_RE, _HANDLE_RESERVED, handle_format_ok


def suggest_handle(nickname):
    """Build a valid, unused unified ID (handle) from a provider nickname."""
    base = unicodedata.normalize('NFC', nickname or '')
    base = ''.join(c for c in base if _HANDLE_RE.fullmatch(c))[:16]
    if len(base) < 2 or base.lower() in _HANDLE_RESERVED:
        base = 'member'  # 'user' is reserved
    candidate = base
    for _ in range(20):
        if not UserProfile.objects.filter(handle__iexact=candidate).exists():
            return candidate
        candidate = f'{base}{secrets.randbelow(10 ** (2 + secrets.randbelow(3)))}'
    return f'{base[:10]}{secrets.randbelow(10 ** 8):08d}'


def ensure_unified_identity(profile, seed, replace_invalid=False):
    """Assign a handle if missing, then set display_name = handle (in memory).

    An existing valid handle is never renamed. With replace_invalid=True a
    present-but-malformed handle is also replaced (legacy repair).
    Returns the list of changed field names; the caller saves them.
    """
    changed = []
    needs_handle = not profile.handle or (
        replace_invalid and not handle_format_ok(profile.handle)
    )
    if needs_handle:
        profile.handle = suggest_handle(seed)
        changed.append('handle')
    if profile.display_name != profile.handle:
        profile.display_name = profile.handle
        changed.append('display_name')
    return changed
