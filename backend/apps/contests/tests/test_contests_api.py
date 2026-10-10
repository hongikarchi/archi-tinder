"""
test_contests_api.py -- GET contests/ and GET contests/<id>/ (BACK-CONTEST-1).
"""
from datetime import datetime, timedelta, timezone as dt_tz

import pytest
from django.utils import timezone

from apps.contests.models import Contest, compute_next_deadline

LIST_URL = '/api/v1/contests/'


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


@pytest.mark.django_db
class TestAuth:
    def test_list_requires_auth(self, anon_client):
        assert anon_client.get(LIST_URL).status_code == 401

    def test_detail_requires_auth(self, anon_client):
        c = _make()
        assert anon_client.get(_detail_url(c.id)).status_code == 401


@pytest.mark.django_db
class TestList:
    def test_filters_and_orders(self, auth_client_a):
        late = _make('late', days=30)
        soon = _make('soon', days=2)
        mid = _make('mid', days=10)
        _make('hidden', days=5, status=Contest.STATUS_HIDDEN)
        _make('pending', days=5, status=Contest.STATUS_PENDING)
        _make('past', days=-1)

        resp = auth_client_a.get(LIST_URL)
        assert resp.status_code == 200
        ids = [r['id'] for r in resp.data['results']]
        assert ids == [soon.id, mid.id, late.id]

    def test_capped_at_100(self, auth_client_a):
        for i in range(105):
            _make(f'c{i}', days=1 + i)
        resp = auth_client_a.get(LIST_URL)
        assert len(resp.data['results']) == 100

    def test_notice_date_null_ok(self, auth_client_a):
        _make(notice_date=None)
        resp = auth_client_a.get(LIST_URL)
        assert resp.data['results'][0]['notice_date'] is None

    def test_serializer_fields(self, auth_client_a):
        _make()
        row = auth_client_a.get(LIST_URL).data['results'][0]
        assert set(row) == {
            'id', 'title', 'organizer', 'organizer_type',
            'submission_deadline', 'apply_deadline', 'notice_date',
            'theme', 'summary', 'eligibility', 'team_size',
            'source_url', 'listing_source', 'listing_url',
            'poster_url', 'poster_credit',
            'interest_count', 'interested', 'next_deadline_kind', 'next_deadline', 'is_closed',
        }
        assert row['is_closed'] is False
        # ISO 8601 with offset.
        assert datetime.fromisoformat(row['submission_deadline'].replace('Z', '+00:00')).tzinfo


@pytest.mark.django_db
class TestDetail:
    def test_past_deadline_published_opens(self, auth_client_a):
        c = _make(days=-3)
        resp = auth_client_a.get(_detail_url(c.id))
        assert resp.status_code == 200
        assert resp.data['is_closed'] is True
        assert resp.data['next_deadline_kind'] == 'submission'

    @pytest.mark.parametrize('st', [Contest.STATUS_HIDDEN, Contest.STATUS_PENDING])
    def test_hidden_pending_404(self, auth_client_a, st):
        c = _make(status=st)
        assert auth_client_a.get(_detail_url(c.id)).status_code == 404

    def test_missing_404(self, auth_client_a):
        assert auth_client_a.get(_detail_url(999999)).status_code == 404


@pytest.mark.django_db
class TestPoster:
    def test_poster_url_returned_when_set(self, auth_client_a):
        url = 'https://example.com/poster.png'
        c = _make(poster_url=url)
        for resp in (auth_client_a.get(LIST_URL), auth_client_a.get(_detail_url(c.id))):
            row = resp.data['results'][0] if 'results' in resp.data else resp.data
            assert row['poster_url'] == url
            assert 'poster_status' not in row
            assert 'takedown_email' not in row

    def test_poster_url_null_when_unset(self, auth_client_a):
        c = _make(poster_url=None)
        assert auth_client_a.get(_detail_url(c.id)).data['poster_url'] is None

    @pytest.mark.parametrize('url,expected', [
        ('http://example.com/p.png', 'http://example.com/p.png'),
        ('https://example.com/p.png', 'https://example.com/p.png'),
        ('javascript:alert(1)', None),
        ('ftp://example.com/p.png', None),
        ('', None),
        (None, None),
    ])
    def test_serializer_poster_url_http_only(self, url, expected):
        from apps.contests.serializers import ContestSerializer
        c = Contest(
            title='T', organizer='O', source_url='https://example.com/',
            submission_deadline=timezone.now() + timedelta(days=5), poster_url=url,
        )
        assert ContestSerializer(c).data['poster_url'] == expected


class TestNextDeadline:
    NOW = datetime(2026, 10, 10, 0, 0, tzinfo=dt_tz.utc)

    def test_apply_in_future(self):
        apply_ = self.NOW + timedelta(days=3)
        sub = self.NOW + timedelta(days=30)
        assert compute_next_deadline(apply_, sub, self.NOW) == ('apply', apply_)

    def test_apply_in_past(self):
        apply_ = self.NOW - timedelta(days=1)
        sub = self.NOW + timedelta(days=30)
        assert compute_next_deadline(apply_, sub, self.NOW) == ('submission', sub)

    def test_apply_null(self):
        sub = self.NOW + timedelta(days=30)
        assert compute_next_deadline(None, sub, self.NOW) == ('submission', sub)

    def test_apply_equal_now_is_not_future(self):
        sub = self.NOW + timedelta(days=30)
        assert compute_next_deadline(self.NOW, sub, self.NOW) == ('submission', sub)

    def test_model_method(self):
        c = Contest(
            apply_deadline=self.NOW + timedelta(days=1),
            submission_deadline=self.NOW + timedelta(days=9),
        )
        assert c.next_deadline(self.NOW)[0] == 'apply'

    @pytest.mark.django_db
    def test_api_kind(self, auth_client_a):
        a = _make('a', days=30, apply_deadline=timezone.now() + timedelta(days=2))
        b = _make('b', days=31, apply_deadline=timezone.now() - timedelta(days=2))
        c = _make('c', days=32)
        rows = {r['id']: r for r in auth_client_a.get(LIST_URL).data['results']}
        assert rows[a.id]['next_deadline_kind'] == 'apply'
        assert rows[a.id]['next_deadline'] == rows[a.id]['apply_deadline']
        assert rows[b.id]['next_deadline_kind'] == 'submission'
        assert rows[c.id]['next_deadline_kind'] == 'submission'
        assert rows[c.id]['next_deadline'] == rows[c.id]['submission_deadline']
