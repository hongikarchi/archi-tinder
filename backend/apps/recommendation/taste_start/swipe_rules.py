"""
swipe_rules.py -- DB-free rules for the taste_v2 swipe path.

Spec: docs/plans/2026-10-11-taste-start-redesign.md §5-3/§5-4.
Settings are read at call time. `session_selector` is imported as a MODULE so
tests can patch `session_selector.select_next`.
"""
from django.conf import settings

from . import session_selector


def _rc():
    return settings.RECOMMENDATION


def should_enter_analyzing(like_count):
    """exploring -> analyzing once the like count reaches the v2 minimum."""
    return like_count >= int(_rc().get('taste_v2_analyzing_min_likes', 1))


def convergence_floor_met(swipes_in_session):
    """'Taste found' needs at least this many swipes made IN this session (§5-4).

    Pass `current_round - original_filters.get('round_offset', 0)` (a promoted
    session starts at current_round = seeded likes, which are not swipes here).
    """
    return swipes_in_session >= int(_rc().get('taste_v2_convergence_min_swipes', 8))


def lookahead(pool_ids, exposed_ids, emb, initial_batch, ctx, *, skip_next=False):
    """(pf1, pf2) lookahead ids for a v2 session.

    sync (skip_next=False): `exposed_ids` already contains the card being served
      now, so pf1 = select(exposed), pf2 = select(exposed + [pf1]).
    async (skip_next=True): the cache entry is read by the NEXT swipe, whose own
      next card is select(exposed); so its prefetch slots are the two picks after
      that one: a = select(exposed); pf1 = select(exposed + [a]);
      pf2 = select(exposed + [a, pf1]).
    """
    exposed = list(exposed_ids)

    def pick(exp):
        bid, _kind = session_selector.select_next(pool_ids, exp, emb, initial_batch, ctx)
        return bid

    if skip_next:
        a = pick(exposed)
        if not a:
            return None, None
        exposed = exposed + [a]
    pf1 = pick(exposed)
    if not pf1:
        return None, None
    pf2 = pick(exposed + [pf1])
    return pf1, pf2
