"""
test_publish_rule.py -- model-level publish rule (FULL-CONTEST-2).

A 'published' contest needs a non-empty official http(s) source_url that is not a
listing/aggregator site. Enforced in Contest.save() and the bulk paths, with a DB
CHECK backstop for the blank case.
"""
from datetime import timedelta

import pytest
from django.core.exceptions import ValidationError
from django.db import IntegrityError, connection, transaction
from django.db.models import F, Value
from django.utils import timezone

from apps.contests.models import Contest
from apps.contests.validators import LISTING_SITE_HOSTS, host_in, validate_poster_url

OFFICIAL = 'https://www.junglimaward.com/2027'
LISTING_URLS = [
    'https://wevity.com/?c=find&gbn=view&ix=1',
    'https://www.wevity.com/?c=find',
    'https://linkareer.com/activity/330489',
    'https://lectus.kr/14th-hanok-design-int-competition/',
    'https://www.thinkcontest.com/Contest/ContestDetail.html?id=1',
    'https://www.contestkorea.com/sub/view.php?str_no=1',
    'https://all-con.co.kr/page/1',
    'https://www.thinkyou.co.kr/contest/1',
    'https://theteams.kr/c/1',
    'HTTPS://M.WEVITY.COM./x',
]


def _kw(**o):
    base = dict(
        title='C', organizer='Org', source_url=OFFICIAL,
        submission_deadline=timezone.now() + timedelta(days=5),
        status=Contest.STATUS_PUBLISHED,
    )
    base.update(o)
    return base


def _make(**o):
    return Contest.objects.create(**_kw(**o))


class TestHostIn:
    @pytest.mark.parametrize('url', [
        'https://wevity.com/x', 'https://WWW.Wevity.com/x', 'https://a.b.wevity.com/x',
        'https://wevity.com./x',
    ])
    def test_matches(self, url):
        assert host_in(url, ('wevity.com',))

    @pytest.mark.parametrize('url', [
        'https://notwevity.com/x', 'https://wevity.com.evil.org/x', 'https://example.com/wevity.com',
        '', 'not a url',
    ])
    def test_no_match(self, url):
        assert not host_in(url, ('wevity.com',))

    def test_listing_hosts_cover_all_sites(self):
        assert len(LISTING_SITE_HOSTS) == 8
        assert 'wevity.com' in LISTING_SITE_HOSTS


@pytest.mark.parametrize('url', LISTING_URLS)
def test_poster_blocked_on_every_listing_site(url):
    with pytest.raises(ValidationError):
        validate_poster_url(url)


@pytest.mark.django_db
class TestSave:
    def test_official_published_ok(self):
        assert _make().status == 'published'

    def test_blank_source_published_rejected(self):
        with pytest.raises(ValidationError) as exc:
            _make(source_url='')
        assert 'source_url' in exc.value.message_dict
        assert not Contest.objects.exists()

    @pytest.mark.parametrize('url', LISTING_URLS)
    def test_listing_site_published_rejected(self, url):
        with pytest.raises(ValidationError) as exc:
            _make(source_url=url)
        assert 'source_url' in exc.value.message_dict
        assert not Contest.objects.exists()

    @pytest.mark.parametrize('status', ['pending', 'hidden'])
    @pytest.mark.parametrize('url', ['', 'https://www.wevity.com/x', OFFICIAL])
    def test_pending_and_hidden_unaffected(self, status, url):
        assert _make(status=status, source_url=url).status == status

    def test_resave_publish_transition_checked(self):
        c = _make(status='pending', source_url='')
        c.status = 'published'
        with pytest.raises(ValidationError):
            c.save()
        c.source_url = OFFICIAL
        c.save()
        c.refresh_from_db()
        assert c.status == 'published'

    def test_published_row_cannot_switch_to_listing_source(self):
        c = _make()
        c.source_url = 'https://linkareer.com/activity/1'
        with pytest.raises(ValidationError):
            c.save()

    def test_update_or_create_enforced(self):
        with pytest.raises(ValidationError):
            Contest.objects.update_or_create(title='X', defaults=_kw(source_url=''))


@pytest.mark.django_db
class TestBulkCreate:
    def test_ok(self):
        Contest.objects.bulk_create([Contest(**_kw()), Contest(**_kw(title='D', source_url='', status='hidden'))])
        assert Contest.objects.count() == 2

    @pytest.mark.parametrize('url', ['', 'https://lectus.kr/x', 'https://sub.wevity.com/x'])
    def test_rejected_all_or_nothing(self, url):
        with pytest.raises(ValidationError):
            Contest.objects.bulk_create([Contest(**_kw(title='ok')), Contest(**_kw(source_url=url))])
        assert not Contest.objects.exists()


