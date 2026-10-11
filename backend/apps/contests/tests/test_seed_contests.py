"""
test_seed_contests.py -- seed_contests management command (BACK-CONTEST-1).
"""
import io

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import override_settings

from apps.contests.models import Contest


def _run(*args):
    out = io.StringIO()
    call_command('seed_contests', *args, stdout=out)
    return out.getvalue()


@pytest.mark.django_db
class TestSeedContests:
    @override_settings(DEBUG=False)
    def test_refuses_when_debug_false(self):
        with pytest.raises(CommandError):
            _run()
        assert Contest.objects.count() == 0

    @override_settings(DEBUG=False)
    def test_clean_also_refuses_when_debug_false(self):
        with pytest.raises(CommandError):
            _run('--clean')

    @override_settings(DEBUG=True)
    def test_creates_seven_with_statuses(self):
        _run()
        assert Contest.objects.count() == 7
        assert Contest.objects.filter(status='published').count() == 6
        pending = Contest.objects.get(status='pending')
        assert pending.title.startswith('에어-비트 시티')
        assert pending.submission_deadline.isoformat() == '2026-11-19T14:59:00+00:00'
        assert not Contest.objects.filter(status='hidden').exists()

    @override_settings(DEBUG=True)
    def test_jeonglim_published_with_apply_deadline(self):
        _run()
        c = Contest.objects.get(title='정림학생건축상 2027')
        assert c.status == 'published'
        # KST 23:59 == 14:59 UTC.
        assert c.submission_deadline.isoformat() == '2027-01-11T14:59:00+00:00'
        assert c.apply_deadline.isoformat() == '2027-01-04T14:59:00+00:00'

    @override_settings(DEBUG=True)
    def test_posters_without_url(self):
        _run()
        for c in Contest.objects.all():
            assert c.poster_url is None
            assert c.listing_source == 'seed'

    @override_settings(DEBUG=True)
    def test_idempotent(self):
        _run()
        _run()
        assert Contest.objects.count() == 7

    @override_settings(DEBUG=True)
    def test_clean_only_removes_seed_rows(self):
        _run()
        keep = Contest.objects.create(
            title='real', organizer='x', source_url='https://example.com/',
            submission_deadline='2030-01-01T00:00:00Z', listing_source='wevity',
        )
        _run('--clean')
        assert list(Contest.objects.values_list('id', flat=True)) == [keep.id]

    @override_settings(DEBUG=True)
    def test_hanok_has_blank_source_and_listing(self):
        _run()
        c = Contest.objects.get(title='제14회 한옥디자인 국제공모')
        assert c.source_url == ''
        assert c.listing_url == 'https://lectus.kr/14th-hanok-design-int-competition/'

    @override_settings(DEBUG=True)
    def test_air_beat_stays_pending(self):
        _run()
        c = Contest.objects.get(title__startswith='에어-비트 시티')
        assert c.status == 'pending'
        assert c.source_url == 'https://airbeatcity.com/contest'
        assert c.import_key is None
        assert Contest.objects.count() == 7
        assert Contest.objects.filter(status='published').count() == 6
