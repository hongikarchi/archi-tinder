"""Request validation for the feedback endpoints. Every failure raises ValidationFail (-> 400)."""
import re

from apps.recommendation.taste_start import tag_io

MAX_ROUND_KEY = 64
MAX_QUERY = 500
MAX_COMMENT = 500
MAX_BLD_ID = 20
MAX_COUNT = 30
MAX_LIST = 30
ROUND_KEY_RE = re.compile(r'^r\d{10,16}\Z')   # frontend: `r${Date.now()}`

REASONS = ('tag', 'photo', 'info', 'etc')
SUB_REASONS = {
    'photo': ('other_building', 'drawing_or_logo', 'not_visible'),
    'info': ('country', 'city', 'year', 'use', 'unbuilt', 'duplicate'),
}


class ValidationFail(ValueError):
    pass


def _is_int(v):
    return isinstance(v, int) and not isinstance(v, bool)


def _text(data, key, max_len, required=True):
    v = data.get(key)
    if not isinstance(v, str) or (required and not v.strip()):
        raise ValidationFail(f'{key} must be a non-empty string' if required else f'{key} must be a string')
    if len(v) > max_len:
        raise ValidationFail(f'{key} must be at most {max_len} characters')
    return v


def _clamp_prob(v):
    """Client prob is diagnostic only: float in [0, 1] or None."""
    if isinstance(v, bool) or not isinstance(v, (int, float)) or v != v:
        return None
    return min(1.0, max(0.0, float(v)))


def check_round_key(v):
    if not isinstance(v, str) or len(v) > MAX_ROUND_KEY or not ROUND_KEY_RE.match(v):
        raise ValidationFail('round_key is invalid')
    return v


def check_common(data):
    """Fields shared by both report types. Returns clean values + parsed Tag objects."""
    round_key = check_round_key(data.get('round_key'))
    query_text = _text(data, 'query_text', MAX_QUERY, required=False)
    source = data.get('source')
    if source not in ('jev', 'dictionary'):
        raise ValidationFail('source must be jev or dictionary')
    language = data.get('language')
    if language not in ('ko', 'en'):
        raise ValidationFail('language must be ko or en')
    raw_tags = data.get('tags')
    try:
        parsed = tag_io.parse_tags(raw_tags)
    except ValueError as exc:
        raise ValidationFail(f'tags {exc}') from None
    tags = []
    for raw, tag in zip(raw_tags, parsed):
        d = tag.to_dict()
        d['prob'] = _clamp_prob(raw.get('prob'))
        tags.append(d)
    return {'round_key': round_key, 'query_text': query_text, 'source': source,
            'language': language, 'tags': tags, 'parsed_tags': parsed}


def check_comment(data):
    c = data.get('comment', '')
    if c is None:
        c = ''
    if not isinstance(c, str) or len(c) > MAX_COMMENT:
        raise ValidationFail(f'comment must be a string of at most {MAX_COMMENT} characters')
    return c


def check_card_fields(data):
    bld_id = _text(data, 'canonical_bld_id', MAX_BLD_ID)
    rank = data.get('card_rank')
    if not _is_int(rank) or not 1 <= rank <= 3:
        raise ValidationFail('card_rank must be an integer 1-3')
    out = {'canonical_bld_id': bld_id, 'card_rank': rank}
    for key in ('hit', 'total'):
        v = data.get(key)
        if not _is_int(v) or not 0 <= v <= MAX_COUNT:
            raise ValidationFail(f'{key} must be an integer 0-{MAX_COUNT}')
        out[key] = v
    reason = data.get('reason')
    if reason is not None and reason not in REASONS:
        raise ValidationFail('reason must be one of tag, photo, info, etc')
    subs = data.get('sub_reasons', [])
    if subs is None:
        subs = []
    if not isinstance(subs, list) or not all(isinstance(s, str) for s in subs):
        raise ValidationFail('sub_reasons must be a list of strings')
    if len(subs) > MAX_LIST:
        raise ValidationFail('sub_reasons is too long')
    allowed = SUB_REASONS.get(reason, ())
    if any(s not in allowed for s in subs):
        raise ValidationFail('invalid sub_reasons for this reason')
    out['reason'] = reason
    out['sub_reasons'] = list(dict.fromkeys(subs))
    return out


def check_wrong_tags_in_tags(raw, parsed_tags, allowed):
    """Each wrong tag {axis, value} must be one of the parsed tags. Returns clean dicts."""
    if raw is None:
        raw = []
    if not isinstance(raw, list):
        raise ValidationFail('wrong_tags must be a list')
    if len(raw) > MAX_LIST:
        raise ValidationFail('wrong_tags is too long')
    if raw and not allowed:
        raise ValidationFail('wrong_tags is only allowed when reason is tag')
    known = {(t.axis, repr(t.to_dict()['value'])) for t in parsed_tags}
    out, seen = [], set()
    for w in raw:
        if not isinstance(w, dict) or 'axis' not in w or 'value' not in w:
            raise ValidationFail('wrong_tags items must be {axis, value}')
        value = w['value']
        if not isinstance(w['axis'], str) or not (
                isinstance(value, str) or (isinstance(value, list) and len(value) == 2)):
            raise ValidationFail('wrong_tags items must be {axis, value}')
        key = (w['axis'], repr(value))
        if key not in known:
            raise ValidationFail('wrong_tags must be among tags')
        if key not in seen:
            seen.add(key)
            out.append({'axis': w['axis'], 'value': w['value']})
    return out