@pytest.mark.django_db
class TestBulkUpdate:
    def test_ok(self):
        c = _make(status='pending', source_url='')
        c.source_url = OFFICIAL
        c.status = 'published'
        Contest.objects.bulk_update([c], ['source_url', 'status'])
        c.refresh_from_db()
        assert c.status == 'published'

    @pytest.mark.parametrize('url', ['', 'https://linkareer.com/x'])
    def test_publish_with_bad_source_rejected(self, url):
        c = _make(status='pending', source_url=url)
        c.status = 'published'
        with pytest.raises(ValidationError):
            Contest.objects.bulk_update([c], ['status'])
        c.refresh_from_db()
        assert c.status == 'pending'

    def test_source_change_on_published_row_rejected(self):
        c = _make()
        c.source_url = 'https://contestkorea.com/x'
        with pytest.raises(ValidationError):
            Contest.objects.bulk_update([c], ['source_url'])
        c.refresh_from_db()
        assert c.source_url == OFFICIAL

    def test_unrelated_fields_not_checked(self):
        c = _make(status='pending', source_url='')
        c.title = 'new'
        Contest.objects.bulk_update([c], ['title'])


@pytest.mark.django_db
class TestQuerySetUpdate:
    def test_publish_row_with_current_official_source_ok(self):
        c = _make(status='pending')
        assert Contest.objects.filter(pk=c.pk).update(status='published') == 1

    @pytest.mark.parametrize('url', ['', 'https://wevity.com/x'])
    def test_publish_row_with_bad_current_source_rejected(self, url):
        ok = _make(title='ok', status='pending')
        bad = _make(title='bad', status='pending', source_url=url)
        with pytest.raises(ValidationError):
            Contest.objects.filter(pk__in=[ok.pk, bad.pk]).update(status='published')
        assert not Contest.objects.filter(status='published').exists()

    def test_publish_with_new_valid_source_ok(self):
        c = _make(status='pending', source_url='')
        assert Contest.objects.filter(pk=c.pk).update(status='published', source_url=OFFICIAL) == 1

    @pytest.mark.parametrize('url', ['', 'https://theteams.kr/x'])
    def test_publish_with_new_bad_source_rejected(self, url):
        c = _make(status='pending')
        with pytest.raises(ValidationError):
            Contest.objects.filter(pk=c.pk).update(status='published', source_url=url)

    @pytest.mark.parametrize('url', ['', 'https://all-con.co.kr/x'])
    def test_source_only_change_on_published_rejected(self, url):
        c = _make()
        with pytest.raises(ValidationError):
            Contest.objects.filter(pk=c.pk).update(source_url=url)
        c.refresh_from_db()
        assert c.source_url == OFFICIAL

    def test_source_only_change_on_unpublished_rows_ok(self):
        c = _make(status='pending')
        assert Contest.objects.filter(pk=c.pk).update(source_url='') == 1
        assert Contest.objects.filter(pk=c.pk).update(source_url='https://wevity.com/x') == 1

    def test_source_only_change_valid_on_published_ok(self):
        c = _make()
        assert Contest.objects.filter(pk=c.pk).update(source_url='https://example.org/') == 1

    def test_unpublish_with_blank_source_ok(self):
        c = _make()
        assert Contest.objects.filter(pk=c.pk).update(status='hidden', source_url='') == 1

    @pytest.mark.parametrize('kwargs', [
        {'status': F('title')}, {'source_url': F('listing_url')}, {'source_url': Value('')},
    ])
    def test_expressions_rejected(self, kwargs):
        c = _make()
        with pytest.raises(ValidationError) as exc:
            Contest.objects.filter(pk=c.pk).update(**kwargs)
        assert 'not supported' in str(exc.value)

    def test_other_fields_unaffected(self):
        c = _make()
        assert Contest.objects.filter(pk=c.pk).update(interest_count=F('interest_count') + 1) == 1


@pytest.mark.django_db
class TestDbCheck:
    def test_raw_published_blank_rejected(self):
        c = _make(status='pending', source_url='')
        with pytest.raises(IntegrityError):
            with transaction.atomic():
                with connection.cursor() as cur:
                    cur.execute(
                        "UPDATE contests_contest SET status = 'published' WHERE id = %s", [c.pk],
                    )

    def test_raw_published_with_source_ok(self):
        c = _make(status='pending')
        with connection.cursor() as cur:
            cur.execute("UPDATE contests_contest SET status = 'published' WHERE id = %s", [c.pk])
