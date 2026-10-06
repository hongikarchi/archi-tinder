"""External-services panel (ADMIN-DASH-2a): GET services/ + PATCH services/<slug>/note/.

No real network: ``requests.get`` / ``requests.post`` inside providers.py are routed to a
fake. Fake credentials are set via settings and asserted absent from bodies and logs.
"""
import json
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest
import requests

from apps.admin_dashboard import providers
from apps.admin_dashboard.models import AdminAuditLog, ProviderNote
from apps.admin_dashboard.testing import make_operator_client

LIST_URL = '/api/v1/admin/dashboard/services/'
NOTE_URL = '/api/v1/admin/dashboard/services/{}/note/'
SLUGS = ['railway', 'vercel', 'neon', 'cloudflare', 'openai', 'gemini', 'huggingface', 'github']

FAKE_OPENAI = 'sk-admin-FAKEOPENAIKEY1234'
FAKE_CF_TOKEN = 'cf-FAKETOKEN-abcdef987654'
FAKE_CF_ACCOUNT = 'acct-FAKEID-0123456789'
FAKE_HF = 'hf_FAKEHFTOKEN123456'
FAKES = [FAKE_OPENAI, FAKE_CF_TOKEN, FAKE_CF_ACCOUNT, FAKE_HF]

DENIED_VARIANTS = {
    'guest': {'guest': True},
    'staff_not_in_list': {'in_list': False},
    'in_list_not_staff': {'is_staff': False},
    'no_google_social_account': {'google': False},
}


def _resp(json_data, status=200, bad_json=False):
    r = MagicMock()
    r.status_code = status
    if bad_json:
        r.json.side_effect = ValueError('bad json')
    else:
        r.json.return_value = json_data
    if status >= 400:
        err = requests.HTTPError(f'{status}')
        err.response = r
        r.raise_for_status.side_effect = err
    else:
        r.raise_for_status.return_value = None
    return r


OK_STATUS = {'status': {'indicator': 'none', 'description': 'All Systems Operational'}}
RAILWAY_OK = {'components': [{'name': 'API', 'status': 'OPERATIONAL'}]}


class FakeNet:
    """Routes requests.get/post by URL substring; records every call."""

    def __init__(self):
        self.routes = {}   # substring -> response | exception | callable(url, kwargs)
        self.calls = []    # (method, url, kwargs)

    def set(self, substring, value):
        self.routes[substring] = value

    def _dispatch(self, method, url, kwargs):
        self.calls.append((method, url, kwargs))
        for sub, value in self.routes.items():
            if sub in url:
                if isinstance(value, Exception):
                    raise value
                if callable(value) and not isinstance(value, MagicMock):
                    return value(url, kwargs)
                return value
        if 'api.railwaystatus.com' in url:
            return _resp(RAILWAY_OK)
        if 'status.cloud.google.com' in url:
            return _resp([])
        if '/api/v2/status.json' in url:
            return _resp(OK_STATUS)
        raise requests.ConnectionError('unrouted ' + url)

    def get(self, url, **kwargs):
        return self._dispatch('GET', url, kwargs)

    def post(self, url, **kwargs):
        return self._dispatch('POST', url, kwargs)

    def urls(self):
        return [c[1] for c in self.calls]


@pytest.fixture
def net():
    fake = FakeNet()
    with patch.object(providers.requests, 'get', side_effect=fake.get), \
            patch.object(providers.requests, 'post', side_effect=fake.post):
        yield fake


@pytest.fixture
def creds(settings):
    settings.OPENAI_ADMIN_KEY = FAKE_OPENAI
    settings.CLOUDFLARE_API_TOKEN = FAKE_CF_TOKEN
    settings.CLOUDFLARE_ACCOUNT_ID = FAKE_CF_ACCOUNT
    settings.HF_TOKEN = FAKE_HF


def _by_slug(body):
    return {s['slug']: s for s in body['services']}


def _assert_no_fakes(text):
    for fake in FAKES:
        assert fake not in text, fake


# -- permissions -----------------------------------------------------------

