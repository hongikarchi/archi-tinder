"""External-service registry for the admin dashboard "external services" panel (ADMIN-DASH-2a).

Per provider: status (public status pages), optional account identity (read-only token),
optional usage/cost (read-only token). Only read-only credentials are ever used
(OPENAI_ADMIN_KEY restricted to Usage read, CLOUDFLARE_API_TOKEN = Account Analytics Read,
existing HF_TOKEN). Railway / Vercel / Neon tokens all carry write power -> not used; those
providers are status + memo + dashboard link only.

Credential hygiene (hard rule): credentials are only ever placed in request headers. They
must never appear in returned data, exception-derived strings, or log lines. Failures are
logged as ``provider slug + exception class`` ONLY (never ``str(exc)`` / ``repr(exc)``, and
never ``exc_info``), and surfaced as short class/status strings.

Every provider part (status / identity / usage) is wrapped so one failing only degrades
that provider's own fields.
"""
import logging
from concurrent.futures import ThreadPoolExecutor, wait
from datetime import datetime, timezone as dt_timezone

import requests
from django.conf import settings

logger = logging.getLogger('apps.admin_dashboard')

_TIMEOUT = 5          # seconds, per HTTP call
OVERALL_TIMEOUT = 8   # seconds, whole fan-out
_MAX_WORKERS = 8

INDICATORS = ('none', 'minor', 'major', 'critical', 'unknown')

# Cloudflare R2 pricing -- https://developers.cloudflare.com/r2/pricing/ (checked 2026-10-06).
# Standard storage class. Free tier is monthly and applies per account.
R2_PRICING = {
    'free_storage_gb': 10,
    'storage_per_gb_month': 0.015,
    'free_class_a': 1_000_000,
    'class_a_per_million': 4.50,
    'free_class_b': 10_000_000,
    'class_b_per_million': 0.36,
}

R2_CLASS_A = frozenset({
    'ListBuckets', 'PutBucket', 'ListObjects', 'PutObject', 'CopyObject',
    'CompleteMultipartUpload', 'CreateMultipartUpload', 'ListMultipartUploads',
    'UploadPart', 'UploadPartCopy', 'ListParts', 'PutBucketEncryption', 'PutBucketCors',
    'PutBucketLifecycleConfiguration',
})
R2_CLASS_B = frozenset({
    'HeadBucket', 'HeadObject', 'GetObject', 'UsageSummary', 'GetBucketEncryption',
    'GetBucketLocation', 'GetBucketCors', 'GetBucketLifecycleConfiguration',
})
R2_FREE_OPS = frozenset({'DeleteObject', 'DeleteBucket', 'AbortMultipartUpload', 'DeleteObjects'})


# -- helpers ---------------------------------------------------------------

def _err(exc):
    """Short, credential-free description of an exception (class + HTTP status only)."""
    resp = getattr(exc, 'response', None)
    code = getattr(resp, 'status_code', None)
    if isinstance(code, int):
        return f'{type(exc).__name__} {code}'
    return type(exc).__name__


def _get_json(url, headers=None, params=None):
    resp = requests.get(url, headers=headers, params=params, timeout=_TIMEOUT)
    resp.raise_for_status()
    return resp.json()


def _status(indicator, description, source):
    if indicator not in INDICATORS:
        indicator = 'unknown'
    return {'indicator': indicator, 'description': str(description)[:200], 'source': source}


def _unknown(source, description='unavailable'):
    return _status('unknown', description, source)


def _month_start(now=None):
    now = now or datetime.now(dt_timezone.utc)
    return now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)


def _unconfigured_usage():
    return {'configured': False, 'items': [], 'cost': None, 'error': None}


# -- status fetchers ---------------------------------------------------------

def _atlassian_status(host):
    def fetch():
        data = _get_json(f'{host}/api/v2/status.json')
        st = data['status']
        return _status(st.get('indicator'), st.get('description') or '', host)
    return fetch


_RAILWAY_STATUS_URL = 'https://api.railwaystatus.com/status'
_RAILWAY_SOURCE = 'https://status.railway.com'
_RAILWAY_RANK = {'none': 1, 'minor': 2, 'major': 3}


def _railway_map(raw):
    s = str(raw or '').upper()
    if s == 'OPERATIONAL':
        return 'none'
    if s.startswith(('DEGRADED', 'PARTIAL')) or s == 'UNDER_MAINTENANCE':
        return 'minor'
    if s.startswith(('MAJOR', 'OUTAGE')):
        return 'major'
    return 'unknown'


