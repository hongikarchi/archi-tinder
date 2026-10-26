"""Board feed (/people/), per-board report image, liked-boards, reaction hardening."""
import uuid
from datetime import timedelta

import pytest
from django.utils import timezone

from apps.notifications.models import Notification

FEED = '/api/v1/people/'
LIKED = '/api/v1/liked-boards/'


def _person(name, vec=(0.0, 0.0, 0.0, 0.0, 0.0), type_code='CLON', opt_in=True, personality=True):
    from django.contrib.auth.models import User
    from apps.accounts.models import PersonalityProfile, UserProfile
    user = User.objects.create_user(username=name, email=f'{name}@example.com', password='x')
    profile = UserProfile.objects.create(user=user, display_name=name.capitalize())
    if personality:
        PersonalityProfile.objects.create(
            user=profile, axis_1=vec[0], axis_2=vec[1], axis_3=vec[2], axis_4=vec[3],
            axis_5=vec[4], type_code=type_code, discovery_opt_in=opt_in,
        )
    return user, profile


def _client(user):
    from rest_framework.test import APIClient
    from rest_framework_simplejwt.tokens import RefreshToken
    c = APIClient()
    c.credentials(HTTP_AUTHORIZATION=f'Bearer {RefreshToken.for_user(user).access_token}')
    return c


def _board(profile, name='B', age_min=0, visibility='public', image='abc', is_temp=False):
    from apps.recommendation.models import Project
    p = Project.objects.create(
        user=profile, name=name, visibility=visibility, report_image=image,
        report_image_mime='image/png', is_temp=is_temp,
    )
    Project.objects.filter(pk=p.pk).update(updated_at=timezone.now() - timedelta(minutes=age_min))
    return p


def _ids(resp):
    return [r['board_id'] for r in resp.data['results']]


@pytest.fixture
def me(db):
    return _person('me', vec=(0, 0, 0, 0, 0), type_code='CLON')


