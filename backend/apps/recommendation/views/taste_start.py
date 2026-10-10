"""Taste-start endpoints: recognise tags from free text, then show the top-3 matches.

POST /api/v1/taste/recognize/  text (+ prev_tags) -> tags + top-3 cards (one JEV call)
POST /api/v1/taste/cards/      tags -> top-3 cards ("다시 찾기", no JEV call)
"""
import logging

from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import UserRateThrottle
from rest_framework.views import APIView

from .. import engine
from ..taste_start import matching, recognize_tags, vocab
from ..taste_start.recognizer import make_tag
from ..throttles import LLMSearchThrottle

logger = logging.getLogger('apps.recommendation')

MAX_TEXT_LEN = 500
MAX_EXCLUDE_IDS = 100
MAX_TAGS = 30
CARD_COUNT = 3
_TAG_AXES = ('style', 'atmosphere', 'color', 'country', 'material', 'element', 'built')


def _bad(detail):
    return Response({'detail': detail}, status=status.HTTP_400_BAD_REQUEST)


def _is_year(v):
    return isinstance(v, int) and not isinstance(v, bool) and 1800 <= v <= 2100


def _rebuild_tag(item):
    """Rebuild one client tag server-side from (axis, value, polarity) ONLY.

    `match`, labels and prob from the client are ignored (trust boundary): they
    come from our vocab/normalization via make_tag. Raises ValueError if invalid.
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


def _parse_tags(raw, field):
    """Return (tags, error_response). Invalid tags -> 400."""
    if not isinstance(raw, list) or len(raw) > MAX_TAGS:
        return None, _bad(f'{field} must be a list of at most {MAX_TAGS} tags')
    tags = []
    for item in raw:
        try:
            tags.append(_rebuild_tag(item))
        except (ValueError, TypeError, KeyError):
            return None, _bad(f'{field} contains an invalid tag')
    return tags, None


def _parse_exclude_ids(raw):
    if raw is None:
        return [], None
    if (not isinstance(raw, list) or len(raw) > MAX_EXCLUDE_IDS
            or not all(isinstance(i, str) and i for i in raw)):
        return None, _bad(f'exclude_ids must be a list of at most {MAX_EXCLUDE_IDS} non-empty strings')
    return raw, None


def _build_cards(tags, exclude_ids):
    """Top-3 cards in match order: [{card, matched_keys, hit, total}]."""
    if not matching.has_want_tags(tags):
        n = CARD_COUNT + len(exclude_ids)
        cards = [c for c in engine.get_diverse_random(n=n)
                 if c.get('canonical_bld_id') not in set(exclude_ids)][:CARD_COUNT]
        return [{'card': c, 'matched_keys': [], 'hit': 0, 'total': 0} for c in cards]

    matches = matching.top_matches(tags, exclude_ids=exclude_ids, limit=CARD_COUNT)
    cards = engine.get_buildings_by_ids([m['canonical_bld_id'] for m in matches])
    by_id = {c.get('canonical_bld_id'): c for c in cards}
    return [
        {
            'card': by_id[m['canonical_bld_id']],
            'matched_keys': [list(k) if isinstance(k, tuple) else k for k in m['matched_keys']],
            'hit': m['hit'],
            'total': m['total'],
        }
        for m in matches if m['canonical_bld_id'] in by_id
    ]


class TasteRecognizeView(APIView):
    permission_classes = [IsAuthenticated]
    throttle_classes = [LLMSearchThrottle]

    def post(self, request):
        text = request.data.get('text')
        if not isinstance(text, str) or not text.strip():
            return _bad('text is required')
        if len(text) > MAX_TEXT_LEN:
            return _bad(f'text must be at most {MAX_TEXT_LEN} characters')
        prev_tags, err = _parse_tags(request.data.get('prev_tags') or [], 'prev_tags')
        if err is not None:
            return err
        exclude_ids, err = _parse_exclude_ids(request.data.get('exclude_ids'))
        if err is not None:
            return err

        result = recognize_tags(text.strip(), prev_tags)
        logger.debug('taste recognize probabilities: %s', result.raw_probabilities)
        return Response({
            'source': result.source,
            'tags': [t.to_dict() for t in result.tags],
            'cards': _build_cards(result.tags, exclude_ids),
        })


class TasteCardsView(APIView):
    permission_classes = [IsAuthenticated]
    throttle_classes = [UserRateThrottle]  # scope 'user' (300/min); no LLM call here

    def post(self, request):
        if 'tags' not in request.data:
            return _bad('tags is required')
        tags, err = _parse_tags(request.data.get('tags'), 'tags')
        if err is not None:
            return err
        exclude_ids, err = _parse_exclude_ids(request.data.get('exclude_ids'))
        if err is not None:
            return err
        return Response({'cards': _build_cards(tags, exclude_ids)})
