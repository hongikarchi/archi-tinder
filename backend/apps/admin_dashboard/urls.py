from django.urls import path

from .views import AuditLogView, FlagsView, MigrationsView, StatsView, VersionView

urlpatterns = [
    path('version/', VersionView.as_view(), name='admin-dash-version'),
    path('migrations/', MigrationsView.as_view(), name='admin-dash-migrations'),
    path('flags/', FlagsView.as_view(), name='admin-dash-flags'),
    path('stats/', StatsView.as_view(), name='admin-dash-stats'),
    path('audit-log/', AuditLogView.as_view(), name='admin-dash-audit-log'),
]
