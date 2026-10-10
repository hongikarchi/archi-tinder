"""
recognizer.py -- Turn a user's newest message into structured, DB-grounded tags.

Primary path: JEV (jev_client.call_jev) answers one choice question per axis.
Fallback path: a local longest-keyword-first dictionary built from the vocab
hints, used only when JEV is unavailable.

Both paths produce the same intermediate `Mention` list, which then goes
through one shared pipeline: merge (use / Warm / Industrial), year resolution,
carry-over of previous-round tags, and single-value-axis replacement.
"""
import functools
import logging
import re
from dataclasses import dataclass, field, replace
from typing import Optional

from . import vocab
from .jev_client import JevUnavailable, call_jev
from .normalization import raw_country_values, raw_material_values
from .questions import NONE, NOT_MENTIONED, build_questions, build_state, prev_question_id
from .year_rule import current_year, parse_years

logger = logging.getLogger('apps.recommendation')

# Axes that hold a single wanted value: a new want-tag replaces the old one.
SINGLE_AXES = ('use', 'style', 'atmosphere', 'color', 'country', 'year', 'built')
# Axes that may hold several tags at once.
MULTI_AXES = ('material', 'element')

_NEUTRAL = (NONE, NOT_MENTIONED)


# -- data classes -------------------------------------------------------------
@dataclass
class Tag:
    """One recognized condition, grounded in building-DB column values.

    `match` maps DB columns to the values a building must have (or, for
    polarity 'exclude', must not have); step 2 turns it into filters/penalties.
    """
    axis: str
    value: object              # str, or (min, max) tuple for axis 'year'
    polarity: str = 'want'     # 'want' | 'exclude'
    label_ko: str = ''
    label_en: str = ''
    match: dict = field(default_factory=dict)
    prob: Optional[float] = None

    @property
    def key(self):
        return (self.axis, _hashable(self.value))

    def to_dict(self):
        return {
            'axis': self.axis,
            'value': list(self.value) if isinstance(self.value, tuple) else self.value,
            'polarity': self.polarity,
            'label_ko': self.label_ko,
            'label_en': self.label_en,
            'match': self.match,
            'prob': self.prob,
        }

    @classmethod
    def from_dict(cls, data):
        value = data['value']
        if data['axis'] == 'year' and isinstance(value, list):
            value = tuple(value)
        return cls(
            axis=data['axis'],
            value=value,
            polarity=data.get('polarity', 'want'),
            label_ko=data.get('label_ko', ''),
            label_en=data.get('label_en', ''),
            match=data.get('match') or {},
            prob=data.get('prob'),
        )


@dataclass
class RecognitionResult:
    tags: list
    source: str                         # 'jev' | 'dictionary'
    raw_probabilities: dict = field(default_factory=dict)


@dataclass
class Mention:
    """A raw hit before merging: what the message said, not yet a Tag."""
    axis: str                  # use|style|atmosphere|color|country|material|element|era|built|year
    value: object
    polarity: str = 'want'     # want | exclude | drop (drop only from the dictionary path)
    prob: Optional[float] = None
    kind: Optional[str] = None  # 'program' | 'typology' for axis 'use'
    pos: int = 0


def _hashable(value):
    return tuple(value) if isinstance(value, list) else value


# -- Tag construction ---------------------------------------------------------
def _year_labels(value):
    lo, hi = value
    if lo is not None and hi is not None:
        if hi - lo == 9 and lo % 10 == 0:
            return f'{lo}년대', f'{lo}s'
        return f'{lo}–{hi}년', f'{lo}-{hi}'
    if lo is not None:
        return f'{lo}년 이후', f'{lo} and later'
    return f'{hi}년 이전', f'up to {hi}'


def make_tag(axis, value, polarity='want', prob=None, kind=None):
    """Build a Tag with labels and DB `match` for (axis, value)."""
    if axis == 'use':
        entry = (vocab.TYPOLOGY if kind == 'typology' else vocab.PROGRAM)[value]
        col = 'typology_primary' if kind == 'typology' else 'program'
        match = {col: [value]}
    elif axis == 'year':
        ko, en = _year_labels(value)
        return Tag('year', tuple(value), polarity, ko, en,
                   {'year_min': value[0], 'year_max': value[1]}, prob)
    else:
        entry = vocab.AXIS_VOCAB[axis][value]
        if axis == 'style':
            match = {'style': [value]}
            if value == 'Industrial':
                match['atmosphere'] = ['Industrial']
        elif axis == 'atmosphere':
            match = {'atmosphere': [value]}
            if value == 'Warm':
                match['color_tone'] = ['Warm']
        elif axis == 'color':
            match = {'color_tone': [value]}
        elif axis == 'material':
            match = {'material_visual': raw_material_values(value)}
        elif axis == 'country':
            match = {'location_country': raw_country_values(value)}
        elif axis == 'element':
            match = {'architectural_elements': [value],
                     'visual_description_contains': [value.lower()]}
        elif axis == 'built':
            match = {'built': value}
        else:
            raise ValueError(f'unsupported axis {axis!r}')
    return Tag(axis, value, polarity, entry.ko, entry.en, match, prob)


