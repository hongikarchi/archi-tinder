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
    # urlsplit silently drops embedded tab/CR/LF; reject any control char.
    if any(ord(c) < 32 or ord(c) == 127 for c in value):
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


# Listing/aggregator sites whose image servers must not be hotlinked: a contest
# poster must be the ORGANIZER's own image (D6). Extend here. Subdomains match.
POSTER_BLOCKED_HOSTS = ('wevity.com',)


def validate_poster_url(value):
    """poster_url: None/'' allowed; else http(s) and not on a blocked listing host."""
    if value is None or value == '':
        return
    validate_http_url(value)
    host = (urlsplit(value).hostname or '').lower().rstrip('.')
    for blocked in POSTER_BLOCKED_HOSTS:
        if host == blocked or host.endswith('.' + blocked):
            raise ValidationError(
                'Poster images from %s are not allowed; use the organizer\'s own image.'
                % blocked,
                code='poster_host_blocked',
            )
