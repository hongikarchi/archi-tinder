"""
test_contest_urls.py -- http/https-only URL validation (BACK-CONTEST-2).
"""
from datetime import timedelta

import pytest
from django.core.exceptions import ValidationError
from django.db import IntegrityError, connection, transaction
from django.utils import timezone

from apps.contests.models import Contest
from apps.contests.serializers import ContestSerializer

BAD_URLS = [
    'javascript:alert(1)',
    'data:text/html,<script>alert(1)</script>',
    'ftp://example.com/x',
    '//host/x',
    'not a url',
    'https://',
]
FIELDS = ['source_url', 'listing_url', 'poster_url']


def _kwargs(**overrides):
    base = dict(
        title='C', organizer='Org', source_url='https://example.com/',
        submission_deadline=timezone.now() + timedelta(days=5),
        status=Contest.STATUS_PUBLISHED,
    )
    base.update(overrides)
    return base


@pytest.mark.django_db
class TestSaveValidation:
    @pytest.mark.parametrize('field', FIELDS)
    @pytest.mark.parametrize('bad', BAD_URLS)
    def test_rejected_on_create(self, field, bad):
        with pytest.raises(ValidationError):
            Contest.objects.create(**_kwargs(**{field: bad}))
        assert Contest.objects.count() == 0

    @pytest.mark.parametrize('field', FIELDS)
    def test_rejected_on_update_or_create(self, field):
        with pytest.raises(ValidationError):
            Contest.objects.update_or_create(
                title='X', defaults=_kwargs(**{field: 'javascript:alert(1)'}),
            )

    @pytest.mark.parametrize('field', FIELDS)
    @pytest.mark.parametrize('good', ['http://example.com/a', 'https://example.com/a?b=1'])
    def test_http_and_https_accepted(self, field, good):
        c = Contest.objects.create(**_kwargs(**{field: good}))
        assert getattr(c, field) == good

    def test_blank_listing_and_null_poster_allowed(self):
        c = Contest.objects.create(**_kwargs(listing_url='', poster_url=None))
        assert c.listing_url == '' and c.poster_url is None

    def test_blank_source_url_rejected(self):
        with pytest.raises(ValidationError):
            Contest.objects.create(**_kwargs(source_url=''))

    def test_resave_with_bad_value_rejected(self):
        c = Contest.objects.create(**_kwargs())
        c.poster_url = 'data:image/png;base64,AAAA'
        with pytest.raises(ValidationError):
            c.save()


@pytest.mark.django_db
class TestSerializerDefense:
    def test_never_emits_non_http_even_if_forced_in(self):
        # Both the ORM guard and the DB constraint block bad rows, so bypass
        # them deliberately: serialize an unsaved in-memory instance.
        c = Contest(**_kwargs(
            poster_url='ftp://example.com/p.jpg', poster_status=Contest.POSTER_ALLOWED,
            listing_url='data:text/html,x',
        ))
        c.source_url = 'javascript:alert(1)'
        c.interested = False
        data = ContestSerializer(c, context={'now': timezone.now()}).data
        assert data['source_url'] == ''
        assert data['listing_url'] == ''
        assert data['poster_url'] is None

    def test_good_values_pass_through(self):
        c = Contest.objects.create(**_kwargs(
            listing_url='http://example.com/l',
            poster_url='https://i.example.com/p.jpg', poster_status=Contest.POSTER_ALLOWED,
        ))
        data = ContestSerializer(c).data
        assert data['source_url'] == 'https://example.com/'
        assert data['listing_url'] == 'http://example.com/l'
        assert data['poster_url'] == 'https://i.example.com/p.jpg'

    def test_unverified_poster_not_emitted(self):
        c = Contest.objects.create(**_kwargs(
            poster_url='https://i.example.com/p.jpg', poster_status=Contest.POSTER_UNVERIFIED,
        ))
        assert ContestSerializer(c).data['poster_url'] is None


def _valid(**o):
    return Contest(**_kwargs(**o))


