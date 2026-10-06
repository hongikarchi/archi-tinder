"""Admin dashboard read-only endpoints (ADMIN-DASH-1, PR 1).

Every view: APIView + IsAdminOperator (permission runs BEFORE the throttle, denials
never touch the DB) + AdminThrottle. Each endpoint is independent -- a failing external
dependency degrades its own fields, never the response status.
"""
import logging
import os
from datetime import timedelta

from django.core.cache import cache
from django.db import connections
from django.db.migrations.executor import MigrationExecutor
from django.utils import timezone
from rest_framework import status as http_status
from rest_framework.response import Response
from rest_framework.views import APIView

from .audit import log_admin_action
from .flags import get_flags
from .github import fetch_github_state
from .models import AdminAuditLog, ProviderNote
from .permissions import IsAdminOperator
from .providers import PROVIDER_SLUGS, fetch_all_services
from .throttling import AdminThrottle

logger = logging.getLogger('apps.admin_dashboard')

_GITHUB_CACHE_KEY = 'admin_dash:github'
_GITHUB_TTL = 15 * 60
_GITHUB_ERROR_TTL = 60  # failures are retried soon; don't pin nulls for 15 min
_STATS_CACHE_KEY = 'admin_dash:stats'
_STATS_TTL = 60

_SERVICES_CACHE_KEY = 'admin:services:v1'
_SERVICES_TTL = 10 * 60
_SERVICES_ERROR_TTL = 60  # degraded fetch is retried soon; don't pin failures for 10 min
_NOTE_MAX_LEN = 200

_DEFAULT_PAGE_SIZE = 50
_MAX_PAGE_SIZE = 100


class AdminDashboardView(APIView):
    permission_classes = [IsAdminOperator]
    throttle_classes = [AdminThrottle]


class VersionView(AdminDashboardView):
    """GET version/ -- deployed backend identity + GitHub main/develop/CI state.

    Opening the dashboard hits this endpoint, so the dashboard-open audit row is
    written here (after permission + throttle).
    """

    def get(self, request):
        log_admin_action(request, 'dashboard_open')

        github = cache.get(_GITHUB_CACHE_KEY)
        if github is None:
            github = fetch_github_state()
            cache.set(_GITHUB_CACHE_KEY, github, _GITHUB_ERROR_TTL if github.get('error') else _GITHUB_TTL)

        return Response({
            'backend': {
                'sha': os.environ.get('RAILWAY_GIT_COMMIT_SHA') or None,
                'deployment_id': os.environ.get('RAILWAY_DEPLOYMENT_ID') or None,
                'environment': os.environ.get('RAILWAY_ENVIRONMENT_NAME') or None,
            },
            'github': github,
        })


class MigrationsView(AdminDashboardView):
    """GET migrations/ -- migrations not yet applied on the 'default' DB (read-only)."""

    def get(self, request):
        executor = MigrationExecutor(connections['default'])
        plan = executor.migration_plan(executor.loader.graph.leaf_nodes())
        unapplied = [f'{migration.app_label}.{migration.name}' for migration, _backwards in plan]
        return Response({'count': len(unapplied), 'unapplied': unapplied})


class FlagsView(AdminDashboardView):
    """GET flags/ -- static registry of feature flags (labels + values only)."""

    def get(self, request):
        return Response({'flags': get_flags()})


def _safe(label, fn):
    """Run one stats block; a failure nulls only that block."""
    try:
        return fn()
    except Exception:
        logger.exception('admin stats block failed: %s', label)
        return None


def _users_block(now):
    from apps.accounts.models import UserProfile
    return {
        'total': UserProfile.objects.count(),
        'google_verified': UserProfile.objects.filter(is_guest=False).count(),
        'guest': UserProfile.objects.filter(is_guest=True).count(),
        'new_7d': UserProfile.objects.filter(created_at__gte=now - timedelta(days=7)).count(),
        'new_30d': UserProfile.objects.filter(created_at__gte=now - timedelta(days=30)).count(),
    }


def _works_block(now):
    from apps.works.models import Work
    return {
        'total': Work.objects.count(),
        'published': Work.objects.filter(is_publishable=True).count(),
        'rejected': Work.objects.filter(is_publishable=False).exclude(gate_reason='').count(),
        'processing': Work.objects.filter(is_publishable=False, gate_reason='').count(),
    }


def _reports_block(now):
    from apps.messaging.models import Report
    return {
        'total': Report.objects.count(),
        'last_7d': Report.objects.filter(created_at__gte=now - timedelta(days=7)).count(),
    }