# ---------------------------------------------------------------------------
# Feed
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestFeed:
    def test_requires_auth(self):
        from rest_framework.test import APIClient
        assert APIClient().get(FEED).status_code in (401, 403)

    def test_assessment_required(self):
        user, _ = _person('nop', personality=False)
        r = _client(user).get(FEED)
        assert r.status_code == 403
        assert r.data == {'detail': 'assessment_required'}

    def test_pool_rules(self, me):
        mu, mp = me
        _, other = _person('other', vec=(1, 0, 0, 0, 0))
        _, hidden = _person('hidden', opt_in=False)
        _, blocked = _person('blocked')
        _, blocker = _person('blocker')
        from apps.messaging.models import Block
        Block.objects.create(blocker=mp, blocked=blocked)
        Block.objects.create(blocker=blocker, blocked=mp)
        ok_other = _board(other, 'ok', 1)
        ok_me = _board(mp, 'mine', 2)
        _board(other, 'private', 3, visibility='private')
        _board(other, 'temp', 4, is_temp=True)
        _board(other, 'noimg', 5, image='')
        _board(other, 'noimg-null', 5, image=None)
        _board(hidden, 'hidden')
        _board(blocked, 'blocked')
        _board(blocker, 'blocker')
        r = _client(mu).get(FEED)
        assert r.status_code == 200
        assert set(_ids(r)) == {str(ok_other.pk), str(ok_me.pk)}
        assert r.data['has_more'] is False and r.data['next_cursor'] is None

    def test_item_shape_and_flags(self, me):
        mu, mp = me
        ou, other = _person('other', vec=(3, 4, 0, 0, 0))
        b = _board(other, 'Their Board')
        mine = _board(mp, 'Mine', 5)
        from apps.social.models import Reaction
        Reaction.objects.create(user=mp, project=b)
        r = _client(mu).get(FEED)
        item = next(i for i in r.data['results'] if i['board_id'] == str(b.pk))
        assert set(item) == {
            'board_id', 'board_name', 'user_id', 'display_name', 'handle', 'avatar_url',
            'type_code', 'distance', 'is_me', 'is_reacted', 'reaction_count', 'updated_at',
        }
        assert item['board_name'] == 'Their Board'
        assert item['user_id'] == ou.id
        assert item['distance'] == 5.0
        assert item['is_me'] is False and item['is_reacted'] is True
        assert item['reaction_count'] == 1
        mine_item = next(i for i in r.data['results'] if i['board_id'] == str(mine.pk))
        assert mine_item['is_me'] is True and mine_item['is_reacted'] is False
        assert mine_item['distance'] == 0.0

    def test_default_is_time_desc(self, me):
        mu, mp = me
        _, o1 = _person('o1', vec=(5, 0, 0, 0, 0))
        _, o2 = _person('o2', vec=(1, 0, 0, 0, 0))
        old = _board(o2, 'old', 30)
        new = _board(o1, 'new', 1)
        mid = _board(mp, 'mid', 10)
        assert _ids(_client(mu).get(FEED)) == [str(new.pk), str(mid.pk), str(old.pk)]

    def test_inspired_and_opposite_with_tiebreak(self, me):
        mu, _ = me
        _, near = _person('near', vec=(1, 0, 0, 0, 0))
        _, far = _person('far', vec=(4, 0, 0, 0, 0))
        far_new = _board(far, 'far-new', 1)
        near_old = _board(near, 'near-old', 20)
        near_new = _board(near, 'near-new', 5)   # same owner -> same distance
        c = _client(mu)
        assert _ids(c.get(FEED, {'filter': 'inspired'})) == [
            str(near_new.pk), str(near_old.pk), str(far_new.pk)]
        assert _ids(c.get(FEED, {'filter': 'opposite'})) == [
            str(far_new.pk), str(near_new.pk), str(near_old.pk)]
        # distance is present for every filter
        assert all('distance' in i for i in c.get(FEED).data['results'])

    def test_type_code_filter(self, me):
        mu, _ = me
        _, a = _person('a', type_code='RSDT')
        _, b = _person('b', type_code='CLON')
        ba2 = _board(a, 'a2', 9)
        ba1 = _board(a, 'a1', 1)
        _board(b, 'b1')
        r = _client(mu).get(FEED, {'filter': 'rsdt'})
        assert _ids(r) == [str(ba1.pk), str(ba2.pk)]
        assert {i['type_code'] for i in r.data['results']} == {'RSDT'}

    def test_bad_params(self, me):
        c = _client(me[0])
        assert c.get(FEED, {'filter': 'nope'}).status_code == 400
        assert c.get(FEED, {'cursor': '!!!'}).status_code == 400
        assert c.get(FEED, {'page_size': 'x'}).status_code == 400
        assert c.get(FEED, {'page_size': '0'}).status_code == 400

    @pytest.mark.parametrize('flt', ['', 'inspired', 'opposite', 'CLON'])
    def test_cursor_pagination_no_dup_no_skip(self, me, flt):
        mu, mp = me
        owners = [_person(f'o{i}', vec=(i % 3, 0, 0, 0, 0))[1] for i in range(5)]
        expected = []
        for n in range(7):
            expected.append(_board(owners[n % 5], f'b{n}', n * 2 if n < 5 else 0))
        # two boards with identical updated_at AND owner-distance -> pid tie-break
        same = timezone.now() - timedelta(days=1)
        from apps.recommendation.models import Project
        Project.objects.filter(pk__in=[expected[5].pk, expected[6].pk]).update(updated_at=same)
        c = _client(mu)
        params = {'filter': flt} if flt else {}
        full = _ids(c.get(FEED, {**params, 'page_size': 30}))
        assert len(full) == 7
        seen, cursor, pages = [], None, 0
        while True:
            q = {**params, 'page_size': 3}
            if cursor:
                q['cursor'] = cursor
            r = c.get(FEED, q)
            assert r.status_code == 200, r.data
            seen += _ids(r)
            pages += 1
            if not r.data['has_more']:
                assert r.data['next_cursor'] is None
                break
            cursor = r.data['next_cursor']
            assert cursor
        assert seen == full and pages == 3

    def test_page_size_cap_and_default(self, me):
        mu, mp = me
        for i in range(32):
            _board(mp, f'b{i}', i)
        c = _client(mu)
        r = c.get(FEED, {'page_size': 999})
        assert len(r.data['results']) == 30 and r.data['has_more'] is True
        assert len(c.get(FEED).data['results']) == 20


