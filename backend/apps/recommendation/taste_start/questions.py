"""
questions.py -- Build the JEV `questions` + `state` payload for one user message.

One choice question per tag axis (program, typology, style, atmosphere,
color_tone, country, era, built), one per material group (`mat_<group>`), one
per architectural element (`el_<element>`), and one `prev_<axis>_<slug>` per
tag chosen in earlier rounds (keep / drop / exclude).

Prompt text is the validated spike prompt. STRICT is load-bearing: without it
accuracy collapsed (Korean text tagged country=South Korea, concrete tagged
Brutalist).
"""
import re

from . import vocab

STRICT = (
    ' Judge ONLY the newest message. Answer an option only if the newest message explicitly names it'
    ' (the word itself or a close synonym). Do not infer it from other words — e.g. concrete does NOT mean Brutalist,'
    ' earth/mud does NOT mean Vernacular, an architect name does NOT mean a country. The language the message is'
    ' written in (Korean, English) says nothing about the country. Conditions from earlier messages do not count.'
    ' If not explicitly named, answer none.'
)

TYPOLOGY_INSTRUCTION = (
    'Which SPECIFIC building type does the user ask for? Answer only for a specific type that is named'
    ' (e.g. 단독주택=House, 아파트=Apartment, 도서관=Library, 와이너리=Winery,'
    ' 유치원=Kindergarten, 기차역=Train Station). Generic words are NOT specific types and must be'
    ' answered none here (they belong to the broad-use question): 주거, 주거 건물, plain 주택,'
    ' 집합/공동 주거, housing, residential, 건물, 건축.'
)
ERA_INSTRUCTION = (
    'Which period of construction does the user ask for? Answer ONLY when the message contains an explicit'
    ' time-period word (근대, 20세기, 옛날, 고건축, 오래된, 최근, 요즘, 신축, 21세기).'
    ' Style words such as 모던, modern, modernist, 모더니즘, 현대적인, contemporary are STYLE,'
    ' not a period: answer none for them. Numbers are handled elsewhere.'
)
STRICT_ITEM = (
    ' Answer wanted/excluded only if THIS exact item (or a direct synonym) is named in the newest message.'
    ' Related items do NOT count: courtyard (중정) is not garden (정원) is not atrium (아트리움);'
    ' 중정 = Courtyard only, 정원 = Garden only, 아트리움 = Atrium only. Do not infer the item'
    ' from the building type or from other words. Otherwise answer not_mentioned.'
)

NONE = 'none'
NOT_MENTIONED = 'not_mentioned'


def _choice(instructions, options):
    """Axis Choice question: options + a 'none' fallback, STRICT appended."""
    criteria = vocab.criteria(options)
    criteria[NONE] = 'Not explicitly named in the newest message'
    return {'type': 'choice', 'instructions': instructions + STRICT, 'criteria': criteria}


def prev_question_id(tag):
    """Stable question id for a previous-round tag, e.g. 'prev_country_japan'."""
    value = tag.value
    if isinstance(value, (list, tuple)):
        value = '_'.join('' if v is None else str(v) for v in value)
    slug = re.sub(r'[^a-z0-9]+', '_', str(value).lower()).strip('_')
    return f'prev_{tag.axis}_{slug}'


def _tag_phrase(tag):
    return f'{tag.axis}: {tag.label_en}'


def build_questions(prev_tags):
    """Return the JEV questions dict for the newest message + earlier-round tags."""
    q = {
        'program': _choice('Which building use (program) does the user want to see?', vocab.PROGRAM),
        'style': _choice('Which architectural style does the user ask for?', vocab.STYLE),
        'atmosphere': _choice('Which spatial atmosphere or mood does the user ask for?',
                              vocab.ATMOSPHERE),
        'color_tone': _choice('Which colour palette does the user ask for? '
                              'Only answer if they talk about colour.', vocab.COLOR),
        'country': _choice('Which country should the buildings be in?', vocab.COUNTRY),
        'typology': _choice(TYPOLOGY_INSTRUCTION, vocab.TYPOLOGY),
        'era': _choice(ERA_INSTRUCTION, vocab.ERA),
        'built': {
            'type': 'choice',
            'instructions': 'Does the newest message say whether the buildings must be already built?'
                            ' Judge only the newest message; if it says nothing about built/unbuilt,'
                            ' answer not_mentioned.',
            'criteria': dict(vocab.criteria(vocab.BUILT),
                             **{NOT_MENTIONED: 'Nothing said about built vs unbuilt'}),
        },
    }
    for group, entry in vocab.MATERIAL.items():
        q[f'mat_{group}'] = {
            'type': 'choice',
            'instructions': f'What does the user say about this material: {entry.hint}?' + STRICT_ITEM,
            'criteria': {
                'wanted': 'The user wants buildings with this material',
                'excluded': 'The user says they do NOT want this material '
                            '(e.g. "벽돌은 아니고", "not brick")',
                NOT_MENTIONED: 'The material is not mentioned in the newest message',
            },
        }
    for name, entry in vocab.ELEMENT.items():
        q[f'el_{name.lower()}'] = {
            'type': 'choice',
            'instructions': f'What does the user say about this architectural element: {entry.hint}?'
                            + STRICT_ITEM,
            'criteria': {
                'wanted': 'The user wants buildings that have this element',
                'excluded': 'The user says they do NOT want this element (e.g. "not a courtyard")',
                NOT_MENTIONED: 'The element is not mentioned in the newest message',
            },
        }
    for tag in prev_tags:
        q[prev_question_id(tag)] = {
            'type': 'choice',
            'instructions': f'The user earlier asked for "{_tag_phrase(tag)}". '
                            'After the newest message, what is the status of that condition?',
            'criteria': {
                'keep': 'Still wanted, or not mentioned again',
                'drop': 'No longer required — user says it does not have to be that '
                        '(e.g. "일본일 필요는 없어", "상관없어")',
                'exclude': 'User now rejects it and does not want it '
                           '(e.g. "벽돌은 아니고", "말고")',
            },
        }
    return q


def build_state(text, prev_tags):
    """Context string sent as JEV `state`."""
    if not prev_tags:
        return f'Newest message from a user searching for architecture references:\n{text}'
    return ('A user is searching for architecture references.\n'
            f'Conditions chosen in earlier messages: {", ".join(_tag_phrase(t) for t in prev_tags)}\n'
            f'Newest message: {text}')