# -- shared pipeline ----------------------------------------------------------
_ERA_RANGES = {
    '21st_century': lambda: (2000, None),
    'modern_20th': lambda: (1900, 1999),
    'historic': lambda: (None, 1899),
    'recent': lambda: (current_year() - 5, None),
}


def _merge_mentions(mentions):
    """Apply the use / Warm / Industrial merge rules and single-axis dedupe."""
    out = []
    # use: typology wins over program (never both).
    typ = [m for m in mentions if m.axis == 'use' and m.kind == 'typology']
    use = typ if typ else [m for m in mentions if m.axis == 'use']
    rest = [m for m in mentions if m.axis != 'use']

    # Warm: atmosphere Warm and/or color Warm -> one atmosphere Warm mention.
    warm = [m for m in rest if m.value == 'Warm' and m.axis in ('atmosphere', 'color')]
    industrial = [m for m in rest if m.value == 'Industrial' and m.axis in ('style', 'atmosphere')]
    merged_ids = {id(m) for m in warm + industrial}
    rest = [m for m in rest if id(m) not in merged_ids]
    if warm:
        first = min(warm, key=lambda m: m.pos)
        rest.append(Mention('atmosphere', 'Warm', first.polarity, first.prob, pos=first.pos))
    if industrial:
        first = min(industrial, key=lambda m: m.pos)
        rest.append(Mention('style', 'Industrial', first.polarity, first.prob, pos=first.pos))

    seen_single = set()
    for m in sorted(use + rest, key=lambda m: m.pos):
        if m.axis in SINGLE_AXES and m.polarity == 'want':
            if m.axis in seen_single:
                continue
            seen_single.add(m.axis)
        out.append(m)
    return out


def _mention_to_tag(m):
    return make_tag(m.axis, m.value, m.polarity, m.prob, m.kind)


def _year_mention(text, mentions):
    """Numeric range from the text wins; otherwise map a JEV/dictionary era word."""
    era = [m for m in mentions if m.axis == 'era']
    mentions = [m for m in mentions if m.axis != 'era']
    years = parse_years(text)
    if years is not None:
        mentions.append(Mention('year', years, 'want'))
    elif era:
        mentions.append(Mention('year', _ERA_RANGES[era[0].value](), 'want',
                                era[0].prob, pos=era[0].pos))
    return mentions


def _combine(prev_tags, decisions, mentions, text):
    """Carry-over + new tags -> final tag list."""
    mentions = _year_mention(text, mentions)
    mentions = _merge_mentions(mentions)

    prev_by_key = {t.key: t for t in prev_tags}
    decisions = dict(decisions)
    new_mentions = []
    for m in mentions:
        if m.polarity in ('drop', 'exclude'):
            key = (m.axis, _hashable(m.value))
            prev = prev_by_key.get(key)
            if prev is not None:   # dictionary path: negation of an earlier tag
                decisions[prev_question_id(prev)] = m.polarity
                continue
            if m.polarity == 'drop':
                continue
        new_mentions.append(m)

    result = []
    for tag in prev_tags:
        d = decisions.get(prev_question_id(tag), 'keep')
        if d == 'drop':
            continue
        if d == 'exclude':
            tag = replace(tag, polarity='exclude')
        result.append(tag)

    for m in new_mentions:
        tag = _mention_to_tag(m)
        if tag.axis in SINGLE_AXES and tag.polarity == 'want':
            result = [t for t in result if not (t.axis == tag.axis and t.polarity == 'want')]
        result = [t for t in result if t.key != tag.key]
        result.append(tag)
    return result


# -- JEV path -----------------------------------------------------------------
def _prob(answer, choice):
    probs = answer.get('probabilities') or {}
    p = probs.get(choice)
    return float(p) if isinstance(p, (int, float)) else None


def _parse_jev(answers):
    """JEV answers -> (mentions, prev decisions, raw probabilities)."""
    mentions, decisions, raw = [], {}, {}
    axis_q = (
        ('program', 'use', vocab.PROGRAM, 'program'),
        ('typology', 'use', vocab.TYPOLOGY, 'typology'),
        ('style', 'style', vocab.STYLE, None),
        ('atmosphere', 'atmosphere', vocab.ATMOSPHERE, None),
        ('color_tone', 'color', vocab.COLOR, None),
        ('country', 'country', vocab.COUNTRY, None),
        ('era', 'era', vocab.ERA, None),
    )
    for qid, ans in answers.items():
        if isinstance(ans, dict):
            raw[qid] = ans.get('probabilities') or {}
    for qid, axis, options, kind in axis_q:
        ans = answers.get(qid) or {}
        choice = ans.get('choice')
        if choice in options:
            mentions.append(Mention(axis, choice, 'want', _prob(ans, choice), kind))
    ans = answers.get('built') or {}
    if ans.get('choice') in ('built_only', 'unbuilt_only'):
        mentions.append(Mention('built', ans['choice'], 'want', _prob(ans, ans['choice'])))
    for prefix, axis, options in (('mat_', 'material', vocab.MATERIAL),
                                  ('el_', 'element', vocab.ELEMENT)):
        for value in options:
            qid = prefix + (value if axis == 'material' else value.lower())
            ans = answers.get(qid) or {}
            choice = ans.get('choice')
            if choice in ('wanted', 'excluded'):
                mentions.append(Mention(axis, value, 'want' if choice == 'wanted' else 'exclude',
                                        _prob(ans, choice)))
    for qid, ans in answers.items():
        if qid.startswith('prev_') and isinstance(ans, dict):
            decisions[qid] = ans.get('choice', 'keep')
    return mentions, decisions, raw


