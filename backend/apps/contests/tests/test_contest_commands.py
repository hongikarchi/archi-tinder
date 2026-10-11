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
    def test_set_url_and_credit(self):
        c = _make()
        out = _run('contest_poster', str(c.pk), 'set',
                   '--url', 'https://img.example.com/p.jpg', '--credit', '주최처')
        assert 'None -> https://img.example.com/p.jpg' in out
        c.refresh_from_db()
        assert c.poster_url == 'https://img.example.com/p.jpg'
        assert c.poster_credit == '주최처'

    def test_set_credit_optional_keeps_existing(self):
        c = _make(poster_credit='old')
        call_command('contest_poster', str(c.pk), 'set', '--url', 'http://i.example.com/p.jpg')
        c.refresh_from_db()
        assert c.poster_url == 'http://i.example.com/p.jpg'
        assert c.poster_credit == 'old'

    @pytest.mark.parametrize('bad', ['javascript:alert(1)', 'ftp://x.com/p.jpg', '//h/p', ''])
    def test_set_rejects_invalid_url(self, bad):
        c = _make()
        with pytest.raises(CommandError):
            call_command('contest_poster', str(c.pk), 'set', '--url', bad)
        c.refresh_from_db()
        assert c.poster_url is None

    def test_set_requires_url(self):
        c = _make()
        with pytest.raises(CommandError):
            call_command('contest_poster', str(c.pk), 'set')

    def test_clear_keeps_credit(self):
        c = _make(poster_url='https://i.example.com/p.jpg', poster_credit='주최처')
        out = _run('contest_poster', str(c.pk), 'clear')
        assert 'https://i.example.com/p.jpg -> None' in out
        c.refresh_from_db()
        assert c.poster_url is None
        assert c.poster_credit == '주최처'

    @pytest.mark.parametrize('action', ['set', 'clear'])
    def test_unknown_id_errors(self, action):
        with pytest.raises(CommandError):
            call_command('contest_poster', '999999', action, '--url', 'https://x.example.com/p.jpg')