def _railway_leaves(node, out):
    """Collect leaf component status strings from a (possibly nested) component tree."""
    if isinstance(node, list):
        for item in node:
            _railway_leaves(item, out)
        return
    if not isinstance(node, dict):
        return
    children = node.get('children')
    if children is None and node.get('type') == 'group':
        children = node.get('components')
    if isinstance(children, list) and children:
        _railway_leaves(children, out)
    elif 'status' in node and not isinstance(node.get('status'), (dict, list)):
        out.append(node['status'])
    elif isinstance(node.get('components'), list):
        _railway_leaves(node['components'], out)


def derive_railway_status(payload):
    """Worst leaf-component indicator -> status dict. Defensive about payload shape."""
    leaves = []
    root = payload.get('components', payload) if isinstance(payload, dict) else payload
    _railway_leaves(root, leaves)
    known = [m for m in (_railway_map(s) for s in leaves) if m != 'unknown']
    if not known:
        return _unknown(_RAILWAY_SOURCE, 'no component data')
    worst = max(known, key=lambda m: _RAILWAY_RANK[m])
    if worst == 'none':
        desc = 'All systems operational'
    else:
        bad = sum(1 for m in known if m != 'none')
        desc = f'{bad} component(s) not operational'
    return _status(worst, desc, _RAILWAY_SOURCE)


def _railway_status():
    return derive_railway_status(_get_json(_RAILWAY_STATUS_URL))


def _neon_status():
    return _status('unknown', 'status page only', 'https://neonstatus.com')


_GCP_SOURCE = 'https://status.cloud.google.com'


def derive_gemini_status(incidents):
    """Open (no ``end``) GCP incidents touching Gemini/Vertex -> minor/major, else none."""
    if not isinstance(incidents, list):
        raise ValueError('unexpected incidents shape')
    open_count = 0
    worst = 'none'
    for inc in incidents:
        if not isinstance(inc, dict) or inc.get('end'):
            continue
        products = inc.get('affected_products') or []
        hit = any(
            isinstance(p, dict) and any(k in str(p.get('title', '')).lower() for k in ('gemini', 'vertex'))
            for p in products
        )
        if not hit:
            continue
        open_count += 1
        if 'OUTAGE' in str(inc.get('status_impact', '')).upper():
            worst = 'major'
        elif worst == 'none':
            worst = 'minor'
    if open_count:
        desc = f'{open_count} open Gemini/Vertex incident(s) (GCP status feed)'
    else:
        desc = 'No open Gemini/Vertex incidents (GCP status feed)'
    return _status(worst, desc, _GCP_SOURCE)


def _gemini_status():
    return derive_gemini_status(_get_json(f'{_GCP_SOURCE}/incidents.json'))


# -- identity fetchers -------------------------------------------------------

def _hf_identity():
    token = getattr(settings, 'HF_TOKEN', '')
    if not token:
        return None
    data = _get_json('https://huggingface.co/api/whoami-v2', headers={'Authorization': f'Bearer {token}'})
    name = data.get('name')
    if not name:
        return None
    email = data.get('email')
    return f'{name} / {email}' if email else str(name)


def _cloudflare_identity():
    token = getattr(settings, 'CLOUDFLARE_API_TOKEN', '')
    if not token:
        return None
    data = _get_json('https://api.cloudflare.com/client/v4/accounts', headers={'Authorization': f'Bearer {token}'})
    results = data.get('result') or []
    if not results:
        return None
    wanted = getattr(settings, 'CLOUDFLARE_ACCOUNT_ID', '')
    pick = next((r for r in results if wanted and r.get('id') == wanted), results[0])
    return pick.get('name') or None


# -- usage fetchers ----------------------------------------------------------

_OPENAI_COSTS_URL = 'https://api.openai.com/v1/organization/costs'
_OPENAI_MAX_PAGES = 3


def _openai_usage():
    key = getattr(settings, 'OPENAI_ADMIN_KEY', '')
    if not key:
        return _unconfigured_usage()
    headers = {'Authorization': f'Bearer {key}'}
    params = {
        'start_time': int(_month_start().timestamp()),
        'bucket_width': '1d',
        'limit': 31,
    }
    total = 0.0
    currency = None
    for _ in range(_OPENAI_MAX_PAGES):
        data = _get_json(_OPENAI_COSTS_URL, headers=headers, params=params)
        buckets = data.get('data')
        if not isinstance(buckets, list):
            raise ValueError('unexpected costs shape')
        for bucket in buckets:
            for res in (bucket.get('results') or []):
                amount = res.get('amount') or {}
                if 'value' not in amount:
                    continue
                total += float(amount['value'])
                currency = currency or amount.get('currency')
        nxt = data.get('next_page')
        if data.get('has_more') and nxt:
            params = {**params, 'page': nxt}
        else:
            break
    currency = str(currency).upper() if currency else 'USD'
    value = round(total, 2)
    return {
        'configured': True,
        'items': [{'label': '이번 달 비용', 'value': value, 'unit': 'USD'}],
        'cost': {'amount': value, 'currency': currency, 'estimated': False},
        'error': None,
    }


