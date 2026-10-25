"""
_pattern_text.py -- deterministic pattern_paragraph builders (pure, no Django/LLM).

2026-10-25 product decision: the persona report's pattern paragraph must ALWAYS
be present. When the LLM leaves it blank (or breaks a numeric guard) the server
builds it here from the same facts the LLM was handed, using the exact
templates from _report_prompts.py. HARD LINE: every number stated comes from a
fact dict (ratio_display / liked_with / liked_total) -- never invented.

Interpretive/generic fallbacks contain no digits at all.
"""
import re

# axis -> (ko modifier placed before "건물", en phrase placed after "with"/"had")
_KO_LABEL = {
    'style': '{v} 스타일의',
    'atmosphere': '{v} 분위기의',
    'color_tone': '{v} 색감의',
    'program': '{v} 용도의',
    'typology_primary': '{v} 유형의',
    'typology_tags': '{v} 유형의',
    'material_visual': '{v} 소재를 쓴',
    'architectural_elements': '{v} 요소가 있는',
    'architect_names': '{v} 설계의',
    'decade': '{v}대의',
    'location_country': '{v}에 있는',
}
_EN_LABEL = {
    'style': 'a {v} style',
    'atmosphere': 'a {v} atmosphere',
    'color_tone': 'a {v} color tone',
    'program': 'a {v} program',
    'typology_primary': 'a {v} typology',
    'typology_tags': 'a {v} typology',
    'material_visual': '{v} as a material',
    'architectural_elements': '{v} as an element',
    'architect_names': '{v} as the architect',
    'decade': 'a build date in the {v}',
    'location_country': 'a location in {v}',
}

# Axes (priority order) used to pick tags for the interpretive fallback.
_INTERPRETIVE_AXES = (
    'style', 'atmosphere', 'material_visual', 'program', 'typology_primary',
    'color_tone', 'architectural_elements', 'typology_tags',
)

GENERIC_KO = '고르신 건물들에서 뚜렷한 공간 취향이 보이기 시작했어요.'
GENERIC_EN = 'A clear spatial taste is starting to show in the buildings you chose.'

_DIGIT_RE = re.compile(r'\d+')


def _ko_feature(fact):
    return _KO_LABEL.get(fact['axis'], '{v}').format(v=fact['value'])


def _en_feature(fact):
    return _EN_LABEL.get(fact['axis'], '{v}').format(v=fact['value'])


def _like_sentence(fact, lang):
    qualitative = fact.get('others_rarely_liked') or fact.get('qualitative_only')
    if lang == 'ko':
        feat = _ko_feature(fact)
        if fact.get('others_rarely_liked'):
            return f'{feat} 건물이 아닌 건물은 거의 고르지 않으셨어요.'
        if qualitative:
            return f'{feat} 건물은 다른 건물보다 더 자주 고르셨어요.'
        return f'{feat} 건물은 다른 건물보다 약 {fact["ratio_display"]}배 자주 고르셨어요.'
    feat = _en_feature(fact)
    if fact.get('others_rarely_liked'):
        return f'buildings without {feat} were rarely chosen at all.'
    if qualitative:
        return f'the ones with {feat} were chosen more often than the other buildings shown.'
    return (
        f'the ones with {feat} were chosen about {fact["ratio_display"]}x '
        f'more often than the other buildings shown.'
    )


def _dislike_sentence(fact, lang):
    mostly = fact.get('dislike_word') == 'mostly'
    if lang == 'ko':
        return f'{_ko_feature(fact)} 건물은 {"대부분" if mostly else "여러 번"} 넘기셨어요.'
    return f'The buildings shown with {_en_feature(fact)} were {"mostly" if mostly else "often"} swiped past.'


def _composition_sentence(fact, lang):
    if lang == 'ko':
        return (
            f'좋아요한 {fact["liked_total"]}곳 중 {fact["liked_with"]}곳이 '
            f'{_ko_feature(fact)} 건물이었어요.'
        )
    return f'{fact["liked_with"]} of the {fact["liked_total"]} buildings you liked had {_en_feature(fact)}.'


def build_fact_paragraph(facts, lang):
    """Deterministic paragraph from like/dislike/composition facts, or '' if no facts.

    like/dislike -> opener + like sentences + dislike sentence (max 2 stated
    multipliers; extra like facts are restated qualitatively).
    """
    likes = [f for f in facts if f.get('polarity') == 'like']
    dislikes = [f for f in facts if f.get('polarity') == 'dislike']
    comps = [f for f in facts if f.get('polarity') == 'composition']

    if likes or dislikes:
        numbered = 0
        like_parts = []
        for fact in likes:
            if not (fact.get('others_rarely_liked') or fact.get('qualitative_only')):
                numbered += 1
                if numbered > 2:
                    fact = {**fact, 'qualitative_only': True}
            like_parts.append(_like_sentence(fact, lang))
        dislike_parts = [_dislike_sentence(f, lang) for f in dislikes]
        if lang == 'ko':
            text = '보여드린 건물 중 ' + ' '.join(like_parts + dislike_parts)
        else:
            parts = []
            for idx, sent in enumerate(like_parts + dislike_parts):
                parts.append(sent[0].lower() + sent[1:] if idx == 0 else sent[0].upper() + sent[1:])
            text = 'Among the buildings shown, ' + ' '.join(parts)
        return text.strip()

    if comps:
        return ' '.join(_composition_sentence(f, lang) for f in comps)
    return ''


def top_liked_tags(liked_tag_frequencies, limit=2):
    """Top `limit` (value) tags by liked count across the interpretive axes."""
    cands = []
    for prio, axis in enumerate(_INTERPRETIVE_AXES):
        for value, count in (liked_tag_frequencies or {}).get(axis, {}).items():
            cands.append((-count, prio, value))
    cands.sort()
    out = []
    for _c, _p, value in cands:
        if value not in out:
            out.append(value)
        if len(out) >= limit:
            break
    return out


def build_interpretive_paragraph(tags, lang):
    """Digit-free interpretive fallback from top liked tags; generic when no tags."""
    tags = [t for t in (tags or []) if t and not _DIGIT_RE.search(t)]
    if not tags:
        return GENERIC_KO if lang == 'ko' else GENERIC_EN
    if lang == 'ko':
        return f'고르신 건물들을 보면 {", ".join(tags[:2])} 쪽에 끌리는 취향이 보여요.'
    return f'Looking at the buildings you chose, you seem drawn to {" and ".join(tags[:2])}.'


def build_fallback_paragraph(facts, liked_tag_frequencies, lang):
    """facts -> interpretive from tags -> generic. Returns (text, kind)."""
    text = build_fact_paragraph(facts, lang)
    if text:
        return text, 'facts'
    tags = top_liked_tags(liked_tag_frequencies)
    return build_interpretive_paragraph(tags, lang), ('interpretive' if tags else 'generic')


def numbers_allowed(text, facts, pattern_mode):
    """Numeric guard for LLM output. interpretive: no digits at all.
    composition: only the fact counts / digits inside feature values.
    facts: not checked (decade values and multipliers legitimately appear)."""
    tokens = _DIGIT_RE.findall(text or '')
    if not tokens:
        return True
    if pattern_mode == 'interpretive':
        return False
    if pattern_mode == 'composition':
        allowed = set()
        for fact in facts:
            allowed.update(_DIGIT_RE.findall(str(fact.get('liked_with', ''))))
            allowed.update(_DIGIT_RE.findall(str(fact.get('liked_total', ''))))
            allowed.update(_DIGIT_RE.findall(str(fact.get('value', ''))))
        return all(t in allowed for t in tokens)
    return True
