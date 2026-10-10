"""
validators.py -- apps/contests

http/https-only URL validation (BACK-CONTEST-2). Django's URLField accepts
ftp/ftps and Django validators do not run on save(), so Contest.save() calls
these explicitly. Used by model fields, Contest.save() and the serializer
(defense in depth) so a javascript:/data: URL can never reach a client.
"""
from urllib.parse import urlsplit

from django.core.exceptions import ValidationError

_ALLOWED_SCHEMES = ('http', 'https')


def is_http_url(value):
    """True only for an absolute http(s) URL with a host."""
    if not isinstance(value, str) or not value or value != value.strip():
        return False
    try:
        parts = urlsplit(value)
        host = parts.hostname
    except ValueError:
        return False
    return parts.scheme.lower() in _ALLOWED_SCHEMES and bool(host)


def validate_http_url(value):
    if not is_http_url(value):
        raise ValidationError(
            'Enter a valid http:// or https:// URL.', code='invalid_url_scheme',
        )