@pytest.mark.django_db
class TestBulkGuards:
    @pytest.mark.parametrize('field', FIELDS)
    @pytest.mark.parametrize('bad', BAD_URLS)
    def test_bulk_create_rejected(self, field, bad):
        with pytest.raises(ValidationError):
            Contest.objects.bulk_create([_valid(**{field: bad})])
        assert not Contest.objects.exists()

    @pytest.mark.parametrize('field', FIELDS)
    @pytest.mark.parametrize('bad', BAD_URLS)
    def test_bulk_update_rejected(self, field, bad):
        c = Contest.objects.create(**_kwargs())
        setattr(c, field, bad)
        with pytest.raises(ValidationError):
            Contest.objects.bulk_update([c], [field])

    @pytest.mark.parametrize('field', FIELDS)
    @pytest.mark.parametrize('bad', BAD_URLS)
    def test_queryset_update_rejected(self, field, bad):
        c = Contest.objects.create(**_kwargs())
        with pytest.raises(ValidationError):
            Contest.objects.filter(pk=c.pk).update(**{field: bad})

    def test_valid_values_pass(self):
        Contest.objects.bulk_create([_valid(
            listing_url='http://example.com/l', poster_url='https://i.example.com/p.jpg',
        )])
        c = Contest.objects.get()
        c.source_url = 'HTTPS://example.org/'
        c.poster_url = None
        c.listing_url = ''
        Contest.objects.bulk_update([c], ['source_url', 'poster_url', 'listing_url'])
        assert Contest.objects.filter(pk=c.pk).update(poster_url='http://x.example/p.png') == 1

    def test_bulk_update_untouched_url_field_not_validated(self):
        c = Contest.objects.create(**_kwargs())
        c.title = 'new'
        Contest.objects.bulk_update([c], ['title'])

    def test_update_non_url_fields_unaffected(self):
        c = Contest.objects.create(**_kwargs())
        assert Contest.objects.filter(pk=c.pk).update(
            poster_status=Contest.POSTER_NONE, updated_at=timezone.now(),
        ) == 1

    def test_update_with_expression_skipped(self):
        from django.db.models import F
        c = Contest.objects.create(**_kwargs())
        assert Contest.objects.filter(pk=c.pk).update(listing_url=F('source_url')) == 1


@pytest.mark.django_db
class TestDbConstraints:
    @pytest.mark.parametrize('field', FIELDS)
    @pytest.mark.parametrize('bad', ['javascript:alert(1)', 'ftp://example.com/x', '//host/x'])
    def test_raw_update_rejected_by_db(self, field, bad):
        c = Contest.objects.create(**_kwargs())
        with pytest.raises(IntegrityError):
            with transaction.atomic():
                with connection.cursor() as cur:
                    cur.execute(
                        f'UPDATE contests_contest SET {field} = %s WHERE id = %s', [bad, c.pk],
                    )

    def test_raw_update_valid_and_blank_ok(self):
        c = Contest.objects.create(**_kwargs())
        with connection.cursor() as cur:
            cur.execute(
                'UPDATE contests_contest SET listing_url = %s, poster_url = NULL WHERE id = %s',
                ['', c.pk],
            )
            cur.execute(
                'UPDATE contests_contest SET source_url = %s WHERE id = %s',
                ['HTTP://example.com/', c.pk],
            )


@pytest.mark.django_db
class TestBlankAndNullAccepted:
    def test_poster_url_none_saved(self):
        assert Contest.objects.create(**_kwargs(poster_url=None)).poster_url is None

    def test_poster_url_empty_via_save(self):
        c = Contest.objects.create(**_kwargs(poster_url=''))
        c.refresh_from_db()
        assert c.poster_url == ''

    def test_poster_url_empty_via_update(self):
        c = Contest.objects.create(**_kwargs(poster_url='https://i.example.com/p.jpg'))
        assert Contest.objects.filter(pk=c.pk).update(poster_url='') == 1
        c.refresh_from_db()
        assert c.poster_url == ''
        assert Contest.objects.filter(pk=c.pk).update(poster_url=None) == 1

    def test_poster_url_empty_via_bulk_create_and_update(self):
        Contest.objects.bulk_create([_valid(poster_url=''), _valid(poster_url=None)])
        assert Contest.objects.filter(poster_url='').count() == 1
        c = Contest.objects.filter(poster_url='').get()
        c.poster_url = None
        Contest.objects.bulk_update([c], ['poster_url'])

    def test_listing_url_empty(self):
        c = Contest.objects.create(**_kwargs(listing_url=''))
        c.refresh_from_db()
        assert c.listing_url == ''

    def test_db_accepts_empty_poster_via_raw_sql(self):
        c = Contest.objects.create(**_kwargs())
        with connection.cursor() as cur:
            cur.execute("UPDATE contests_contest SET poster_url = '' WHERE id = %s", [c.pk])

    def test_source_url_empty_still_rejected_by_db(self):
        c = Contest.objects.create(**_kwargs())
        with pytest.raises(IntegrityError):
            with transaction.atomic():
                with connection.cursor() as cur:
                    cur.execute("UPDATE contests_contest SET source_url = '' WHERE id = %s", [c.pk])
