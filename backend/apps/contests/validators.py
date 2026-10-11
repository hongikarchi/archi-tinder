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


# Contest listing/aggregator sites. A published contest's source_url must be the
# OFFICIAL announcement, never one of these; their image servers must not be
# hotlinked either (a poster must be the ORGANIZER's own image, D6). Subdomains
# match. NOTE: the last two domains (thinkyou.co.kr = 씽유, theteams.kr = 더팀스)
# are unverified guesses -- verify them before relying on them.
LISTING_SITE_HOSTS = (
    'wevity.com', 'linkareer.com', 'lectus.kr', 'thinkcontest.com',
    'contestkorea.com', 'all-con.co.kr', 'thinkyou.co.kr', 'theteams.kr',
)

# Posters from any listing site are blocked (kept as a separate name for callers).
POSTER_BLOCKED_HOSTS = LISTING_SITE_HOSTS


def url_host(url):
    """Lower-cased hostname without a trailing dot ('' when unparseable)."""
    try:
        host = urlsplit(url).hostname or ''
    except ValueError:
        return ''
    return host.lower().rstrip('.')


def matching_host(url, hosts):
    """The entry of `hosts` that `url`'s host equals or is a subdomain of, else None."""
    host = url_host(url)
    if not host:
        return None
    for candidate in hosts:
        if host == candidate or host.endswith('.' + candidate):
            return candidate
    return None


def host_in(url, hosts):
    """True when `url`'s host is (a subdomain of) one of `hosts`; case-insensitive."""
    return matching_host(url, hosts) is not None


def validate_poster_url(value):
    """poster_url: None/'' allowed; else http(s) and not on a blocked listing host."""
    if value is None or value == '':
        return
    validate_http_url(value)
    blocked = matching_host(value, POSTER_BLOCKED_HOSTS)
    if blocked:
        raise ValidationError(
            'Poster images from %s are not allowed; use the organizer\'s own image.'
            % blocked,
            code='poster_host_blocked',
        )


def validate_publishable(status, source_url):
    """A 'published' contest needs an official http(s) source_url (not a listing site).

    hidden / pending have no requirement. Enforced in the model layer
    (Contest.save / ContestQuerySet) so every writer -- admin API, seed command,
    the future collector -- obeys it. The blank case is also a DB CHECK
    (contest_published_has_source); the listing-domain case is ORM-level only.
    """
    if status != 'published':
        return
    if not source_url:
        raise ValidationError(
            {'source_url': 'A published contest requires an official source URL.'},
            code='source_url_required',
        )
    if not is_http_url(source_url):
        raise ValidationError(
            {'source_url': 'Enter a valid http:// or https:// URL.'}, code='invalid_url_scheme',
        )
    blocked = matching_host(source_url, LISTING_SITE_HOSTS)
    if blocked:
        raise ValidationError(
            {'source_url': 'A published contest\'s source URL must be the official page, '
                           'not a listing site (%s).' % blocked},
            code='source_url_listing_site',
        )