# ---------------------------------------------------------------------------
# Per-board image
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestBoardImage:
    def url(self, pk):
        return f'/api/v1/people/boards/{pk}/report-image/'

    def test_public_ok(self, me):
        _, other = _person('other')
        b = _board(other, image='B64DATA')
        r = _client(me[0]).get(self.url(b.pk))
        assert r.status_code == 200
        assert r.data == {'image_data': 'B64DATA', 'mime_type': 'image/png'}

    def test_404_cases(self, me):
        _, other = _person('other')
        c = _client(me[0])
        assert c.get(self.url(_board(other, visibility='private').pk)).status_code == 404
        assert c.get(self.url(_board(other, image='').pk)).status_code == 404
        assert c.get(self.url(_board(other, is_temp=True).pk)).status_code == 404
        assert c.get(self.url(uuid.uuid4())).status_code == 404

    def test_opted_out_owner_404(self, me):
        _, hidden = _person('hidden', opt_in=False)
        b = _board(hidden)
        r = _client(me[0]).get(self.url(b.pk))
        assert r.status_code == 404
        assert r.data == {'detail': 'No public report image for this board.'}

    @pytest.mark.parametrize('direction', ['i_block', 'they_block'])
    def test_blocked_either_direction_404(self, me, direction):
        _, mp = me[0], me[1]
        _, o = _person('o')
        from apps.messaging.models import Block
        if direction == 'i_block':
            Block.objects.create(blocker=mp, blocked=o)
        else:
            Block.objects.create(blocker=o, blocked=mp)
        r = _client(me[0]).get(self.url(_board(o).pk))
        assert r.status_code == 404
        assert r.data == {'detail': 'No public report image for this board.'}

    def test_own_board_while_opted_out_200(self):
        user, prof = _person('solo', opt_in=False)
        b = _board(prof, image='MINE')
        r = _client(user).get(self.url(b.pk))
        assert r.status_code == 200
        assert r.data['image_data'] == 'MINE'

    def test_old_per_user_route_gone(self, me):
        assert _client(me[0]).get(f'/api/v1/people/{me[0].id}/report-image/').status_code == 404

    def test_requires_auth(self, me):
        from rest_framework.test import APIClient
        _, other = _person('other')
        b = _board(other)
        assert APIClient().get(self.url(b.pk)).status_code in (401, 403)