@pytest.mark.django_db
class TestPermissionMatrix:

    @pytest.mark.parametrize('method,url', [('get', LIST_URL), ('patch', NOTE_URL.format('neon'))])
    def test_anonymous_401(self, api_client, net, method, url):
        assert getattr(api_client, method)(url, {'login_note': 'x'}, format='json').status_code == 401

    @pytest.mark.parametrize('variant', sorted(DENIED_VARIANTS))
    @pytest.mark.parametrize('method,url', [('get', LIST_URL), ('patch', NOTE_URL.format('neon'))])
    def test_denied_variants_403(self, settings, net, variant, method, url):
        client, _ = make_operator_client(settings, **DENIED_VARIANTS[variant])
        assert getattr(client, method)(url, {'login_note': 'x'}, format='json').status_code == 403
        assert net.calls == []
        assert AdminAuditLog.objects.count() == 0
        assert ProviderNote.objects.count() == 0

    def test_admin_200(self, admin_client, net):
        assert admin_client.get(LIST_URL).status_code == 200
        assert admin_client.patch(NOTE_URL.format('neon'), {'login_note': 'a'}, format='json').status_code == 200

    def test_methods_not_allowed(self, admin_client, net):
        assert admin_client.post(LIST_URL, {}, format='json').status_code == 405
        assert admin_client.patch(LIST_URL, {}, format='json').status_code == 405
        assert admin_client.get(NOTE_URL.format('neon')).status_code == 405
        assert admin_client.put(NOTE_URL.format('neon'), {'login_note': 'x'}, format='json').status_code == 405
        assert admin_client.post(NOTE_URL.format('neon'), {'login_note': 'x'}, format='json').status_code == 405
        assert admin_client.delete(NOTE_URL.format('neon')).status_code == 405

    def test_throttle_class_wired(self):
        from apps.admin_dashboard.permissions import IsAdminOperator
        from apps.admin_dashboard.throttling import AdminThrottle
        from apps.admin_dashboard.views import ProviderNoteView, ServicesView
        for view in (ServicesView, ProviderNoteView):
            assert view.permission_classes == [IsAdminOperator]
            assert view.throttle_classes == [AdminThrottle]


# -- GET services/ ------------------------------------------------------------

