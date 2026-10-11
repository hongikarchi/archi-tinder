"""
test_next_deadline_jeongrim.py -- D9 apply -> submission transition at the KST boundary.

Seed values for the 정림 row: apply_deadline 2027-01-04 23:59 KST,
submission_deadline 2027-01-11 23:59 KST (stored UTC-aware by Django).
"""
from datetime import datetime
from zoneinfo import ZoneInfo

import pytest

from apps.contests.models import Contest
from apps.contests.serializers import ContestSerializer

KST = ZoneInfo('Asia/Seoul')
APPLY = datetime(2027, 1, 4, 23, 59, tzinfo=KST)
SUBMISSION = datetime(2027, 1, 11, 23, 59, tzinfo=KST)


@pytest.fixture
def jeongrim(db):
    return Contest.objects.create(
        title='정림', organizer='정림건축문화재단', source_url='https://www.junglimaward.com/',
        apply_deadline=APPLY, submission_deadline=SUBMISSION,
        status=Contest.STATUS_PUBLISHED,
    )


def _state(contest, now):
    data = ContestSerializer(contest, context={'now': now}).data
    return data['next_deadline_kind'], data['is_closed'], contest.next_deadline(now)


@pytest.mark.parametrize('now', [
    datetime(2026, 12, 1, 12, 0, tzinfo=KST),
    datetime(2027, 1, 4, 23, 58, tzinfo=KST),
])
def test_before_apply_deadline_is_apply(jeongrim, now):
    kind, closed, (k2, when) = _state(jeongrim, now)
    assert kind == k2 == 'apply'
    assert when == APPLY
    assert closed is False


def test_one_minute_after_apply_is_submission(jeongrim):
    now = datetime(2027, 1, 5, 0, 0, tzinfo=KST)
    kind, closed, (k2, when) = _state(jeongrim, now)
    assert kind == k2 == 'submission'
    assert when == SUBMISSION
    assert closed is False


def test_after_submission_is_closed(jeongrim):
    now = datetime(2027, 1, 12, 0, 0, tzinfo=KST)
    kind, closed, (k2, when) = _state(jeongrim, now)
    assert kind == k2 == 'submission'
    assert when == SUBMISSION
    assert closed is True


def test_stored_values_roundtrip_as_same_instants(jeongrim):
    jeongrim.refresh_from_db()
    assert jeongrim.apply_deadline == APPLY
    assert jeongrim.submission_deadline == SUBMISSION