def classify_r2_action(action):
    """'A' | 'B' | None (free op). Unknown action types count as Class B."""
    if action in R2_FREE_OPS:
        return None
    if action in R2_CLASS_A:
        return 'A'
    return 'B'


def estimate_r2_cost(total_gb, class_a, class_b):
    """Estimated monthly R2 bill in USD with the free tier applied (always an estimate)."""
    p = R2_PRICING
    cost = (
        max(0, total_gb - p['free_storage_gb']) * p['storage_per_gb_month']
        + max(0, class_a - p['free_class_a']) / 1e6 * p['class_a_per_million']
        + max(0, class_b - p['free_class_b']) / 1e6 * p['class_b_per_million']
    )
    return {'amount': round(cost, 2), 'currency': 'USD', 'estimated': True}


_CF_GRAPHQL_URL = 'https://api.cloudflare.com/client/v4/graphql'
_CF_QUERY = """
query R2Usage($accountTag: string!, $start: Time!, $end: Time!) {
  viewer {
    accounts(filter: {accountTag: $accountTag}) {
      r2StorageAdaptiveGroups(limit: 1000, filter: {datetime_geq: $start, datetime_leq: $end}, orderBy: [datetime_DESC]) {
        max { objectCount payloadSize }
        dimensions { bucketName datetime }
      }
      r2OperationsAdaptiveGroups(limit: 1000, filter: {datetime_geq: $start, datetime_leq: $end}) {
        sum { requests }
        dimensions { actionType }
      }
    }
  }
}
"""


def _cloudflare_usage():
    token = getattr(settings, 'CLOUDFLARE_API_TOKEN', '')
    account_id = getattr(settings, 'CLOUDFLARE_ACCOUNT_ID', '')
    if not token or not account_id:
        return _unconfigured_usage()
    now = datetime.now(dt_timezone.utc)
    body = {
        'query': _CF_QUERY,
        'variables': {
            'accountTag': account_id,
            'start': _month_start(now).strftime('%Y-%m-%dT%H:%M:%SZ'),
            'end': now.strftime('%Y-%m-%dT%H:%M:%SZ'),
        },
    }
    resp = requests.post(_CF_GRAPHQL_URL, headers={'Authorization': f'Bearer {token}'}, json=body, timeout=_TIMEOUT)
    resp.raise_for_status()
    data = resp.json()
    if data.get('errors'):
        raise ValueError('graphql errors')
    accounts = ((data.get('data') or {}).get('viewer') or {}).get('accounts')
    if not isinstance(accounts, list) or not accounts:
        raise ValueError('unexpected graphql shape')
    acct = accounts[0]

    buckets = {}
    for row in acct.get('r2StorageAdaptiveGroups') or []:
        name = (row.get('dimensions') or {}).get('bucketName')
        if name is None or name in buckets:
            continue  # rows are datetime DESC -> first per bucket is the latest
        mx = row.get('max') or {}
        buckets[name] = (float(mx.get('payloadSize') or 0), int(mx.get('objectCount') or 0))

    class_a = class_b = 0
    for row in acct.get('r2OperationsAdaptiveGroups') or []:
        n = int((row.get('sum') or {}).get('requests') or 0)
        kind = classify_r2_action((row.get('dimensions') or {}).get('actionType'))
        if kind == 'A':
            class_a += n
        elif kind == 'B':
            class_b += n

    items = []
    total_gb = 0.0
    for name, (payload, objects) in buckets.items():
        gb = payload / 1e9
        total_gb += gb
        items.append({'label': f'{name} 저장량', 'value': round(gb, 2), 'unit': 'GB'})
        items.append({'label': f'{name} 객체 수', 'value': objects, 'unit': '개'})
    items.append({'label': 'Class A 요청', 'value': class_a, 'unit': '회'})
    items.append({'label': 'Class B 요청', 'value': class_b, 'unit': '회'})
    return {
        'configured': True,
        'items': items,
        'cost': estimate_r2_cost(total_gb, class_a, class_b),
        'error': None,
    }


# -- registry ----------------------------------------------------------------

def _provider(slug, name, dashboard_url, status, status_source, identity=None, usage=None):
    return {
        'slug': slug, 'name': name, 'dashboard_url': dashboard_url,
        'status': status, 'status_source': status_source,
        'identity': identity, 'usage': usage,
    }