@pytest.mark.django_db
class TestServicesList:

    def test_shape_and_order(self, admin_client, net):
        body = admin_client.get(LIST_URL).json()
        assert [s['slug'] for s in body['services']] == SLUGS
        assert body['fetched_at']
        for s in body['services']:
            assert set(s) == {'slug', 'name', 'dashboard_url', 'status', 'account', 'usage'}
            assert set(s['status']) == {'indicator', 'description', 'source'}
            assert set(s['account']) == {'auto', 'note'}
            assert s['dashboard_url'].startswith('https://')
        svc = _by_slug(body)
        assert svc['cloudflare']['name'] == 'Cloudflare R2'
        assert svc['railway']['status']['indicator'] == 'none'
        assert svc['vercel']['status'] == {
            'indicator': 'none', 'description': 'All Systems Operational',
            'source': 'https://www.vercel-status.com',
        }
        assert svc['neon']['status']['indicator'] == 'unknown'
        assert svc['neon']['status']['description'] == 'status page only'
        assert svc['neon']['status']['source'] == 'https://neonstatus.com'
        assert svc['gemini']['status']['indicator'] == 'none'
        # link-only providers: usage null; usage-capable but no creds: configured false
        for slug in ('railway', 'vercel', 'neon', 'gemini', 'huggingface', 'github'):
            assert svc[slug]['usage'] is None
        for slug in ('openai', 'cloudflare'):
            assert svc[slug]['usage'] == {'configured': False, 'items': [], 'cost': None, 'error': None}

    def test_missing_credentials_make_no_authenticated_call(self, admin_client, net, settings):
        settings.OPENAI_ADMIN_KEY = ''
        settings.CLOUDFLARE_API_TOKEN = ''
        settings.CLOUDFLARE_ACCOUNT_ID = ''
        settings.HF_TOKEN = ''
        admin_client.get(LIST_URL)
        joined = ' '.join(net.urls())
        assert 'api.openai.com' not in joined
        assert 'api.cloudflare.com' not in joined
        assert 'whoami' not in joined
        assert all('Authorization' not in (kw.get('headers') or {}) for _, _, kw in net.calls)

    def test_cloudflare_usage_needs_account_id_too(self, admin_client, net, settings):
        settings.CLOUDFLARE_API_TOKEN = FAKE_CF_TOKEN
        settings.CLOUDFLARE_ACCOUNT_ID = ''
        net.set('api.cloudflare.com/client/v4/accounts', _resp({'result': [{'id': 'z', 'name': 'Acme'}]}))
        svc = _by_slug(admin_client.get(LIST_URL).json())['cloudflare']
        assert svc['usage']['configured'] is False
        assert svc['account']['auto'] == 'Acme'
        assert not any(m == 'POST' for m, _, _ in net.calls)

    def test_identity_huggingface_and_cloudflare(self, admin_client, net, creds):
        net.set('whoami-v2', _resp({'name': 'archi', 'email': 'a@b.co'}))
        net.set('api.cloudflare.com/client/v4/accounts', _resp(
            {'result': [{'id': 'other', 'name': 'Other'}, {'id': FAKE_CF_ACCOUNT, 'name': 'Archi Org'}]}))
        net.set('api.cloudflare.com/client/v4/graphql', _resp({'data': {'viewer': {'accounts': [{}]}}}))
        net.set('api.openai.com', _resp({'data': []}))
        body = admin_client.get(LIST_URL).json()
        svc = _by_slug(body)
        assert svc['huggingface']['account']['auto'] == 'archi / a@b.co'
        assert svc['cloudflare']['account']['auto'] == 'Archi Org'
        assert svc['openai']['account']['auto'] is None
        _assert_no_fakes(json.dumps(body))

    def test_huggingface_identity_name_only(self, admin_client, net, creds):
        net.set('whoami-v2', _resp({'name': 'archi'}))
        net.set('api.cloudflare.com', requests.Timeout())
        net.set('api.openai.com', requests.Timeout())
        assert _by_slug(admin_client.get(LIST_URL).json())['huggingface']['account']['auto'] == 'archi'

    @pytest.mark.parametrize('failure', ['timeout', 'bad_json', 'http_500'])
    def test_single_provider_failure_is_isolated(self, admin_client, net, failure):
        value = {
            'timeout': requests.Timeout('slow'),
            'bad_json': _resp(None, bad_json=True),
            'http_500': _resp({}, status=500),
        }[failure]
        net.set('www.githubstatus.com', value)
        resp = admin_client.get(LIST_URL)
        assert resp.status_code == 200
        svc = _by_slug(resp.json())
        assert svc['github']['status']['indicator'] == 'unknown'
        assert svc['github']['status']['source'] == 'https://www.githubstatus.com'
        assert svc['vercel']['status']['indicator'] == 'none'
        assert svc['railway']['status']['indicator'] == 'none'

    @pytest.mark.parametrize('slug,needle', [
        ('railway', 'api.railwaystatus.com'),
        ('gemini', 'status.cloud.google.com'),
        ('huggingface', 'status.huggingface.co'),
        ('cloudflare', 'www.cloudflarestatus.com'),
        ('openai', 'status.openai.com'),
        ('vercel', 'www.vercel-status.com'),
    ])
    def test_each_status_fetcher_degrades_alone(self, admin_client, net, slug, needle):
        net.set(needle, requests.Timeout())
        resp = admin_client.get(LIST_URL)
        assert resp.status_code == 200
        svc = _by_slug(resp.json())
        assert svc[slug]['status']['indicator'] == 'unknown'
        assert svc['github']['status']['indicator'] == 'none'

    def test_status_page_without_status_key_is_unknown(self, admin_client, net):
        net.set('status.huggingface.co', _resp({'unexpected': True}))
        assert _by_slug(admin_client.get(LIST_URL).json())['huggingface']['status']['indicator'] == 'unknown'

    def test_invalid_indicator_value_normalized(self, admin_client, net):
        net.set('www.githubstatus.com', _resp({'status': {'indicator': 'weird', 'description': 'x'}}))
        assert _by_slug(admin_client.get(LIST_URL).json())['github']['status']['indicator'] == 'unknown'

    def test_provider_worker_crash_degrades_only_that_provider(self, admin_client, net):
        real = providers._fetch_one

        def flaky(provider):
            if provider['slug'] == 'neon':
                raise RuntimeError('boom')
            return real(provider)

        with patch.object(providers, '_fetch_one', side_effect=flaky):
            resp = admin_client.get(LIST_URL)
        assert resp.status_code == 200
        svc = _by_slug(resp.json())
        assert svc['neon']['status']['indicator'] == 'unknown'
        assert svc['github']['status']['indicator'] == 'none'

    def test_overall_timeout_degrades_unfinished_providers(self, admin_client, net, creds):
        import threading
        release = threading.Event()
        real = providers._fetch_one

        def slow(provider):
            if provider['slug'] == 'openai':
                release.wait(5)
            return real(provider)

        net.set('api.cloudflare.com', requests.Timeout())
        with patch.object(providers, '_fetch_one', side_effect=slow), \
                patch.object(providers, 'OVERALL_TIMEOUT', 0.3):
            resp = admin_client.get(LIST_URL)
        release.set()
        assert resp.status_code == 200
        svc = _by_slug(resp.json())
        assert svc['openai']['status']['indicator'] == 'unknown'
        assert svc['openai']['usage']['error'] == 'timeout'
        assert svc['openai']['usage']['configured'] is True
        assert svc['github']['status']['indicator'] == 'none'

    def test_cache_and_refresh(self, admin_client, net):
        admin_client.get(LIST_URL)
        n = len(net.calls)
        admin_client.get(LIST_URL)
        assert len(net.calls) == n  # served from cache
        admin_client.get(LIST_URL + '?refresh=1')
        assert len(net.calls) > n  # bypassed
        n2 = len(net.calls)
        admin_client.get(LIST_URL)
        assert len(net.calls) == n2  # refresh re-set the cache

    def test_no_credentials_in_body_or_logs(self, admin_client, net, creds, caplog):
        net.set('whoami-v2', _resp({'name': 'archi'}))
        net.set('api.cloudflare.com/client/v4/accounts', _resp({'result': [{'id': FAKE_CF_ACCOUNT, 'name': 'Org'}]}))
        # Failures whose exception text embeds the secrets: must not leak anywhere.
        net.set('api.cloudflare.com/client/v4/graphql', requests.ConnectionError(f'Bearer {FAKE_CF_TOKEN} {FAKE_CF_ACCOUNT}'))
        net.set('api.openai.com', requests.ConnectionError(f'Authorization: Bearer {FAKE_OPENAI}'))
        net.set('www.githubstatus.com', requests.ConnectionError(FAKE_HF))
        with caplog.at_level('DEBUG'):
            resp = admin_client.get(LIST_URL)
        assert resp.status_code == 200
        _assert_no_fakes(resp.content.decode())
        _assert_no_fakes(caplog.text)
        svc = _by_slug(resp.json())
        assert svc['openai']['usage']['configured'] is True
        assert svc['openai']['usage']['error'] == 'ConnectionError'
        assert svc['cloudflare']['usage']['error'] == 'ConnectionError'
        # logs still carry the provider slug + class for debuggability
        assert 'provider=openai' in caplog.text and 'ConnectionError' in caplog.text

    def test_credentials_only_sent_as_bearer_headers(self, admin_client, net, creds):
        net.set('api.openai.com', _resp({'data': []}))
        net.set('api.cloudflare.com', _resp({'result': [], 'data': {'viewer': {'accounts': [{}]}}}))
        net.set('whoami-v2', _resp({'name': 'n'}))
        admin_client.get(LIST_URL)
        for _, url, kw in net.calls:
            assert FAKE_OPENAI not in url and FAKE_CF_TOKEN not in url and FAKE_HF not in url
            assert FAKE_OPENAI not in json.dumps(kw.get('params') or {})
        auth = {url: kw['headers']['Authorization'] for _, url, kw in net.calls if kw.get('headers')}
        assert auth['https://api.openai.com/v1/organization/costs'] == f'Bearer {FAKE_OPENAI}'
        assert auth['https://huggingface.co/api/whoami-v2'] == f'Bearer {FAKE_HF}'

    def test_no_provider_secret_in_flags_or_services_setting_names(self, admin_client, settings, net):
        """Extends the flags secret-leak test to the new setting names."""
        from apps.admin_dashboard import flags as flags_mod
        settings.OPENAI_ADMIN_KEY = FAKE_OPENAI
        settings.CLOUDFLARE_API_TOKEN = FAKE_CF_TOKEN
        settings.CLOUDFLARE_ACCOUNT_ID = FAKE_CF_ACCOUNT
        raw = admin_client.get('/api/v1/admin/dashboard/flags/').content.decode()
        _assert_no_fakes(raw)
        names = {row[0] for row in flags_mod._REGISTRY}
        assert not names & {'OPENAI_ADMIN_KEY', 'CLOUDFLARE_API_TOKEN', 'CLOUDFLARE_ACCOUNT_ID'}