# -- dictionary fallback ------------------------------------------------------
_DROP_RE = re.compile(r'^\s*(일|이|가|은|는|도)?\s*(필요\s*(는|가)?\s*없|아니어도|아니라도|상관\s*없|안\s*중요|중요하지\s*않)')
_EXCLUDE_RE = re.compile(r'^[은는이가을를도]?\s*(아니|말고|빼고|싫|제외|없이)')
_EN_NEG_RE = re.compile(r'\b(not|no|without)\s+(an?\s+|the\s+)?$')
_SPLIT_RE = re.compile(r'[,/;—]')
_PAREN_RE = re.compile(r'\([^)]*\)')
_HANGUL_RE = re.compile(r'[가-힣]')


def _keywords(entry, axis):
    """Dictionary keywords for one vocab entry (from hint + English label)."""
    words = {entry.en.lower()} if axis != 'era' else set()
    for tok in _SPLIT_RE.split(_PAREN_RE.sub('', entry.hint)):
        tok = tok.strip().lower()
        if not tok or any(c.isdigit() for c in tok) or len(tok.split()) > 3:
            continue
        words.add(tok)
    if axis in ('atmosphere', 'color', 'style'):
        # Bare Korean adjective stems: '따뜻한 분위기' -> '따뜻한', '따뜻'; '차분한' -> '차분'.
        for w in list(words):
            first = w.split()[0]
            if _HANGUL_RE.match(first) and first.endswith('한'):
                words.add(first)
                if len(first) >= 3:
                    words.add(first[:-1])
    out = set()
    for w in words:
        if len(w) >= 2 or (axis == 'material' and _HANGUL_RE.match(w)):
            out.add(w)
    return out


@functools.lru_cache(maxsize=1)
def _keyword_table():
    """[(compiled regex, keyword_len, [(axis, value, kind)])] longest keyword first."""
    sources = (
        ('use', vocab.PROGRAM, 'program'), ('use', vocab.TYPOLOGY, 'typology'),
        ('style', vocab.STYLE, None), ('atmosphere', vocab.ATMOSPHERE, None),
        ('color', vocab.COLOR, None), ('country', vocab.COUNTRY, None),
        ('material', vocab.MATERIAL, None), ('element', vocab.ELEMENT, None),
        ('era', vocab.ERA, None),
    )
    by_kw = {}
    for axis, options, kind in sources:
        for value, entry in options.items():
            for kw in _keywords(entry, axis):
                by_kw.setdefault(kw, []).append((axis, value, kind))
    table = []
    for kw in sorted(by_kw, key=len, reverse=True):
        if kw.isascii():
            pat = re.compile(r'(?<![a-z0-9])' + re.escape(kw) + r'(?![a-z0-9])')
        else:
            pat = re.compile(re.escape(kw))
        table.append((pat, by_kw[kw]))
    return table


def _polarity_at(text, start, end):
    tail = text[end:end + 12]
    if _DROP_RE.match(tail):
        return 'drop'
    if _EXCLUDE_RE.match(tail) or _EN_NEG_RE.search(text[max(0, start - 12):start]):
        return 'exclude'
    return 'want'


def _dictionary_mentions(text):
    """Longest-keyword-first substring matching with span masking."""
    low = text.lower()
    masked = low
    mentions = []
    for pat, targets in _keyword_table():
        spans = [m.span() for m in pat.finditer(masked)]
        for start, end in spans:
            pol = _polarity_at(low, start, end)
            for axis, value, kind in targets:
                mentions.append(Mention(axis, value, pol, None, kind, pos=start))
            masked = masked[:start] + '\x00' * (end - start) + masked[end:]
    return mentions


# -- public entry point -------------------------------------------------------
def recognize_tags(text, prev_tags):
    """Recognize tags in `text`, carrying over `prev_tags` from earlier rounds."""
    prev_tags = list(prev_tags or [])
    try:
        answers = call_jev(build_state(text, prev_tags), build_questions(prev_tags))
    except JevUnavailable as exc:
        logger.info('taste_start: JEV unavailable (%s), using dictionary fallback', exc)
        mentions = _dictionary_mentions(text)
        return RecognitionResult(_combine(prev_tags, {}, mentions, text), 'dictionary', {})
    mentions, decisions, raw = _parse_jev(answers)
    return RecognitionResult(_combine(prev_tags, decisions, mentions, text), 'jev', raw)
