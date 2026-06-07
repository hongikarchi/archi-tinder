"""apps.accounts.storage — avatar upload storage abstraction.

FRONT-AVATAR-1: Mirrors the INFRA-REDIS-1 prod/local-fallback pattern.

  R2 branch  — active when ALL of R2_ENDPOINT_URL, R2_ACCESS_KEY_ID,
               R2_SECRET_ACCESS_KEY, R2_AVATAR_BUCKET are set in the env
               (settings.AVATAR_R2_ENABLED == True). boto3 is imported
               *inside* the branch so CI / local dev without R2 creds never
               even attempts the import.

  Filesystem fallback — active when R2_* vars are absent (local dev + CI).
               Uses Django's FileSystemStorage instantiated at call time
               (NOT module-level) so @override_settings(MEDIA_ROOT=...) in
               tests correctly redirects writes to tmp_path.

Public API:
  store_avatar(image_bytes: bytes, key: str, request) -> str
      Write image_bytes under `key` (e.g. 'avatars/<uuid>.webp') and return
      the absolute public URL to store in UserProfile.avatar_url.
"""

import logging

from django.conf import settings

logger = logging.getLogger('apps.accounts')


def store_avatar(image_bytes: bytes, key: str, request) -> str:
    """Persist avatar bytes and return the absolute public URL.

    Parameters
    ----------
    image_bytes : bytes
        Already-processed WEBP bytes (512x512, mode=RGB).
    key : str
        Object key / relative file path, e.g. 'avatars/<uuid>.webp'.
    request : HttpRequest
        Used by the filesystem branch to build an absolute URL via
        request.build_absolute_uri (so http vs https + hostname are correct
        regardless of the test client or real server).

    Returns
    -------
    str
        Absolute URL suitable for UserProfile.avatar_url (URLField).
    """
    if settings.AVATAR_R2_ENABLED:
        return _store_r2(image_bytes, key)
    return _store_filesystem(image_bytes, key, request)


# ---------------------------------------------------------------------------
# R2 branch
# ---------------------------------------------------------------------------

def _store_r2(image_bytes: bytes, key: str) -> str:
    """Upload to Cloudflare R2 and return the public CDN URL.

    boto3 is imported here (not at module top) so the module loads cleanly
    in local / CI environments where boto3 may not be present or R2 creds
    are absent.
    """
    import boto3  # noqa: PLC0415 -- lazy import intentional (see module docstring)

    s3 = boto3.client(
        's3',
        endpoint_url=settings.R2_ENDPOINT_URL,
        aws_access_key_id=settings.R2_ACCESS_KEY_ID,
        aws_secret_access_key=settings.R2_SECRET_ACCESS_KEY,
        region_name='auto',
    )
    s3.put_object(
        Bucket=settings.R2_AVATAR_BUCKET,
        Key=key,
        Body=image_bytes,
        ContentType='image/webp',
        CacheControl='public, max-age=31536000, immutable',
    )
    base = settings.AVATAR_PUBLIC_BASE_URL.rstrip('/')
    return f'{base}/{key}'


# ---------------------------------------------------------------------------
# Filesystem fallback (local dev + CI)
# ---------------------------------------------------------------------------

def _store_filesystem(image_bytes: bytes, key: str, request) -> str:
    """Write to MEDIA_ROOT/<key> and return an absolute URL.

    FileSystemStorage is instantiated at call time (not module-level) so
    @override_settings(MEDIA_ROOT=tmp_path) in tests is respected -- a
    module-level instance would cache the real MEDIA_ROOT at import time
    and ignore the tmp_path override.

    avatar_url is a URLField; it REJECTS relative paths. We build the URL
    via request.build_absolute_uri so it is always an absolute http(s) URL.
    """
    from django.core.files.base import ContentFile
    from django.core.files.storage import FileSystemStorage

    # Instantiate at call time to respect @override_settings(MEDIA_ROOT=...).
    fs = FileSystemStorage(
        location=settings.MEDIA_ROOT,
        base_url=settings.MEDIA_URL,
    )
    # FileSystemStorage._save creates missing parent dirs automatically;
    # passing key with subdir ('avatars/...') writes to MEDIA_ROOT/avatars/.
    saved_name = fs.save(key, ContentFile(image_bytes))
    # saved_name may differ from key if a name collision is resolved (uuid4
    # makes this extremely unlikely, but handled defensively).
    # Build an absolute URL via request.build_absolute_uri so scheme/host
    # are correct in all contexts (http in tests, https in prod with proxy).
    relative_url = settings.MEDIA_URL + saved_name.lstrip('/')
    return request.build_absolute_uri(relative_url)
