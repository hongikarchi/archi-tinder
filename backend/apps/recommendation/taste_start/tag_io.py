"""
tag_io.py -- Rebuild tags from untrusted (axis, value, polarity) input.

Shared by the taste endpoints (browser-sent tags) and session/board storage
(stored tags are re-read the same way). `match`, labels and prob from the
caller are ignored: they come from our vocab/normalization via make_tag.

Error contract: every invalid input raises ValueError (the views turn it into
HTTP 400).
"""
from . import vocab
from .recognizer import make_tag

MAX_TAGS = 30
_TAG_AXES = ('style', 'atmosphere', 'color', 'country', 'material', 'element', 'built')


def _is_year(v):
    return isinstance(v, int) and not isinstance(v, bool) and 1800 <= v <= 2100


def rebuild_tag(item):
    """Rebuild one tag server-side from (axis, value, polarity) ONLY.

    Raises ValueError if invalid.
    """
    if not isinstance(item, dict):
        raise ValueError('tag must be an object')
    axis, value = item.get('axis'), item.get('value')
    polarity = item.get('polarity', 'want')
    if polarity not in ('want', 'exclude'):
        raise ValueError('bad polarity')
    if axis == 'year':
        if (not isinstance(value, (list, tuple)) or len(value) != 2
                or not all(v is None or _is_year(v) for v in value)
                or (value[0] is None and value[1] is None)
                or (value[0] is not None and value[1] is not None and value[0] > value[1])):
            raise ValueError('bad year value')
        return make_tag('year', (value[0], value[1]), polarity)
    if not isinstance(axis, str) or not isinstance(value, str):
        raise ValueError('bad axis/value')
    if axis == 'use':
        # `kind` only picks the vocab (program and typology share some values);
        # the value itself is validated against that vocab.
        client_match = item.get('match')
        is_typology = isinstance(client_match, dict) and 'typology_primary' in client_match
        kind = 'typology' if is_typology else 'program'
        table = vocab.TYPOLOGY if is_typology else vocab.PROGRAM
        if value not in table:
            raise ValueError('unknown use value')
        return make_tag('use', value, polarity, kind=kind)
    if axis not in _TAG_AXES or value not in vocab.AXIS_VOCAB[axis]:
        raise ValueError('unknown axis/value')
    return make_tag(axis, value, polarity)


def parse_tags(items, max_tags=MAX_TAGS):
    """Rebuild a list of tags. Raises ValueError on a bad list or any bad tag."""
    if not isinstance(items, list) or len(items) > max_tags:
        raise ValueError(f'must be a list of at most {max_tags} tags')
    tags = []
    for item in items:
        try:
            tags.append(rebuild_tag(item))
        except (ValueError, TypeError, KeyError):
            raise ValueError('contains an invalid tag') from None
    return tags
