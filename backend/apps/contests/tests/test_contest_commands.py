"""
test_contest_commands.py -- contest_status / contest_poster (BACK-CONTEST-2).
Commands are production-usable: settings.DEBUG is forced False in every test.
"""
from datetime import timedelta
from io import StringIO

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError
from django.utils import timezone

from apps.contests.models import Contest


@pytest.fixture(autouse=True)
def _debug_off(settings):
    settings.DEBUG = False


def _make(**kwargs):
    defaults = dict(
        title='C', organizer='Org', source_url='https://example.com/',
        submission_deadline=timezone.now() + timedelta(days=5),
        status=Contest.STATUS_HIDDEN,
    )
    defaults.update(kwargs)
    return Contest.objects.create(**defaults)


def _run(*args):
    out = StringIO()
    call_command(*args, stdout=out)
    return out.getvalue()


@pytest.mark.django_db
class TestContestStatus:
    def test_transitions_and_prints_before_after(self):
        c = _make()
        for new in ('published', 'pending', 'hidden'):
            before = Contest.objects.get(pk=c.pk).status
            out = _run('contest_status', str(c.pk), new)
            assert f'{before} -> {new}' in out
            assert Contest.objects.get(pk=c.pk).status == new

    def test_unknown_id_errors(self):
        with pytest.raises(CommandError):
            call_command('contest_status', '999999', 'published')

    def test_invalid_status_errors(self):
        c = _make()
        with pytest.raises(CommandError):
            call_command('contest_status', str(c.pk), 'bogus')

    def test_exit_code_nonzero_via_cli(self):
        # CommandError -> manage.py exits 1
        from django.core.management import execute_from_command_line
        with pytest.raises(SystemExit) as exc:
            execute_from_command_line(['manage.py', 'contest_status', '999999', 'published'])
        assert exc.value.code != 0


@pytest.mark.django_db
class TestContestPoster:
    def test_allow_sets_fields(self):
        c = _make()
        out = _run('contest_poster', str(c.pk), 'allow',
                   '--url', 'https://img.example.com/p.jpg',
                   '--credit', '주최처', '--basis', '공공누리 제1유형')
        assert 'unverified -> allowed' in out
        c.refresh_from_db()
        assert c.poster_status == Contest.POSTER_ALLOWED
        assert c.poster_url == 'https://img.example.com/p.jpg'
        assert c.poster_credit == '주최처'
        assert c.poster_permission_basis == '공공누리 제1유형'
        assert c.poster_permission_at is not None

    def test_allow_requires_basis(self):
        c = _make()
        with pytest.raises(CommandError):
            call_command('contest_poster', str(c.pk), 'allow', '--url', 'https://i.example.com/p.jpg')
        with pytest.raises(CommandError):
            call_command('contest_poster', str(c.pk), 'allow',
                         '--url', 'https://i.example.com/p.jpg', '--basis', '   ')
        c.refresh_from_db()
        assert c.poster_status == Contest.POSTER_UNVERIFIED

    @pytest.mark.parametrize('bad', ['javascript:alert(1)', 'ftp://x.com/p.jpg', '//h/p', ''])
    def test_allow_requires_http_url(self, bad):
        c = _make()
        with pytest.raises(CommandError):
            call_command('contest_poster', str(c.pk), 'allow', '--url', bad, '--basis', 'mail')
        c.refresh_from_db()
        assert c.poster_url is None and c.poster_status == Contest.POSTER_UNVERIFIED

    def test_restore_after_none(self):
        c = _make()
        call_command('contest_poster', str(c.pk), 'allow',
                     '--url', 'https://i.example.com/p.jpg', '--basis', 'mail 2026-10-01')
        call_command('contest_poster', str(c.pk), 'none')
        c.refresh_from_db()
        assert c.poster_status == Contest.POSTER_NONE
        out = _run('contest_poster', str(c.pk), 'restore')
        assert 'none -> allowed' in out
        c.refresh_from_db()
        assert c.poster_status == Contest.POSTER_ALLOWED

    def test_restore_refused_without_url_or_basis(self):
        no_url = _make(poster_status=Contest.POSTER_NONE, poster_permission_basis='mail')
        with pytest.raises(CommandError):
            call_command('contest_poster', str(no_url.pk), 'restore')
        no_basis = _make(poster_status=Contest.POSTER_NONE, poster_url='https://i.example.com/p.jpg')
        with pytest.raises(CommandError):
            call_command('contest_poster', str(no_basis.pk), 'restore')
        no_url.refresh_from_db()
        no_basis.refresh_from_db()
        assert no_url.poster_status == Contest.POSTER_NONE
        assert no_basis.poster_status == Contest.POSTER_NONE

    def test_none(self):
        c = _make(poster_status=Contest.POSTER_ALLOWED, poster_url='https://i.example.com/p.jpg')
        out = _run('contest_poster', str(c.pk), 'none')
        assert 'allowed -> none' in out
        c.refresh_from_db()
        assert c.poster_status == Contest.POSTER_NONE

    @pytest.mark.parametrize('action', ['none', 'restore'])
    def test_unknown_id_errors(self, action):
        with pytest.raises(CommandError):
            call_command('contest_poster', '999999', action)