# ---------------------------------------------------------------------------
# Liked boards
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestLikedBoards:
    def _like(self, profile, project, age_min=0):
        from apps.social.models import Reaction
        r = Reaction.objects.create(user=profile, project=project)
        Reaction.objects.filter(pk=r.pk).update(created_at=timezone.now() - timedelta(minutes=age_min))
        return r

    def test_requires_auth(self):
        from rest_framework.test import APIClient
        assert APIClient().get(LIKED).status_code in (401, 403)

    def test_own_public_only_ordered_with_owner(self, me):
        mu, mp = me
        _, o = _person('o')
        _, o2 = _person('o2')
        b_old = _board(o, 'old')
        b_new = _board(o2, 'new')
        b_priv = _board(o, 'priv', visibility='private')
        b_temp = _board(o, 'temp', is_temp=True)
        other_like = _board(o, 'othersLike')
        self._like(mp, b_old, 30)
        self._like(mp, b_new, 1)
        self._like(mp, b_priv, 2)
        self._like(mp, b_temp, 3)
        self._like(o2, other_like, 0)  # someone else's reaction
        r = _client(mu).get(LIKED)
        assert r.status_code == 200
        assert [i['project_id'] for i in r.data['items']] == [str(b_new.pk), str(b_old.pk)]
        item = r.data['items'][0]
        assert set(item) >= {
            'project_id', 'name', 'date', 'visibility', 'building_count',
            'cover_image_url', 'thumbnails', 'has_report_image', 'report_image_url', 'owner',
        }
        assert item['owner']['user_id'] == o2.user_id
        assert item['owner']['display_name'] == o2.display_name
        assert set(item['owner']) == {'user_id', 'display_name', 'handle', 'avatar_url'}
        assert r.data['total_count'] == 2 and r.data['has_more'] is False

    def test_pagination(self, me):
        mu, mp = me
        _, o = _person('o')
        boards = [_board(o, f'b{i}') for i in range(5)]
        for i, b in enumerate(boards):
            self._like(mp, b, i)
        c = _client(mu)
        r1 = c.get(LIKED, {'page_size': 2})
        assert r1.data['has_more'] is True and r1.data['next_page'] == 2
        r3 = c.get(LIKED, {'page_size': 2, 'page': 3})
        assert len(r3.data['items']) == 1 and r3.data['has_more'] is False
        assert r3.data['next_page'] is None and r3.data['total_count'] == 5
        assert c.get(LIKED, {'page_size': 500}).data['page_size'] == 50

    def test_blocked_owner_excluded(self, me):
        mu, mp = me
        _, o = _person('o')
        _, o2 = _person('o2')
        from apps.messaging.models import Block
        Block.objects.create(blocker=mp, blocked=o)
        Block.objects.create(blocker=o2, blocked=mp)
        self._like(mp, _board(o))
        self._like(mp, _board(o2))
        assert _client(mu).get(LIKED).data['items'] == []

    def test_has_report_image_flag_without_loading_column(self, me):
        mu, mp = me
        _, o = _person('o')
        with_img = _board(o, 'with', image='BIGBASE64')
        empty = _board(o, 'empty', image='')
        none_img = _board(o, 'none', image=None)
        self._like(mp, with_img, 1)
        self._like(mp, empty, 2)
        self._like(mp, none_img, 3)
        r = _client(mu).get(LIKED)
        by_id = {i['project_id']: i for i in r.data['items']}
        a = by_id[str(with_img.pk)]
        assert a['has_report_image'] is True
        assert a['report_image_url'] == f'/api/v1/projects/{with_img.pk}/report-image/'
        for b in (empty, none_img):
            item = by_id[str(b.pk)]
            assert item['has_report_image'] is False
            assert item['report_image_url'] == ''

    def test_query_count_independent_of_page_rows(self, me):
        from django.db import connection
        from django.test.utils import CaptureQueriesContext
        mu, mp = me
        _, o = _person('o')
        c = _client(mu)
        self._like(mp, _board(o, 'first'))
        c.get(LIKED)  # warm auth/profile lookups
        with CaptureQueriesContext(connection) as one:
            c.get(LIKED)
        for i in range(5):
            self._like(mp, _board(o, f'more{i}', image='' if i % 2 else 'x'))
        with CaptureQueriesContext(connection) as many:
            c.get(LIKED)
        assert len(many) == len(one)


# ---------------------------------------------------------------------------
# Feed cache + throttles
# ---------------------------------------------------------------------------

@pytest.fixture
def loader_spy(monkeypatch):
    from apps.social import views_people
    calls = []
    real = views_people._load_sorted_entries

    def spy(*a, **kw):
        calls.append(a)
        return real(*a, **kw)

    monkeypatch.setattr(views_people, '_load_sorted_entries', spy)
    return calls


