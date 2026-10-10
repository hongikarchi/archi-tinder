"""
test_contest_urls.py -- http/https-only URL validation (BACK-CONTEST-2).
"""
from datetime import timedelta

import pytest
from django.core.exceptions import ValidationError
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
    def test_never_emits_non_http_even_if_forced_in(self, auth_client_a):
        c = Contest.objects.create(**_kwargs(
            poster_url='https://i.example.com/p.jpg', poster_status=Contest.POSTER_ALLOWED,
            listing_url='https://example.com/list',
        ))
        Contest.objects.filter(pk=c.pk).update(
            source_url='javascript:alert(1)',
            listing_url='data:text/html,x',
            poster_url='ftp://example.com/p.jpg',
        )
        detail = auth_client_a.get(f'/api/v1/contests/{c.id}/').data
        assert detail['source_url'] == ''
        assert detail['listing_url'] == ''
        assert detail['poster_url'] is None
        row = auth_client_a.get('/api/v1/contests/').data['results'][0]
        assert (row['source_url'], row['listing_url'], row['poster_url']) == ('', '', None)

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