# -- derivations ----------------------------------------------------------------

class TestRailwayDerivation:

    def test_all_operational(self):
        out = providers.derive_railway_status({'components': [
            {'name': 'a', 'status': 'OPERATIONAL'}, {'name': 'b', 'status': 'OPERATIONAL'}]})
        assert out['indicator'] == 'none'

    def test_worst_leaf_in_nested_groups(self):
        out = providers.derive_railway_status({'components': [
            {'name': 'A', 'status': 'OPERATIONAL'},
            {'name': 'Group', 'type': 'group', 'status': 'OPERATIONAL', 'children': [
                {'name': 'c1', 'status': 'OPERATIONAL'},
                {'name': 'c2', 'status': 'DEGRADED_PERFORMANCE'},
                {'name': 'inner', 'type': 'group', 'children': [{'name': 'c3', 'status': 'MAJOR_OUTAGE'}]},
            ]},
        ]})
        assert out['indicator'] == 'major'
        assert out['source'] == 'https://status.railway.com'

    @pytest.mark.parametrize('raw,expected', [
        ('OPERATIONAL', 'none'), ('DEGRADED_PERFORMANCE', 'minor'), ('PARTIAL_OUTAGE', 'minor'),
        ('UNDER_MAINTENANCE', 'minor'), ('MAJOR_OUTAGE', 'major'), ('OUTAGE', 'major'),
    ])
    def test_status_mapping(self, raw, expected):
        assert providers.derive_railway_status([{'status': raw}])['indicator'] == expected

    def test_unknown_leaves_ignored_when_known_exist(self):
        out = providers.derive_railway_status([{'status': 'WEIRD'}, {'status': 'DEGRADED'}])
        assert out['indicator'] == 'minor'

    @pytest.mark.parametrize('payload', [{}, [], None, 'str', {'components': []}, [{'status': 'WEIRD'}]])
    def test_defensive_shapes_unknown(self, payload):
        assert providers.derive_railway_status(payload)['indicator'] == 'unknown'


