"""Admin contest management API (FULL-CONTEST-2)."""
from datetime import timedelta

import pytest
from django.utils import timezone

from apps.admin_dashboard.models import AdminAuditLog
from apps.admin_dashboard.testing import make_operator_client
from apps.contests.models import Contest

LIST_URL = '/api/v1/admin/dashboard/contests/'
OFFICIAL = 'https://www.junglimaward.com/2027'


def detail_url(pk):
    return f'{LIST_URL}{pk}/'


def _make(title='C', days=10, **kw):
    defaults = dict(
        title=title, organizer='Org', source_url=OFFICIAL,
        submission_deadline=timezone.now() + timedelta(days=days),
        status=Contest.STATUS_PUBLISHED,
    )
    defaults.update(kw)
    return Contest.objects.create(**defaults)


def _payload(**o):
    body = {
        'title': '새 공모전', 'organizer': '주최', 'organizer_type': 'association',
        'status': 'pending', 'submission_deadline': '2026-10-28T18:00',
    }
    body.update(o)
    return body


def _audit(action=None):
    qs = AdminAuditLog.objects.all()
    return qs.filter(action=action) if action else qs


@pytest.mark.django_db
class TestPermissions:
    def test_anonymous_401_on_all(self, api_client):
        c = _make()
        assert api_client.get(LIST_URL).status_code == 401
        assert api_client.post(LIST_URL, _payload(), format='json').status_code == 401
        assert api_client.patch(detail_url(c.pk), {'title': 'x'}, format='json').status_code == 401

    @pytest.mark.parametrize('variant', [
        {'guest': True}, {'in_list': False}, {'is_staff': False}, {'google': False},
    ])
    def test_non_admin_403_on_all(self, settings, variant):
        client, _ = make_operator_client(settings, **variant)
        c = _make()
        assert client.get(LIST_URL).status_code == 403
        assert client.post(LIST_URL, _payload(), format='json').status_code == 403
        assert client.patch(detail_url(c.pk), {'title': 'x'}, format='json').status_code == 403
        assert Contest.objects.count() == 1
        c.refresh_from_db()
        assert c.title == 'C'
        assert _audit().count() == 0

    def test_plain_authenticated_user_403(self, settings):
        # A regular logged-in user (not even staff).
        from apps.admin_dashboard.testing import make_operator_client as mk
        client, _ = mk(settings, username='plain', email='plain@example.com', is_staff=False, in_list=False)
        assert client.get(LIST_URL).status_code == 403

    def test_no_delete(self, admin_client):
        c = _make()
        assert admin_client.delete(detail_url(c.pk)).status_code == 405
        assert Contest.objects.filter(pk=c.pk).exists()


@pytest.mark.django_db
class TestList:
    def test_includes_hidden_pending_and_past(self, admin_client):
        _make('pub', days=5)
        _make('hid', days=6, status='hidden')
        _make('pen', days=7, status='pending')
        _make('past', days=-3)
        body = admin_client.get(LIST_URL).json()
        assert body['count'] == 4
        assert {r['title'] for r in body['results']} == {'pub', 'hid', 'pen', 'past'}

    def test_order_newest_deadline_first(self, admin_client):
        _make('a', days=1)
        _make('b', days=30)
        _make('c', days=10)
        titles = [r['title'] for r in admin_client.get(LIST_URL).json()['results']]
        assert titles == ['b', 'c', 'a']

    def test_status_filter(self, admin_client):
        _make('pub')
        _make('pen', status='pending')
        rows = admin_client.get(LIST_URL, {'status': 'pending'}).json()['results']
        assert [r['title'] for r in rows] == ['pen']
        assert admin_client.get(LIST_URL, {'status': 'bogus'}).status_code == 400

    def test_pagination(self, admin_client):
        for i in range(5):
            _make(f't{i}', days=i + 1)
        body = admin_client.get(LIST_URL, {'page': 2, 'page_size': 2}).json()
        assert body['count'] == 5
        assert len(body['results']) == 2
        assert admin_client.get(LIST_URL, {'page_size': 9999}).json()['count'] == 5

    def test_row_fields_and_raw_values(self, admin_client):
        c = _make(
            status='hidden', listing_url='https://lectus.kr/x', listing_source='lectus',
            poster_url='https://i.example.com/p.jpg', team_size='3인', import_key='k1',
            submission_deadline=timezone.now() - timedelta(days=1),
        )
        row = admin_client.get(LIST_URL).json()['results'][0]
        assert set(row) == {
            'id', 'title', 'organizer', 'organizer_type', 'status', 'submission_deadline',
            'apply_deadline', 'notice_date', 'theme', 'summary', 'eligibility', 'team_size',
            'source_url', 'listing_source', 'listing_url', 'poster_url', 'poster_credit',
            'interest_count', 'import_key', 'created_at', 'updated_at', 'last_verified_at',
            'is_closed',
        }
        assert row['id'] == c.pk
        assert row['status'] == 'hidden'
        assert row['is_closed'] is True
        assert row['import_key'] == 'k1'
        assert row['listing_url'] == 'https://lectus.kr/x'
        assert row['last_verified_at'] is None