PROVIDERS = [
    _provider('railway', 'Railway', 'https://railway.com/dashboard', _railway_status, _RAILWAY_SOURCE),
    _provider('vercel', 'Vercel', 'https://vercel.com/dashboard',
              _atlassian_status('https://www.vercel-status.com'), 'https://www.vercel-status.com'),
    _provider('neon', 'Neon', 'https://console.neon.tech', _neon_status, 'https://neonstatus.com'),
    _provider('cloudflare', 'Cloudflare R2', 'https://dash.cloudflare.com',
              _atlassian_status('https://www.cloudflarestatus.com'), 'https://www.cloudflarestatus.com',
              identity=_cloudflare_identity, usage=_cloudflare_usage),
    _provider('openai', 'OpenAI', 'https://platform.openai.com/usage',
              _atlassian_status('https://status.openai.com'), 'https://status.openai.com',
              usage=_openai_usage),
    _provider('gemini', 'Gemini', 'https://aistudio.google.com/usage', _gemini_status, _GCP_SOURCE),
    _provider('huggingface', 'Hugging Face', 'https://huggingface.co/settings/billing',
              _atlassian_status('https://status.huggingface.co'), 'https://status.huggingface.co',
              identity=_hf_identity),
    _provider('github', 'GitHub', 'https://github.com/hongikarchi/archi-tinder',
              _atlassian_status('https://www.githubstatus.com'), 'https://www.githubstatus.com'),
]

PROVIDER_SLUGS = tuple(p['slug'] for p in PROVIDERS)


def _usage_is_configured(provider):
    """Whether this provider's usage credentials are present (no network)."""
    slug = provider['slug']
    if slug == 'openai':
        return bool(getattr(settings, 'OPENAI_ADMIN_KEY', ''))
    if slug == 'cloudflare':
        return bool(getattr(settings, 'CLOUDFLARE_API_TOKEN', '') and getattr(settings, 'CLOUDFLARE_ACCOUNT_ID', ''))
    return False


def _base(provider):
    return {
        'slug': provider['slug'],
        'name': provider['name'],
        'dashboard_url': provider['dashboard_url'],
    }


def _degraded(provider, reason):
    usage = None
    if provider['usage'] is not None:
        configured = _usage_is_configured(provider)
        usage = {'configured': configured, 'items': [], 'cost': None, 'error': reason if configured else None}
    return {
        **_base(provider),
        'status': _unknown(provider['status_source']),
        'account': {'auto': None},
        'usage': usage,
    }


def _fetch_one(provider):
    """Fetch one provider; every part fails independently and never raises."""
    slug = provider['slug']
    try:
        status = provider['status']()
    except Exception as exc:
        logger.warning('admin services: status failed provider=%s exc=%s', slug, type(exc).__name__)
        status = _unknown(provider['status_source'])

    auto = None
    if provider['identity'] is not None:
        try:
            auto = provider['identity']()
        except Exception as exc:
            logger.warning('admin services: identity failed provider=%s exc=%s', slug, type(exc).__name__)

    usage = None
    if provider['usage'] is not None:
        try:
            usage = provider['usage']()
        except Exception as exc:
            logger.warning('admin services: usage failed provider=%s exc=%s', slug, type(exc).__name__)
            usage = {'configured': _usage_is_configured(provider), 'items': [], 'cost': None, 'error': _err(exc)}

    return {**_base(provider), 'status': status, 'account': {'auto': auto}, 'usage': usage}


def fetch_all_services():
    """Fetch every provider concurrently (bounded). Returns (services, degraded_flag)."""
    results = {}
    executor = ThreadPoolExecutor(max_workers=_MAX_WORKERS)
    try:
        futures = {executor.submit(_fetch_one, p): p for p in PROVIDERS}
        done, not_done = wait(futures, timeout=OVERALL_TIMEOUT)
        for fut in done:
            provider = futures[fut]
            try:
                results[provider['slug']] = fut.result()
            except Exception as exc:  # _fetch_one never raises; belt and braces
                logger.warning('admin services: worker failed provider=%s exc=%s', provider['slug'], type(exc).__name__)
                results[provider['slug']] = _degraded(provider, type(exc).__name__)
        for fut in not_done:
            provider = futures[fut]
            logger.warning('admin services: timed out provider=%s', provider['slug'])
            results[provider['slug']] = _degraded(provider, 'timeout')
    finally:
        executor.shutdown(wait=False, cancel_futures=True)

    services = [results[p['slug']] for p in PROVIDERS]
    degraded = bool(not_done) or any((s['usage'] or {}).get('error') for s in services)
    return services, degraded
