"""
test_contest_interest.py -- interest API + poster report API (BACK-CONTEST-2).
"""
from datetime import timedelta

import pytest
from django.core.cache import cache
from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.utils import timezone

from apps.contests.models import Contest, ContestInterest, ContestPosterReport

LIST_URL = '/api/v1/contests/'


def _interest_url(pk):
    return f'/api/v1/contests/{pk}/interest/'


def _report_url(pk):
    return f'/api/v1/contests/{pk}/poster-report/'


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


@pytest.mark.django_db
class TestPosterReport:
    def test_creates_report_and_hides_poster(self, auth_client_a, user_a):
        _, profile = user_a
        c = _make(poster_url='https://img.example.com/p.jpg',
                  poster_status=Contest.POSTER_ALLOWED)
        assert auth_client_a.get(_detail_url(c.id)).data['poster_url'] == 'https://img.example.com/p.jpg'

        resp = auth_client_a.post(
            _report_url(c.id), {'reason': 'my poster', 'reporter_email': 'owner@example.com'},
            format='json',
        )
        assert resp.status_code == 201
        assert resp.data == {'status': 'received'}
        rep = ContestPosterReport.objects.get(contest=c)
        assert rep.reporter_id == profile.pk
        assert rep.reason == 'my poster'
        assert rep.reporter_email == 'owner@example.com'
        c.refresh_from_db()
        assert c.poster_status == Contest.POSTER_NONE
        detail = auth_client_a.get(_detail_url(c.id)).data
        assert detail['poster_url'] is None
        assert detail['poster_status'] == 'none'

    def test_body_optional(self, auth_client_a):
        c = _make()
        assert auth_client_a.post(_report_url(c.id)).status_code == 201
        assert ContestPosterReport.objects.filter(contest=c).count() == 1

    def test_invalid_email_400(self, auth_client_a):
        c = _make()
        resp = auth_client_a.post(_report_url(c.id), {'reporter_email': 'nope'}, format='json')
        assert resp.status_code == 400
        assert not ContestPosterReport.objects.exists()

    def test_unverified_becomes_none(self, auth_client_a):
        c = _make(poster_status=Contest.POSTER_UNVERIFIED)
        auth_client_a.post(_report_url(c.id))
        c.refresh_from_db()
        assert c.poster_status == Contest.POSTER_NONE

    def test_repeat_by_same_user_is_already_reported(self, auth_client_a):
        c = _make(poster_status=Contest.POSTER_ALLOWED, poster_url='https://i.example.com/p.png')
        assert auth_client_a.post(_report_url(c.id)).status_code == 201
        for _ in range(2):
            r = auth_client_a.post(_report_url(c.id))
            assert r.status_code == 200
            assert r.data == {'status': 'already_reported'}
        c.refresh_from_db()
        assert c.poster_status == Contest.POSTER_NONE
        assert ContestPosterReport.objects.filter(contest=c).count() == 1

    def test_repeat_after_operator_restore_does_not_rehide(self, auth_client_a):
        c = _make(poster_status=Contest.POSTER_ALLOWED, poster_url='https://i.example.com/p.png')
        auth_client_a.post(_report_url(c.id))
        Contest.objects.filter(pk=c.pk).update(poster_status=Contest.POSTER_ALLOWED)
        r = auth_client_a.post(_report_url(c.id))
        assert r.status_code == 200
        c.refresh_from_db()
        assert c.poster_status == Contest.POSTER_ALLOWED
        assert ContestPosterReport.objects.filter(contest=c).count() == 1

    def test_different_user_can_report_and_rehides(self, auth_client_a, auth_client_b):
        c = _make(poster_status=Contest.POSTER_ALLOWED, poster_url='https://i.example.com/p.png')
        auth_client_a.post(_report_url(c.id))
        Contest.objects.filter(pk=c.pk).update(poster_status=Contest.POSTER_ALLOWED)
        r = auth_client_b.post(_report_url(c.id))
        assert r.status_code == 201
        c.refresh_from_db()
        assert c.poster_status == Contest.POSTER_NONE
        assert ContestPosterReport.objects.filter(contest=c).count() == 2

    def test_no_profile_403(self, db):
        from django.contrib.auth.models import User
        from rest_framework.test import APIClient
        from rest_framework_simplejwt.tokens import RefreshToken
        user = User.objects.create_user(username='noprof', password='x')
        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION=f'Bearer {RefreshToken.for_user(user).access_token}')
        c = _make()
        assert client.post(_report_url(c.id)).status_code == 403
        assert not ContestPosterReport.objects.exists()

    def test_db_unique_constraint_one_per_reporter(self, user_a):
        from django.db import IntegrityError, transaction
        _, profile = user_a
        c = _make()
        ContestPosterReport.objects.create(contest=c, reporter=profile)
        with pytest.raises(IntegrityError):
            with transaction.atomic():
                ContestPosterReport.objects.create(contest=c, reporter=profile)
        # anonymous (reporter NULL) rows are exempt
        ContestPosterReport.objects.create(contest=c, reporter=None)
        ContestPosterReport.objects.create(contest=c, reporter=None)

    @pytest.mark.parametrize('st', [Contest.STATUS_HIDDEN, Contest.STATUS_PENDING])
    def test_404_unpublished(self, auth_client_a, st):
        c = _make(status=st, poster_status=Contest.POSTER_ALLOWED)
        assert auth_client_a.post(_report_url(c.id)).status_code == 404
        c.refresh_from_db()
        assert c.poster_status == Contest.POSTER_ALLOWED
        assert not ContestPosterReport.objects.exists()

    def test_401_anonymous(self, anon_client):
        c = _make()
        assert anon_client.post(_report_url(c.id)).status_code == 401

    def test_guest_allowed(self, user_a, auth_client_a):
        user, profile = user_a
        profile.is_guest = True
        profile.save(update_fields=['is_guest'])
        c = _make()
        assert auth_client_a.post(_report_url(c.id)).status_code == 201

    def test_reporter_set_null_on_user_delete(self, user_a, auth_client_a):
        user, _ = user_a
        c = _make()
        auth_client_a.post(_report_url(c.id))
        user.delete()
        rep = ContestPosterReport.objects.get(contest=c)
        assert rep.reporter_id is None

    def test_throttle(self, auth_client_a):
        c = _make()
        codes = [auth_client_a.post(_report_url(c.id)).status_code for _ in range(11)]
        assert codes[0] == 201
        assert codes[1:10] == [200] * 9
        assert codes[10] == 429