@pytest.mark.django_db
class TestCreate:
    def test_happy_path(self, admin_client):
        resp = admin_client.post(LIST_URL, _payload(
            source_url=OFFICIAL, status='published', theme='t', apply_deadline='2026-10-20T09:00+09:00',
        ), format='json')
        assert resp.status_code == 201, resp.content
        body = resp.json()
        c = Contest.objects.get(pk=body['id'])
        assert c.status == 'published'
        assert c.last_verified_at is not None
        assert body['interest_count'] == 0
        assert c.apply_deadline.isoformat() == '2026-10-20T00:00:00+00:00'
        logs = _audit('contest_create')
        assert logs.count() == 1
        log = logs.get()
        assert (log.target_type, log.target_id) == ('contest', str(c.pk))
        assert log.payload == {'title': '새 공모전', 'status': 'published'}

    def test_default_status_hidden_when_omitted(self, admin_client):
        body = _payload()
        del body['status']
        resp = admin_client.post(LIST_URL, body, format='json')
        assert resp.status_code == 201
        assert resp.json()['status'] == 'hidden'

    def test_read_only_fields_ignored(self, admin_client):
        resp = admin_client.post(LIST_URL, _payload(
            interest_count=99, import_key='x', created_at='2000-01-01T00:00:00Z',
        ), format='json')
        assert resp.status_code == 201
        c = Contest.objects.get()
        assert c.interest_count == 0 and c.import_key is None
        assert c.created_at.year != 2000

    @pytest.mark.parametrize('source', ['', 'https://www.wevity.com/?c=find', 'https://lectus.kr/x'])
    def test_publish_rule_400_not_500(self, admin_client, source):
        resp = admin_client.post(LIST_URL, _payload(status='published', source_url=source), format='json')
        assert resp.status_code == 400
        assert 'source_url' in resp.json()
        assert Contest.objects.count() == 0
        assert _audit().count() == 0

    def test_pending_with_listing_source_allowed(self, admin_client):
        resp = admin_client.post(LIST_URL, _payload(source_url='https://www.wevity.com/x'), format='json')
        assert resp.status_code == 201

    @pytest.mark.parametrize('field,value', [
        ('source_url', 'javascript:alert(1)'), ('listing_url', 'ftp://x.com/a'),
        ('poster_url', 'https://www.wevity.com/p.jpg'), ('poster_url', 'data:image/png;base64,AA'),
        ('status', 'bogus'), ('organizer_type', 'bogus'), ('title', ''), ('title', 'x' * 201),
        ('submission_deadline', 'tomorrow'), ('submission_deadline', '2026-10-28'),
        ('submission_deadline', None), ('apply_deadline', 'garbage'),
    ])
    def test_validation_400(self, admin_client, field, value):
        resp = admin_client.post(LIST_URL, _payload(**{field: value}), format='json')
        assert resp.status_code == 400
        assert field in resp.json()
        assert Contest.objects.count() == 0
        assert _audit().count() == 0

    def test_missing_required_400(self, admin_client):
        resp = admin_client.post(LIST_URL, {'title': 'x'}, format='json')
        assert resp.status_code == 400
        assert {'organizer', 'submission_deadline'} <= set(resp.json())