class TestGeminiDerivation:

    def _inc(self, title, impact='SERVICE_DISRUPTION', end=None, **extra):
        inc = {'affected_products': [{'title': title}], 'status_impact': impact}
        if end is not None:
            inc['end'] = end
        inc.update(extra)
        return inc

    def test_no_incidents_none(self):
        assert providers.derive_gemini_status([])['indicator'] == 'none'

    def test_closed_incident_ignored(self):
        out = providers.derive_gemini_status([self._inc('Gemini API', end='2026-10-01T00:00:00Z')])
        assert out['indicator'] == 'none'

    def test_null_end_counts_as_open(self):
        out = providers.derive_gemini_status([{**self._inc('Gemini API'), 'end': None}])
        assert out['indicator'] == 'minor'

    def test_unrelated_product_ignored(self):
        assert providers.derive_gemini_status([self._inc('Cloud Storage', 'SERVICE_OUTAGE')])['indicator'] == 'none'

    def test_case_insensitive_and_vertex(self):
        assert providers.derive_gemini_status([self._inc('VERTEX AI Search')])['indicator'] == 'minor'

    def test_outage_is_major(self):
        out = providers.derive_gemini_status([self._inc('Gemini API', 'SERVICE_OUTAGE')])
        assert out['indicator'] == 'major'
        assert 'GCP status feed' in out['description']

    def test_major_beats_minor(self):
        out = providers.derive_gemini_status([
            self._inc('Gemini API'), self._inc('Vertex AI Gemini API', 'SERVICE_OUTAGE')])
        assert out['indicator'] == 'major'

    def test_bad_shape_raises(self):
        with pytest.raises(ValueError):
            providers.derive_gemini_status({'not': 'a list'})


# -- R2 cost + classification --------------------------------------------------------

