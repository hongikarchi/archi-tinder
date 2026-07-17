"""apps.works.storage — presigned PUT + key-existence helpers for Works R2 bucket.

FULL-WORKS-1: mirrors the accounts/storage.py lazy-import boto3 pattern.

R2-verified (2026-07-17): Cloudflare R2's S3 API does NOT implement presigned
POST — a correctly-signed POST policy upload against the real dev bucket
(archibe-works-dev) returns `501 NotImplemented` ("Presigned post requests are
not yet implemented"). Cloudflare's documented pattern for client-side direct
uploads is presigned PUT (developers.cloudflare.com/r2/objects/upload-objects/),
so this module generates presigned PUT URLs instead of POST policies.

Public API:
  generate_presigned_put(key, content_type) -> {url, key}
  verify_key_exists(key) -> (exists: bool, size: int|None)
"""
import logging

from django.conf import settings

logger = logging.getLogger('apps.works')


class WorksR2DisabledError(Exception):
    """Raised when WORKS_R2_ENABLED is False and an R2 operation is attempted."""


def generate_presigned_put(key: str, content_type: str) -> dict:
    """Generate a presigned PUT URL for direct browser-to-R2 upload.

    Parameters
    ----------
    key : str
        R2 object key, e.g. 'works/<profile_id>/<hex>_cover.webp'.
    content_type : str
        Declared content type (e.g. 'image/webp'). This is baked into the
        SigV4 signature (Params={'ContentType': ...}) — the client MUST send
        an identical Content-Type header on the PUT, or R2 rejects the
        upload with 403. This enforces an EXACT match, which is stronger
        than the old POST-policy 'starts-with' condition.

        Note: a presigned PUT cannot express a size cap (the POST policy's
        'content-length-range' condition has no PUT equivalent) — size
        enforcement moves server-side to finalize (see verify_key_exists).

    Returns
    -------
    dict
        {'url': str, 'key': str} — no 'fields' dict (PUT uploads send the
        body directly with a Content-Type header, unlike POST's multipart
        form fields).

    Raises
    ------
    WorksR2DisabledError
        When settings.WORKS_R2_ENABLED is False.
    """
    if not settings.WORKS_R2_ENABLED:
        raise WorksR2DisabledError('WORKS_R2_ENABLED is False — no R2 credentials configured.')

    s3 = _make_s3_client()
    url = s3.generate_presigned_url(
        'put_object',
        Params={'Bucket': settings.R2_WORKS_BUCKET, 'Key': key, 'ContentType': content_type},
        ExpiresIn=600,
    )
    return {'url': url, 'key': key}


def _make_s3_client():
    """Create a boto3 S3 client configured for the Works R2 bucket.

    Extracted so callers that verify multiple keys can build one client and
    pass it to verify_key_exists, avoiding per-key client construction overhead.
    boto3 is imported here (not at module top) so the module loads cleanly in
    local / CI environments where boto3 may not be present.
    """
    import boto3  # noqa: PLC0415 -- lazy import intentional (see module docstring)

    return boto3.client(
        's3',
        endpoint_url=settings.R2_ENDPOINT_URL,
        aws_access_key_id=settings.R2_ACCESS_KEY_ID,
        aws_secret_access_key=settings.R2_SECRET_ACCESS_KEY,
        region_name='auto',
    )


def verify_key_exists(key: str, s3_client=None) -> tuple:
    """Check whether an object key exists in the Works R2 bucket, and its size.

    A presigned PUT cannot express a server-side size cap the way a POST
    policy's 'content-length-range' condition could, so finalize enforces
    the 10 MB cap itself using the size returned here (see FinalizeView).

    Parameters
    ----------
    key : str
        R2 object key to verify.
    s3_client : optional boto3 S3 client
        When provided, the existing client is reused (avoids per-key client
        construction when checking multiple keys in a single request).  When
        None (default), a new client is created via _make_s3_client().

    Returns
    -------
    tuple
        (exists: bool, size: int | None) — size is the object's
        ContentLength in bytes when exists is True, otherwise None.

    Raises
    ------
    Exception
        Any non-404 ClientError is re-raised so callers see genuine errors.
    """
    from botocore.exceptions import ClientError

    s3 = s3_client if s3_client is not None else _make_s3_client()
    try:
        head = s3.head_object(Bucket=settings.R2_WORKS_BUCKET, Key=key)
        return True, head.get('ContentLength')
    except ClientError as e:
        error_code = e.response['Error']['Code']
        if error_code in ('404', 'NoSuchKey'):
            return False, None
        raise