@pytest.mark.django_db
class TestFeedCache:
    def test_second_page_served_from_cached_list(self, me, loader_spy):
        mu, mp = me
        for i in range(5):
            _board(mp, f'b{i}', i)
        c = _client(mu)
        r1 = c.get(FEED, {'page_size': 2})
        r2 = c.get(FEED, {'page_size': 2, 'cursor': r1.data['next_cursor']})
        r3 = c.get(FEED, {'page_size': 2, 'cursor': r2.data['next_cursor']})
        assert len(loader_spy) == 1
        assert len(_ids(r1) + _ids(r2) + _ids(r3)) == 5
        assert r3.data['has_more'] is False

    def test_cache_isolated_by_filter_and_requester(self, me, loader_spy):
        mu, mp = me
        ou, other = _person('other', vec=(2, 0, 0, 0, 0), type_code='RSDT')
        _board(mp, 'mine', 1)
        _board(other, 'theirs', 2)
        c, oc = _client(mu), _client(ou)
        c.get(FEED)
        c.get(FEED, {'filter': 'inspired'})
        c.get(FEED, {'filter': 'rsdt'})
        assert len(loader_spy) == 3          # one per filter
        oc.get(FEED)
        assert len(loader_spy) == 4          # other requester: own entry
        c.get(FEED)
        c.get(FEED, {'filter': 'inspired'})
        oc.get(FEED)
        assert len(loader_spy) == 4          # all hits now
        # distance differs per requester (cached lists are not shared)
        mine_for_other = next(
            i for i in oc.get(FEED).data['results'] if i['board_name'] == 'mine')
        mine_for_me = next(
            i for i in c.get(FEED).data['results'] if i['board_name'] == 'mine')
        assert mine_for_me['distance'] == 0.0 and mine_for_other['distance'] == 2.0

    def test_revalidation_drops_board_made_private_after_caching(self, me):
        mu, _ = me
        _, o = _person('o')
        keep = _board(o, 'keep', 5)
        gone = _board(o, 'gone', 1)
        c = _client(mu)
        assert set(_ids(c.get(FEED))) == {str(keep.pk), str(gone.pk)}
        from apps.recommendation.models import Project
        Project.objects.filter(pk=gone.pk).update(visibility='private')
        assert _ids(c.get(FEED)) == [str(keep.pk)]

    def test_revalidation_drops_newly_blocked_owner_and_opted_out(self, me):
        mu, mp = me
        _, o = _person('o')
        _, o2 = _person('o2')
        _board(o, 'b1', 1)
        _board(o2, 'b2', 2)
        c = _client(mu)
        assert len(_ids(c.get(FEED))) == 2
        from apps.accounts.models import PersonalityProfile
        from apps.messaging.models import Block
        Block.objects.create(blocker=mp, blocked=o)
        PersonalityProfile.objects.filter(user=o2).update(discovery_opt_in=False)
        assert _ids(c.get(FEED)) == []

    def test_volatile_fields_are_fresh_within_ttl(self, me):
        mu, _ = me
        _, o = _person('o')
        b = _board(o, 'old name')
        c = _client(mu)
        c.get(FEED)
        from apps.recommendation.models import Project
        Project.objects.filter(pk=b.pk).update(name='new name', reaction_count=7)
        item = c.get(FEED).data['results'][0]
        assert item['board_name'] == 'new name' and item['reaction_count'] == 7
        from apps.social.models import Reaction
        Reaction.objects.create(user=me[1], project=b)
        assert c.get(FEED).data['results'][0]['is_reacted'] is True

    def test_cached_entries_hold_only_ordering_data(self, me):
        from django.core.cache import cache
        from apps.social import views_people
        mu, mp = me
        _, o = _person('o', vec=(1, 0, 0, 0, 0))
        b = _board(o, 'secret name', 1)
        _client(mu).get(FEED, {'filter': 'inspired'})
        key = views_people._cache_key(mp.pk, 'inspired', None)
        assert key.startswith('people_feed:v2:')
        entries = cache.get(key)
        assert entries and len(entries) == 1
        sort_key, pid, dist = entries[0]
        assert pid == str(b.pk) and dist == 1.0
        assert isinstance(sort_key, tuple) and len(sort_key) == 3
        blob = repr(entries)
        assert 'secret name' not in blob and 'display_name' not in blob

    def test_owner_display_fields_fresh_on_cached_page(self, me, loader_spy):
        from apps.accounts.models import UserProfile
        mu, _ = me
        _, o = _person('o')
        _board(o, 'b', 1)
        c = _client(mu)
        assert c.get(FEED).data['results'][0]['display_name'] == 'O'
        UserProfile.objects.filter(pk=o.pk).update(display_name='Renamed')
        item = c.get(FEED).data['results'][0]
        assert item['display_name'] == 'Renamed'
        assert len(loader_spy) == 1          # served from cache, still fresh