class TestR2:

    def test_below_free_tier_is_zero_and_estimated(self):
        out = providers.estimate_r2_cost(5, 500_000, 5_000_000)
        assert out == {'amount': 0.0, 'currency': 'USD', 'estimated': True}

    def test_exactly_free_tier_is_zero(self):
        assert providers.estimate_r2_cost(10, 1_000_000, 10_000_000)['amount'] == 0.0

    def test_storage_only(self):
        assert providers.estimate_r2_cost(110, 0, 0)['amount'] == 1.5  # 100 GB * 0.015

    def test_class_a_and_b(self):
        # (3e6-1e6)/1e6*4.5 = 9.0 ; (30e6-10e6)/1e6*0.36 = 7.2
        assert providers.estimate_r2_cost(0, 3_000_000, 30_000_000)['amount'] == 16.2

    def test_combined_rounding(self):
        assert providers.estimate_r2_cost(20, 2_000_000, 11_000_000)['amount'] == round(0.15 + 4.5 + 0.36, 2)

    @pytest.mark.parametrize('action', sorted(providers.R2_CLASS_A))
    def test_class_a_actions(self, action):
        assert providers.classify_r2_action(action) == 'A'

    @pytest.mark.parametrize('action', sorted(providers.R2_CLASS_B))
    def test_class_b_actions(self, action):
        assert providers.classify_r2_action(action) == 'B'

    @pytest.mark.parametrize('action', sorted(providers.R2_FREE_OPS))
    def test_free_ops_excluded(self, action):
        assert providers.classify_r2_action(action) is None

    def test_unknown_action_is_class_b(self):
        assert providers.classify_r2_action('SomeFutureOp') == 'B'
        assert providers.classify_r2_action(None) == 'B'


def _cf_graphql_payload():
    return {'data': {'viewer': {'accounts': [{
        'r2StorageAdaptiveGroups': [
            # DESC by datetime: first row per bucket is the latest
            {'max': {'objectCount': 120, 'payloadSize': 3_500_000_000}, 'dimensions': {'bucketName': 'images', 'datetime': '2026-10-06T10:00:00Z'}},
            {'max': {'objectCount': 100, 'payloadSize': 3_000_000_000}, 'dimensions': {'bucketName': 'images', 'datetime': '2026-10-05T10:00:00Z'}},
            {'max': {'objectCount': 7, 'payloadSize': 500_000_000}, 'dimensions': {'bucketName': 'works', 'datetime': '2026-10-06T10:00:00Z'}},
        ],
        'r2OperationsAdaptiveGroups': [
            {'sum': {'requests': 2_000_000}, 'dimensions': {'actionType': 'PutObject'}},
            {'sum': {'requests': 500_000}, 'dimensions': {'actionType': 'ListObjects'}},
            {'sum': {'requests': 12_000_000}, 'dimensions': {'actionType': 'GetObject'}},
            {'sum': {'requests': 900_000}, 'dimensions': {'actionType': 'MysteryOp'}},
            {'sum': {'requests': 9_999_999}, 'dimensions': {'actionType': 'DeleteObject'}},
        ],
    }]}}}


@pytest.mark.django_db
class TestCloudflareUsage:

    def test_usage_items_and_cost(self, admin_client, net, creds):
        net.set('api.cloudflare.com/client/v4/graphql', _resp(_cf_graphql_payload()))
        net.set('api.cloudflare.com/client/v4/accounts', _resp({'result': []}))
        net.set('api.openai.com', requests.Timeout())
        usage = _by_slug(admin_client.get(LIST_URL).json())['cloudflare']['usage']
        assert usage['configured'] is True and usage['error'] is None
        items = {i['label']: i for i in usage['items']}
        assert items['images 저장량'] == {'label': 'images 저장량', 'value': 3.5, 'unit': 'GB'}
        assert items['images 객체 수']['value'] == 120
        assert items['works 저장량']['value'] == 0.5
        assert items['works 객체 수']['value'] == 7
        assert items['Class A 요청']['value'] == 2_500_000
        assert items['Class B 요청']['value'] == 12_900_000  # Get + unknown; Delete excluded
        # storage 4 GB (free) ; A: 1.5M over -> 6.75 ; B: 2.9M over -> 1.044 => 7.79
        assert usage['cost'] == {'amount': 7.79, 'currency': 'USD', 'estimated': True}

    def test_graphql_request_shape(self, admin_client, net, creds):
        net.set('api.cloudflare.com/client/v4/graphql', _resp(_cf_graphql_payload()))
        net.set('api.cloudflare.com/client/v4/accounts', _resp({'result': []}))
        net.set('api.openai.com', requests.Timeout())
        admin_client.get(LIST_URL)
        method, url, kw = next(c for c in net.calls if c[1].endswith('/graphql'))
        assert method == 'POST'
        assert kw['timeout'] == 5
        assert kw['headers']['Authorization'] == f'Bearer {FAKE_CF_TOKEN}'
        v = kw['json']['variables']
        assert v['accountTag'] == FAKE_CF_ACCOUNT
        start = datetime.strptime(v['start'], '%Y-%m-%dT%H:%M:%SZ')
        end = datetime.strptime(v['end'], '%Y-%m-%dT%H:%M:%SZ')
        assert start.day == 1 and (start.hour, start.minute, start.second) == (0, 0, 0)
        assert 0 <= (end - start).days <= 31
        assert 'r2StorageAdaptiveGroups' in kw['json']['query']
        assert 'r2OperationsAdaptiveGroups' in kw['json']['query']

    @pytest.mark.parametrize('payload', [
        {'errors': [{'message': 'nope'}]},
        {'data': {'viewer': {'accounts': []}}},
        {'data': None},
    ])
    def test_graphql_errors_degrade(self, admin_client, net, creds, payload):
        net.set('api.cloudflare.com/client/v4/graphql', _resp(payload))
        net.set('api.cloudflare.com/client/v4/accounts', _resp({'result': []}))
        net.set('api.openai.com', requests.Timeout())
        resp = admin_client.get(LIST_URL)
        assert resp.status_code == 200
        usage = _by_slug(resp.json())['cloudflare']['usage']
        assert usage['configured'] is True and usage['error'] == 'ValueError' and usage['cost'] is None


