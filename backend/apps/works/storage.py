"""apps.works.storage — presigned POST + key-existence helpers for Works R2 bucket.

FULL-WORKS-1: mirrors the accounts/storage.py lazy-import boto3 pattern.

Public API:
  generate_presigned_post(key, content_type, max_bytes=10MB) -> {url, fields}
  verify_key_exists(key) -> bool
"""
import logging

from django.conf import settings

logger = logging.getLogger('apps.works')


class WorksR2DisabledError(Exception):
    """Raised when WORKS_R2_ENABLED is False and an R2 operation is attempted."""


def generate_presigned_post(key: str, content_type: str, max_bytes: int = 10 * 1024 * 1024) -> dict:
    """Generate a presigned POST URL for direct browser-to-R2 upload.

    Parameters
    ----------
    key : str
        R2 object key, e.g. 'works/<profile_id>/<hex>_cover.webp'.
    content_type : str
        Declared content type (e.g. 'image/webp').
    max_bytes : int
        Maximum allowed Content-Length (default 10 MB).

    Returns
    -------
    dict
        {'url': str, 'fields': dict} — identical shape to what boto3 returns,
        passed through to the caller without modification.

    Raises
    ------
    WorksR2DisabledError
        When settings.WORKS_R2_ENABLED is False.
    """
    if not settings.WORKS_R2_ENABLED:
        raise WorksR2DisabledError('WORKS_R2_ENABLED is False — no R2 credentials configured.')

    import boto3  # noqa: PLC0415 -- lazy import intentional (see module docstring)

    s3 = boto3.client(
        's3',
        endpoint_url=settings.R2_ENDPOINT_URL,
        aws_access_key_id=settings.R2_ACCESS_KEY_ID,
        aws_secret_access_key=settings.R2_SECRET_ACCESS_KEY,
        region_name='auto',
    )
    result = s3.generate_presigned_post(
        Bucket=settings.R2_WORKS_BUCKET,
        Key=key,
        Conditions=[
            ['content-length-range', 1, max_bytes],
            ['starts-with', '$Content-Type', 'image/'],
        ],
        ExpiresIn=600,
    )
    return result


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


def verify_key_exists(key: str, s3_client=None) -> bool:
    """Check whether an object key exists in the Works R2 bucket.

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
    bool
        True if the object exists, False if it returns a 404 / NoSuchKey error.

    Raises
    ------
    Exception
        Any non-404 ClientError is re-raised so callers see genuine errors.
    """
    from botocore.exceptions import ClientError

    s3 = s3_client if s3_client is not None else _make_s3_client()
    try:
        s3.head_object(Bucket=settings.R2_WORKS_BUCKET, Key=key)
        return True
    except ClientError as e:
        error_code = e.response['Error']['Code']
        if error_code in ('404', 'NoSuchKey'):
            return False
        raise
