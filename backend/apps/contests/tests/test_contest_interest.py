"""
test_contest_interest.py -- interest API (BACK-CONTEST-2).
"""
from datetime import timedelta

import pytest
from django.core.cache import cache
from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.utils import timezone

from apps.contests.models import Contest, ContestInterest

LIST_URL = '/api/v1/contests/'


def _interest_url(pk):
    return f'/api/v1/contests/{pk}/interest/'


def _detail_url(pk):
    return f'/api/v1/contests/{pk}/'


def _make(title='C', days=10, **kwargs):
    defaults = dict(
        title=title,
        organizer='Org',
        source_url='https://example.com/',
        submission_deadline=timezone.now() + timedelta(days=days),
        status=Contest.STATUS_PUBLISHED,
    )
    defaults.update(kwargs)
    return Contest.objects.create(**defaults)


@pytest.fixture(autouse=True)
def _clear_throttle_cache():
    cache.clear()
    yield
    cache.clear()


@pytest.mark.django_db
class TestInterest:
    def test_post_201_then_200_idempotent(self, auth_client_a):
        c = _make()
        r1 = auth_client_a.post(_interest_url(c.id))
        assert r1.status_code == 201
        assert r1.data == {'interest_count': 1, 'interested': True}
        r2 = auth_client_a.post(_interest_url(c.id))
        assert r2.status_code == 200
        assert r2.data == {'interest_count': 1, 'interested': True}
        assert ContestInterest.objects.filter(contest=c).count() == 1

    def test_double_post_same_user_count_is_one(self, auth_client_a):
        c = _make()
        auth_client_a.post(_interest_url(c.id))
        r = auth_client_a.post(_interest_url(c.id))
        assert r.data['interest_count'] == 1
        c.refresh_from_db()
        assert c.interest_count == 1

    def test_post_after_row_precreated_race_shape(self, auth_client_a, user_a):
        _, profile = user_a
        c = _make()
        ContestInterest.objects.create(user=profile, contest=c)  # "other request" won
        r = auth_client_a.post(_interest_url(c.id))
        assert r.status_code == 200
        assert r.data == {'interest_count': 1, 'interested': True}
        assert ContestInterest.objects.filter(contest=c).count() == 1

    def test_count_increments_per_user_and_decrements(self, auth_client_a, auth_client_b):
        c = _make()
        auth_client_a.post(_interest_url(c.id))
        auth_client_b.post(_interest_url(c.id))
        c.refresh_from_db()
        assert c.interest_count == 2
        assert auth_client_a.delete(_interest_url(c.id)).status_code == 204
        c.refresh_from_db()
        assert c.interest_count == 1

    def test_delete_idempotent_and_never_negative(self, auth_client_a):
        c = _make()
        assert auth_client_a.delete(_interest_url(c.id)).status_code == 204
        assert auth_client_a.delete(_interest_url(c.id)).status_code == 204
        c.refresh_from_db()
        assert c.interest_count == 0

    def test_counter_floor_at_zero_under_drift(self, user_a):
        _, profile = user_a
        c = _make()
        interest = ContestInterest.objects.create(user=profile, contest=c)
        Contest.objects.filter(pk=c.pk).update(interest_count=0)  # simulate drift
        interest.delete()
        c.refresh_from_db()
        assert c.interest_count == 0

    def test_cascade_user_delete_decrements(self, user_a):
        user, profile = user_a
        c = _make()
        ContestInterest.objects.create(user=profile, contest=c)
        c.refresh_from_db()
        assert c.interest_count == 1
        user.delete()
        c.refresh_from_db()
        assert c.interest_count == 0

    @pytest.mark.parametrize('st', [Contest.STATUS_HIDDEN, Contest.STATUS_PENDING])
    def test_404_on_unpublished(self, auth_client_a, st):
        c = _make(status=st)
        assert auth_client_a.post(_interest_url(c.id)).status_code == 404
        assert auth_client_a.delete(_interest_url(c.id)).status_code == 404

    def test_404_missing(self, auth_client_a):
        assert auth_client_a.post(_interest_url(999999)).status_code == 404

    def test_401_anonymous(self, anon_client):
        c = _make()
        assert anon_client.post(_interest_url(c.id)).status_code == 401
        assert anon_client.delete(_interest_url(c.id)).status_code == 401

    def test_allowed_after_deadline(self, auth_client_a):
        c = _make(days=-3)
        assert auth_client_a.post(_interest_url(c.id)).status_code == 201

    def test_interested_flag_per_user_list_and_detail(self, auth_client_a, auth_client_b):
        c1 = _make('one', days=2)
        c2 = _make('two', days=3)
        auth_client_a.post(_interest_url(c1.id))

        a_list = {r['id']: r['interested'] for r in auth_client_a.get(LIST_URL).data['results']}
        b_list = {r['id']: r['interested'] for r in auth_client_b.get(LIST_URL).data['results']}
        assert a_list == {c1.id: True, c2.id: False}
        assert b_list == {c1.id: False, c2.id: False}
        assert auth_client_a.get(_detail_url(c1.id)).data['interested'] is True
        assert auth_client_b.get(_detail_url(c1.id)).data['interested'] is False

    def test_list_query_count_constant(self, auth_client_a):
        for i in range(3):
            _make(f'a{i}', days=1 + i)
        auth_client_a.get(LIST_URL)  # warm auth/user caches
        with CaptureQueriesContext(connection) as small:
            auth_client_a.get(LIST_URL)
        for i in range(10):
            _make(f'b{i}', days=10 + i)
        with CaptureQueriesContext(connection) as big:
            auth_client_a.get(LIST_URL)
        assert len(big) == len(small)

    def test_throttle(self, auth_client_a):
        c = _make()
        codes = [auth_client_a.post(_interest_url(c.id)).status_code for _ in range(61)]
        assert codes[-1] == 429
        assert 429 not in codes[:60]

    def test_throttle_scope_registered(self):
        from django.conf import settings
        from apps.contests.views import ContestInterestThrottle
        assert ContestInterestThrottle.scope == 'contest_interest'
        assert settings.REST_FRAMEWORK['DEFAULT_THROTTLE_RATES']['contest_interest'] == '60/min'

    def test_guest_gets_verify_required(self, user_a, auth_client_a):
        _, profile = user_a
        profile.is_guest = True
        profile.save(update_fields=['is_guest'])
        c = _make()
        for method in (auth_client_a.post, auth_client_a.delete):
            r = method(_interest_url(c.id))
            assert r.status_code == 403
            assert r.data['detail'] == 'verify_required'
        assert ContestInterest.objects.filter(contest=c).count() == 0
        # Reading stays open to guests.
        assert auth_client_a.get(_detail_url(c.id)).status_code == 200