class TestThrottleConfig:
    def test_scopes_registered_and_wired(self):
        from django.conf import settings
        from rest_framework.throttling import UserRateThrottle
        from apps.social.views_people import (
            PeopleBoardImageThrottle, PeopleBoardReportImageView,
            PeopleDiscoveryView, PeopleFeedThrottle,
        )
        rates = settings.REST_FRAMEWORK['DEFAULT_THROTTLE_RATES']
        assert issubclass(PeopleFeedThrottle, UserRateThrottle)
        assert issubclass(PeopleBoardImageThrottle, UserRateThrottle)
        assert PeopleFeedThrottle.scope == 'people_feed' and 'people_feed' in rates
        assert PeopleBoardImageThrottle.scope == 'people_board_image'
        assert 'people_board_image' in rates
        assert PeopleFeedThrottle in PeopleDiscoveryView.throttle_classes
        assert PeopleBoardImageThrottle in PeopleBoardReportImageView.throttle_classes

    @pytest.mark.django_db
    def test_image_endpoint_is_throttled(self, me, monkeypatch):
        from rest_framework.throttling import SimpleRateThrottle
        from apps.social.views_people import PeopleBoardImageThrottle
        monkeypatch.setitem(SimpleRateThrottle.THROTTLE_RATES, 'people_board_image', '2/min')
        _, o = _person('o')
        b = _board(o)
        c = _client(me[0])
        url = f'/api/v1/people/boards/{b.pk}/report-image/'
        assert c.get(url).status_code == 200
        assert c.get(url).status_code == 200
        assert c.get(url).status_code == 429
        assert PeopleBoardImageThrottle.scope == 'people_board_image'


# ---------------------------------------------------------------------------
# Reaction hardening
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestReactionHardening:
    def url(self, pk):
        return f'/api/v1/projects/{pk}/react/'

    def test_own_board_403(self, me):
        mu, mp = me
        b = _board(mp)
        r = _client(mu).post(self.url(b.pk))
        assert r.status_code == 403
        assert r.data['detail'] == 'Cannot react to your own board.'
        b.refresh_from_db()
        assert b.reaction_count == 0

    @pytest.mark.parametrize('direction', ['i_block', 'they_block'])
    def test_blocked_either_direction_403(self, me, direction):
        mu, mp = me
        _, o = _person('o')
        from apps.messaging.models import Block
        if direction == 'i_block':
            Block.objects.create(blocker=mp, blocked=o)
        else:
            Block.objects.create(blocker=o, blocked=mp)
        b = _board(o)
        assert _client(mu).post(self.url(b.pk)).status_code == 403
        b.refresh_from_db()
        assert b.reaction_count == 0

    def test_private_still_403_and_idempotent_post(self, me):
        mu, _ = me
        _, o = _person('o')
        c = _client(mu)
        assert c.post(self.url(_board(o, visibility='private').pk)).status_code == 403
        pub = _board(o)
        assert c.post(self.url(pub.pk)).status_code == 201
        assert c.post(self.url(pub.pk)).status_code == 200

    @pytest.mark.parametrize('read', [False, True])
    def test_unlike_deletes_notification(self, me, read):
        mu, mp = me
        ou, o = _person('o')
        cu, c_prof = _person('c')
        b = _board(o, 'Board Name')
        assert _client(mu).post(self.url(b.pk)).status_code == 201
        assert _client(cu).post(self.url(b.pk)).status_code == 201
        notifs = Notification.objects.filter(recipient=o, type='reaction')
        assert notifs.count() == 2
        assert notifs.get(actor=mp).payload['project_title'] == 'Board Name'
        if read:
            notifs.update(read_at=timezone.now())
        other_board = _board(o, 'other')
        _client(mu).post(self.url(other_board.pk))
        assert _client(mu).delete(self.url(b.pk)).status_code == 204
        remaining = Notification.objects.filter(recipient=o, type='reaction')
        # my notification for b is gone; other actor's and my other-board one remain
        assert not remaining.filter(actor=mp, payload__project_id=str(b.pk)).exists()
        assert remaining.filter(actor=c_prof, payload__project_id=str(b.pk)).exists()
        assert remaining.filter(actor=mp, payload__project_id=str(other_board.pk)).exists()

    def test_delete_not_reacted_404(self, me):
        _, o = _person('o')
        assert _client(me[0]).delete(self.url(_board(o).pk)).status_code == 404