# -- OpenAI -----------------------------------------------------------------------------

def _openai_page(values, has_more=False, next_page=None, currency='usd'):
    return {
        'data': [{'results': [{'amount': {'value': v, 'currency': currency}} for v in values]}],
        'has_more': has_more, 'next_page': next_page,
    }


@pytest.mark.django_db
class TestOpenAIUsage:

    def _setup(self, net):
        net.set('api.cloudflare.com', requests.Timeout())

    def test_pagination_sum(self, admin_client, net, creds):
        self._setup(net)
        pages = {
            None: _openai_page([1.25, 2.0], True, 'p2'),
            'p2': _openai_page([0.5], True, 'p3'),
            'p3': _openai_page([4.0], False, None),
        }
        net.set('api.openai.com', lambda url, kw: _resp(pages[(kw.get('params') or {}).get('page')]))
        usage = _by_slug(admin_client.get(LIST_URL).json())['openai']['usage']
        assert usage['cost'] == {'amount': 7.75, 'currency': 'USD', 'estimated': False}
        assert usage['items'] == [{'label': '이번 달 비용', 'value': 7.75, 'unit': 'USD'}]
        assert usage['configured'] is True and usage['error'] is None
        calls = [c for c in net.calls if 'api.openai.com' in c[1]]
        assert len(calls) == 3
        first = calls[0][2]['params']
        assert first['bucket_width'] == '1d' and first['limit'] == 31
        month_start = datetime.fromtimestamp(first['start_time'], tz=timezone.utc)
        assert month_start.day == 1 and month_start.hour == 0
        assert calls[1][2]['params']['page'] == 'p2'

    def test_stops_after_three_pages(self, admin_client, net, creds):
        self._setup(net)
        net.set('api.openai.com', lambda url, kw: _resp(_openai_page([1.0], True, 'more')))
        usage = _by_slug(admin_client.get(LIST_URL).json())['openai']['usage']
        assert usage['cost']['amount'] == 3.0
        assert len([c for c in net.calls if 'api.openai.com' in c[1]]) == 3

    def test_currency_uppercased(self, admin_client, net, creds):
        self._setup(net)
        net.set('api.openai.com', _resp(_openai_page(['2.505'], currency='eur')))
        cost = _by_slug(admin_client.get(LIST_URL).json())['openai']['usage']['cost']
        assert cost['currency'] == 'EUR'
        assert cost['amount'] == round(2.505, 2)

    @pytest.mark.parametrize('value', [requests.Timeout(), _resp(None, bad_json=True), _resp({}, status=403),
                                       _resp({'data': 'nope'})])
    def test_failure_degrades_with_error_string(self, admin_client, net, creds, value):
        self._setup(net)
        net.set('api.openai.com', value)
        resp = admin_client.get(LIST_URL)
        assert resp.status_code == 200
        usage = _by_slug(resp.json())['openai']['usage']
        assert usage['configured'] is True
        assert usage['cost'] is None and usage['items'] == []
        assert isinstance(usage['error'], str) and usage['error']
        _assert_no_fakes(resp.content.decode())

    def test_http_error_string_includes_status_only(self, admin_client, net, creds):
        self._setup(net)
        net.set('api.openai.com', _resp({}, status=403))
        usage = _by_slug(admin_client.get(LIST_URL).json())['openai']['usage']
        assert usage['error'] == 'HTTPError 403'

    def test_degraded_result_uses_short_cache_ttl(self, admin_client, net, creds):
        self._setup(net)
        net.set('api.openai.com', requests.Timeout())
        with patch('apps.admin_dashboard.views.cache.set') as cache_set:
            admin_client.get(LIST_URL)
        assert cache_set.call_args[0][2] == 60