@pytest.mark.django_db
class TestKstDatetimes:
    def test_naive_interpreted_as_kst(self, admin_client):
        resp = admin_client.post(LIST_URL, _payload(
            submission_deadline='2026-10-28T18:00', apply_deadline='2026-10-20T09:30:00',
        ), format='json')
        assert resp.status_code == 201
        c = Contest.objects.get()
        assert c.submission_deadline.isoformat() == '2026-10-28T09:00:00+00:00'
        assert c.apply_deadline.isoformat() == '2026-10-20T00:30:00+00:00'
        assert resp.json()['submission_deadline'] == '2026-10-28T18:00:00+09:00'

    def test_offset_preserved(self, admin_client):
        resp = admin_client.post(LIST_URL, _payload(submission_deadline='2026-10-28T18:00:00+09:00'), format='json')
        assert resp.status_code == 201
        assert Contest.objects.get().submission_deadline.isoformat() == '2026-10-28T09:00:00+00:00'
        resp = admin_client.post(LIST_URL, _payload(title='z', submission_deadline='2026-10-28T18:00:00Z'), format='json')
        assert resp.status_code == 201
        assert Contest.objects.get(title='z').submission_deadline.isoformat() == '2026-10-28T18:00:00+00:00'

    def test_patch_naive_interpreted_as_kst(self, admin_client):
        c = _make()
        resp = admin_client.patch(detail_url(c.pk), {'submission_deadline': '2026-10-28T18:00'}, format='json')
        assert resp.status_code == 200
        c.refresh_from_db()
        assert c.submission_deadline.isoformat() == '2026-10-28T09:00:00+00:00'

    def test_apply_deadline_cleared_with_null(self, admin_client):
        c = _make(apply_deadline=timezone.now())
        resp = admin_client.patch(detail_url(c.pk), {'apply_deadline': None}, format='json')
        assert resp.status_code == 200
        c.refresh_from_db()
        assert c.apply_deadline is None


@pytest.mark.django_db
class TestPatch:
    def test_unknown_id_404(self, admin_client):
        assert admin_client.patch(detail_url(99999), {'title': 'x'}, format='json').status_code == 404

    def test_update_fields_and_verified(self, admin_client):
        c = _make()
        resp = admin_client.patch(detail_url(c.pk), {
            'title': '바뀐 제목', 'summary': 's', 'team_size': None, 'poster_credit': '주최',
            'notice_date': '2026-11-01',
        }, format='json')
        assert resp.status_code == 200, resp.content
        c.refresh_from_db()
        assert c.title == '바뀐 제목' and c.summary == 's'
        assert c.notice_date.isoformat() == '2026-11-01'
        assert c.last_verified_at is not None
        assert resp.json()['title'] == '바뀐 제목'

    def test_audit_update_only(self, admin_client):
        c = _make()
        admin_client.patch(detail_url(c.pk), {'title': 'n', 'summary': 's', 'theme': ''}, format='json')
        assert _audit('contest_status_change').count() == 0
        log = _audit('contest_update').get()
        assert (log.target_type, log.target_id) == ('contest', str(c.pk))
        assert sorted(log.payload['fields']) == ['summary', 'title']

    def test_audit_status_change_only(self, admin_client):
        c = _make()
        resp = admin_client.patch(detail_url(c.pk), {'status': 'hidden'}, format='json')
        assert resp.status_code == 200
        log = _audit('contest_status_change').get()
        assert log.payload == {'from': 'published', 'to': 'hidden'}
        assert log.target_id == str(c.pk)
        assert _audit('contest_update').count() == 0

    def test_audit_status_and_other_fields_two_rows(self, admin_client):
        c = _make(status='pending')
        admin_client.patch(detail_url(c.pk), {'status': 'published', 'title': 'new'}, format='json')
        assert _audit('contest_status_change').get().payload == {'from': 'pending', 'to': 'published'}
        assert _audit('contest_update').get().payload == {'fields': ['title']}
        assert _audit().count() == 2

    def test_same_status_is_not_a_status_change(self, admin_client):
        c = _make()
        admin_client.patch(detail_url(c.pk), {'status': 'published', 'title': 'q'}, format='json')
        assert _audit('contest_status_change').count() == 0
        assert _audit('contest_update').count() == 1

    def test_noop_patch_logs_reverify(self, admin_client):
        c = _make()
        assert admin_client.patch(detail_url(c.pk), {}, format='json').status_code == 200
        assert _audit('contest_update').get().payload == {'fields': []}
        c.refresh_from_db()
        assert c.last_verified_at is not None

    @pytest.mark.parametrize('source', ['', 'https://linkareer.com/activity/1'])
    def test_publish_rule_400_not_500(self, admin_client, source):
        c = _make(status='pending', source_url=source)
        resp = admin_client.patch(detail_url(c.pk), {'status': 'published'}, format='json')
        assert resp.status_code == 400
        assert 'source_url' in resp.json()
        c.refresh_from_db()
        assert c.status == 'pending'
        assert c.last_verified_at is None
        assert _audit().count() == 0

    def test_publish_with_source_in_same_request(self, admin_client):
        c = _make(status='pending', source_url='')
        resp = admin_client.patch(detail_url(c.pk), {'status': 'published', 'source_url': OFFICIAL}, format='json')
        assert resp.status_code == 200
        assert _audit('contest_status_change').count() == 1

    def test_published_cannot_switch_to_listing_source(self, admin_client):
        c = _make()
        resp = admin_client.patch(detail_url(c.pk), {'source_url': 'https://wevity.com/x'}, format='json')
        assert resp.status_code == 400
        c.refresh_from_db()
        assert c.source_url == OFFICIAL

    def test_hide_always_allowed(self, admin_client):
        c = _make()
        assert admin_client.patch(detail_url(c.pk), {'status': 'hidden', 'source_url': ''}, format='json').status_code == 200

    @pytest.mark.parametrize('clear', [None, ''])
    def test_clear_poster(self, admin_client, clear):
        c = _make(poster_url='https://i.example.com/p.jpg', poster_credit='주최')
        resp = admin_client.patch(detail_url(c.pk), {'poster_url': clear}, format='json')
        assert resp.status_code == 200
        c.refresh_from_db()
        assert not c.poster_url
        assert c.poster_credit == '주최'
        assert resp.json()['poster_url'] in (None, '')
        assert _audit('contest_update').get().payload == {'fields': ['poster_url']}

    def test_set_poster_and_blocked_host(self, admin_client):
        c = _make()
        ok = admin_client.patch(detail_url(c.pk), {'poster_url': 'https://i.example.com/p.jpg'}, format='json')
        assert ok.status_code == 200
        bad = admin_client.patch(detail_url(c.pk), {'poster_url': 'https://img.wevity.com/p.jpg'}, format='json')
        assert bad.status_code == 400
        assert 'poster_url' in bad.json()
        c.refresh_from_db()
        assert c.poster_url == 'https://i.example.com/p.jpg'
        assert _audit().count() == 1

    def test_read_only_fields_ignored(self, admin_client):
        c = _make()
        admin_client.patch(detail_url(c.pk), {'interest_count': 50, 'import_key': 'zz', 'id': 12345}, format='json')
        c.refresh_from_db()
        assert c.interest_count == 0 and c.import_key is None

    @pytest.mark.parametrize('field,value', [
        ('status', 'bogus'), ('source_url', 'javascript:x'), ('title', ''), ('submission_deadline', 'nope'),
    ])
    def test_validation_400_no_audit(self, admin_client, field, value):
        c = _make()
        resp = admin_client.patch(detail_url(c.pk), {field: value}, format='json')
        assert resp.status_code == 400
        assert field in resp.json()
        assert _audit().count() == 0