def _sessions_block(now):
    from apps.recommendation.models import AnalysisSession
    last_7d = AnalysisSession.objects.filter(created_at__gte=now - timedelta(days=7))
    return {
        'last_24h': AnalysisSession.objects.filter(created_at__gte=now - timedelta(hours=24)).count(),
        'last_7d': last_7d.count(),
        'converged_7d': last_7d.filter(phase='converged').count(),
    }


def _buildings_block(now):
    # Make-DB-owned table: raw SQL on the read-only 'buildings' connection, publishable only.
    with connections['buildings'].cursor() as cur:
        cur.execute('SELECT count(*) FROM canonical_v2_buildings WHERE is_publishable = true')
        return {'publishable': cur.fetchone()[0]}


class StatsView(AdminDashboardView):
    """GET stats/ -- DB counts. Cached 60s. Each block fails to null independently."""

    def get(self, request):
        data = cache.get(_STATS_CACHE_KEY)
        if data is None:
            now = timezone.now()
            data = {
                'users': _safe('users', lambda: _users_block(now)),
                'works': _safe('works', lambda: _works_block(now)),
                'reports': _safe('reports', lambda: _reports_block(now)),
                'sessions': _safe('sessions', lambda: _sessions_block(now)),
                'buildings': _safe('buildings', lambda: _buildings_block(now)),
            }
            cache.set(_STATS_CACHE_KEY, data, _STATS_TTL)
        return Response(data)


def _int_param(raw, default, lo, hi):
    try:
        return max(lo, min(hi, int(raw)))
    except (TypeError, ValueError):
        return default


class AuditLogView(AdminDashboardView):
    """GET audit-log/?page=&page_size= -- newest first (page_size <= 100)."""

    def get(self, request):
        page = _int_param(request.query_params.get('page'), 1, 1, 10**6)
        page_size = _int_param(request.query_params.get('page_size'), _DEFAULT_PAGE_SIZE, 1, _MAX_PAGE_SIZE)
        qs = AdminAuditLog.objects.select_related('actor').order_by('-created_at', '-id')
        count = qs.count()
        start = (page - 1) * page_size
        rows = qs[start:start + page_size]
        return Response({
            'results': [
                {
                    'id': r.id,
                    'actor_email': r.actor.email if r.actor else None,
                    'action': r.action,
                    'target_type': r.target_type,
                    'target_id': r.target_id,
                    'payload': r.payload,
                    'ip': r.ip,
                    'created_at': r.created_at.isoformat(),
                }
                for r in rows
            ],
            'count': count,
        })


class ServicesView(AdminDashboardView):
    """GET services/ -- external provider status / account / usage (ADMIN-DASH-2a).

    The external part is cached 10 min; ``?refresh=1`` bypasses and re-sets it. Admin
    notes are merged AFTER the cache read so an edit shows on the very next GET.
    """

    def get(self, request):
        payload = None if request.query_params.get('refresh') == '1' else cache.get(_SERVICES_CACHE_KEY)
        if payload is None:
            services, degraded = fetch_all_services()
            payload = {'services': services, 'fetched_at': timezone.now().isoformat()}
            cache.set(_SERVICES_CACHE_KEY, payload, _SERVICES_ERROR_TTL if degraded else _SERVICES_TTL)

        notes = dict(ProviderNote.objects.values_list('provider', 'login_note'))
        services = [
            {**svc, 'account': {'auto': svc['account']['auto'], 'note': notes.get(svc['slug'], '')}}
            for svc in payload['services']
        ]
        return Response({'services': services, 'fetched_at': payload['fetched_at']})


class ProviderNoteView(AdminDashboardView):
    """PATCH services/<slug>/note/ -- edit the admin memo for one provider (audit-logged)."""

    def patch(self, request, slug):
        if slug not in PROVIDER_SLUGS:
            return Response({'detail': 'Unknown provider.'}, status=http_status.HTTP_404_NOT_FOUND)

        raw = request.data.get('login_note') if hasattr(request.data, 'get') else None
        if not isinstance(raw, str):
            return Response({'login_note': ['This field is required and must be a string.']},
                            status=http_status.HTTP_400_BAD_REQUEST)
        note = raw.strip()
        if len(note) > _NOTE_MAX_LEN:
            return Response({'login_note': [f'Ensure this field has no more than {_NOTE_MAX_LEN} characters.']},
                            status=http_status.HTTP_400_BAD_REQUEST)

        existing = ProviderNote.objects.filter(provider=slug).first()
        old = existing.login_note if existing else ''
        obj, _created = ProviderNote.objects.update_or_create(
            provider=slug, defaults={'login_note': note, 'updated_by': request.user},
        )
        log_admin_action(request, 'provider_note.update', 'provider', slug, {'old': old, 'new': note})
        return Response({'slug': slug, 'login_note': obj.login_note, 'updated_at': obj.updated_at.isoformat()})
