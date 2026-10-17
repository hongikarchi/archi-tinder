"""Taste-start endpoints: recognise tags from free text, then show the top-3 matches.

POST /api/v1/taste/recognize/  text -> tags + top-3 cards (one JEV call; every message is a fresh search,
                               any legacy `prev_tags` field is ignored)
POST /api/v1/taste/cards/      tags -> top-3 cards ("다시 찾기", no JEV call)
"""
import logging

from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import UserRateThrottle
from rest_framework.views import APIView

from .. import engine
from ..taste_start import matching, recognize_tags, tag_io
from ..throttles import LLMSearchThrottle

logger = logging.getLogger('apps.recommendation')

MAX_TEXT_LEN = 500
MAX_EXCLUDE_IDS = 100
MAX_TAGS = 30
CARD_COUNT = 3


def _bad(detail):
    return Response({'detail': detail}, status=status.HTTP_400_BAD_REQUEST)


_rebuild_tag = tag_io.rebuild_tag   # kept alias (old private name)


def _parse_tags(raw, field):
    """Return (tags, error_response). Invalid tags -> 400."""
    try:
        return tag_io.parse_tags(raw, MAX_TAGS), None
    except ValueError as exc:
        msg = str(exc)
        if msg.startswith('must be'):
            return None, _bad(f'{field} {msg}')
        return None, _bad(f'{field} contains an invalid tag')


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
        exclude_ids, err = _parse_exclude_ids(request.data.get('exclude_ids'))
        if err is not None:
            return err

        result = recognize_tags(text.strip())
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