# -- PATCH note ------------------------------------------------------------------------------

@pytest.mark.django_db
class TestProviderNote:

    def test_unknown_slug_404(self, admin_client, net):
        resp = admin_client.patch(NOTE_URL.format('nope'), {'login_note': 'x'}, format='json')
        assert resp.status_code == 404
        assert ProviderNote.objects.count() == 0
        assert AdminAuditLog.objects.count() == 0

    def test_too_long_400(self, admin_client, net):
        resp = admin_client.patch(NOTE_URL.format('neon'), {'login_note': 'x' * 201}, format='json')
        assert resp.status_code == 400
        assert ProviderNote.objects.count() == 0
        assert AdminAuditLog.objects.count() == 0

    def test_exactly_200_ok_after_strip(self, admin_client, net):
        resp = admin_client.patch(NOTE_URL.format('neon'), {'login_note': '  ' + 'x' * 200 + '  '}, format='json')
        assert resp.status_code == 200
        assert len(resp.json()['login_note']) == 200

    @pytest.mark.parametrize('body', [{}, {'login_note': None}, {'login_note': 5}, {'login_note': ['a']}])
    def test_missing_or_non_string_400(self, admin_client, net, body):
        assert admin_client.patch(NOTE_URL.format('neon'), body, format='json').status_code == 400

    def test_upsert_audit_and_next_get_sees_note(self, admin_client, net):
        admin_client.get(LIST_URL)  # primes the 10-min cache
        calls_before = len(net.calls)

        r1 = admin_client.patch(NOTE_URL.format('vercel'), {'login_note': '  team@acme.com  '}, format='json')
        assert r1.status_code == 200
        body = r1.json()
        assert body['slug'] == 'vercel' and body['login_note'] == 'team@acme.com' and body['updated_at']

        seen = _by_slug(admin_client.get(LIST_URL).json())
        assert seen['vercel']['account']['note'] == 'team@acme.com'
        assert seen['github']['account']['note'] == ''
        assert len(net.calls) == calls_before  # no refresh needed: note merged after cache

        r2 = admin_client.patch(NOTE_URL.format('vercel'), {'login_note': 'new@acme.com'}, format='json')
        assert r2.status_code == 200
        assert ProviderNote.objects.filter(provider='vercel').count() == 1
        assert _by_slug(admin_client.get(LIST_URL).json())['vercel']['account']['note'] == 'new@acme.com'

        rows = list(AdminAuditLog.objects.filter(action='provider_note.update').order_by('id'))
        assert len(rows) == 2
        assert rows[0].target_type == 'provider' and rows[0].target_id == 'vercel'
        assert rows[0].payload == {'old': '', 'new': 'team@acme.com'}
        assert rows[1].payload == {'old': 'team@acme.com', 'new': 'new@acme.com'}
        assert rows[0].actor.email == 'admin@example.com'

        note = ProviderNote.objects.get(provider='vercel')
        assert note.updated_by.email == 'admin@example.com'

    def test_clearing_note(self, admin_client, net):
        admin_client.patch(NOTE_URL.format('github'), {'login_note': 'abc'}, format='json')
        resp = admin_client.patch(NOTE_URL.format('github'), {'login_note': '   '}, format='json')
        assert resp.status_code == 200 and resp.json()['login_note'] == ''
        last = AdminAuditLog.objects.filter(action='provider_note.update').order_by('-id').first()
        assert last.payload == {'old': 'abc', 'new': ''}

    def test_note_survives_refresh(self, admin_client, net):
        admin_client.patch(NOTE_URL.format('neon'), {'login_note': 'n'}, format='json')
        body = admin_client.get(LIST_URL + '?refresh=1').json()
        assert _by_slug(body)['neon']['account']['note'] == 'n'