@pytest.mark.django_db
class TestAuditIsAtomic:
    """An audit-write failure must roll the contest mutation back (no unaudited change)."""

    def _boom(self, monkeypatch):
        def raiser(*a, **k):
            raise RuntimeError('audit down')
        monkeypatch.setattr(AdminAuditLog.objects, 'create', raiser)

    def _call(self, fn):
        try:
            resp = fn()
        except RuntimeError:
            return  # test client re-raised the server error
        assert resp.status_code >= 500

    def test_post_rolls_back(self, admin_client, monkeypatch):
        self._boom(monkeypatch)
        self._call(lambda: admin_client.post(LIST_URL, _payload(), format='json'))
        assert Contest.objects.count() == 0

    def test_patch_rolls_back(self, admin_client, monkeypatch):
        c = _make(title='orig', status=Contest.STATUS_PUBLISHED)
        self._boom(monkeypatch)
        self._call(lambda: admin_client.patch(
            detail_url(c.pk), {'title': 'changed', 'status': 'hidden'}, format='json'))
        c.refresh_from_db()
        assert c.title == 'orig' and c.status == Contest.STATUS_PUBLISHED


@pytest.mark.django_db
class TestFieldKeyedErrors:
    def test_status_only_publish_without_source_is_source_url_keyed(self, admin_client):
        c = _make(status=Contest.STATUS_HIDDEN, source_url='')
        resp = admin_client.patch(detail_url(c.pk), {'status': 'published'}, format='json')
        assert resp.status_code == 400
        assert 'source_url' in resp.json()
        assert 'non_field_errors' not in resp.json()
        c.refresh_from_db()
        assert c.status == Contest.STATUS_HIDDEN
        assert _audit().count() == 0
