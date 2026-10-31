from django.urls import path

from .contests_views import ContestDetailView, ContestListCreateView
from .views import (
    AuditLogView, FlagsView, MigrationsView, ProviderNoteView, ServicesView, StatsView, VersionView,
)

urlpatterns = [
    path('version/', VersionView.as_view(), name='admin-dash-version'),
    path('migrations/', MigrationsView.as_view(), name='admin-dash-migrations'),
    path('flags/', FlagsView.as_view(), name='admin-dash-flags'),
    path('stats/', StatsView.as_view(), name='admin-dash-stats'),
    path('services/', ServicesView.as_view(), name='admin-dash-services'),
    path('services/<slug:slug>/note/', ProviderNoteView.as_view(), name='admin-dash-provider-note'),
    path('contests/', ContestListCreateView.as_view(), name='admin-dash-contests'),
    path('contests/<int:pk>/', ContestDetailView.as_view(), name='admin-dash-contest-detail'),
    path('audit-log/', AuditLogView.as_view(), name='admin-dash-audit-log'),
]
