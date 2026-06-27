# Generated for LOGIN-ONBOARD-1
#
# Forward:
#   1. For every UserProfile: compute a unified ID from handle (preferred) or
#      display_name. NFC-normalize, strip whitespace, enforce format, dedupe
#      case-insensitively. Set handle = display_name = that value.
#   2. is_guest backfill:
#      - Has usable password AND email_verified_at is null → is_guest=True (unverified).
#      - Has email_verified_at set → is_guest=False (verified).
#      - No usable password / already is_guest=True → leave True (legacy guest / OAuth).
#
# Reverse: no-op (safe; DB state is compatible with prior code).

import re
import unicodedata

from django.db import migrations, transaction


def _is_usable_password(password):
    """Check if a password hash is usable (not the unusable placeholder)."""
    from django.contrib.auth.hashers import UNUSABLE_PASSWORD_PREFIX
    return not (password is None or password.startswith(UNUSABLE_PASSWORD_PREFIX))


def _nfc(value):
    return unicodedata.normalize('NFC', value) if value else ''


# Allowed char set for the unified ID (mirrors serializers.py _HANDLE_RE).
_ALLOWED_RE = re.compile(r'^[가-힣ᄀ-ᇿꥠ-꥿ힰ-퟿a-zA-Z0-9_]+$')


def _is_valid_format(value):
    """Return True if value passes the unified-ID format (no length check)."""
    return bool(_ALLOWED_RE.fullmatch(value)) if value else False


def _slugify_display_name(value):
    """Best-effort ASCII slug from a display_name that may contain spaces/special chars.

    Steps:
      1. NFC normalize.
      2. Strip whitespace from both ends; collapse internal whitespace.
      3. If the result already passes the unified-ID format, return it.
      4. Otherwise, strip non-allowed chars (keep Hangul + ASCII + digits + _).
      5. Lowercase ASCII portion (Hangul has no case).
      6. Truncate to 20 chars.
      7. If still empty, return None (caller will use fallback).
    """
    value = _nfc(value).strip()
    value = re.sub(r'\s+', '', value)  # remove all whitespace

    if _is_valid_format(value) and 2 <= len(value) <= 20:
        return value[:20]

    # Strip disallowed chars
    cleaned = re.sub(r'[^가-힣ᄀ-ᇿꥠ-꥿ힰ-퟿a-zA-Z0-9_]', '', value)
    cleaned = cleaned[:20]

    if not cleaned or len(cleaned) < 2:
        return None

    return cleaned


def _unique_id(base, seen_lower, pk_suffix, max_len=20):
    """Return a unique ID derived from `base`, not in `seen_lower` (case-folded set).

    Appends a numeric suffix, truncating the base to fit within max_len.
    pk_suffix is used as a final fallback when base itself is unusable.
    """
    candidate = base[:max_len]
    if candidate.lower() not in seen_lower and len(candidate) >= 2:
        seen_lower.add(candidate.lower())
        return candidate

    # Try numeric suffixes
    for i in range(1, 10000):
        suffix = str(i)
        room = max_len - len(suffix)
        if room < 1:
            break
        candidate = base[:room] + suffix
        if candidate.lower() not in seen_lower and len(candidate) >= 2:
            seen_lower.add(candidate.lower())
            return candidate

    # Final fallback: user_<pk>
    fallback = f'user_{pk_suffix}'[:max_len]
    seen_lower.add(fallback.lower())
    return fallback


def forward_migration(apps, schema_editor):
    """Backfill unified ID + is_guest for all existing UserProfile rows."""
    if schema_editor.connection.alias != 'default':
        return

    UserProfile = apps.get_model('accounts', 'UserProfile')

    with transaction.atomic():
        profiles = list(
            UserProfile.objects.select_related('user').all()
        )

        seen_lower = set()  # case-folded unified IDs already committed

        for profile in profiles:
            user = profile.user

            # -- Compute unified ID --
            # Prefer existing handle (already validated in most cases).
            raw = _nfc(profile.handle or '').strip() if profile.handle else None

            if raw and _is_valid_format(raw) and 2 <= len(raw) <= 20:
                base = raw[:20]
            else:
                # Fall back to display_name
                base = _slugify_display_name(profile.display_name or '')
                if not base:
                    base = f'user_{profile.pk}'

            unified = _unique_id(base, seen_lower, profile.pk)

            profile.handle = unified
            profile.display_name = unified

            # -- Backfill is_guest --
            has_password = _is_usable_password(user.password)
            has_verified_email = profile.email_verified_at is not None

            if has_verified_email:
                # Verified via Google → not a guest.
                profile.is_guest = False
            elif has_password and not profile.is_guest:
                # id+password account, not yet verified → mark as guest (unverified).
                profile.is_guest = True
            # else: already is_guest=True (legacy guest or no-credential) → leave.

            profile.save(update_fields=['handle', 'display_name', 'is_guest'])


def reverse_migration(apps, schema_editor):
    """No-op reverse — prior code is compatible with the backfilled data."""
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0010_remove_user_follow'),
    ]

    operations = [
        migrations.RunPython(forward_migration, reverse_code=reverse_migration),
    ]
