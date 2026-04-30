from django.urls import path
from .views import (
    ProjectListCreateView, ProjectDetailView, UserProjectsListView,
    SessionCreateView, SessionStateView, SwipeView, SessionResultView,
    DiverseRandomView, BuildingBatchView, ParseQueryView,
    ProjectReportGenerateView, ProjectReportImageView,
    ProjectBookmarkView, ImageLoadTelemetryView,
)

urlpatterns = [
    # Projects (owner list + create)
    path('projects/',                                         ProjectListCreateView.as_view()),
    # Project detail — GET (public/visibility-gated) + PATCH + DELETE
    path('projects/<uuid:pk>/',                               ProjectDetailView.as_view()),
    path('projects/<uuid:pk>/report/generate-image/',         ProjectReportImageView.as_view()),
    path('projects/<uuid:pk>/report/generate/',               ProjectReportGenerateView.as_view()),
    path('projects/<uuid:project_id>/bookmark/',              ProjectBookmarkView.as_view()),
    # User-scoped project list — BOARD1 Phase 13
    path('users/<int:user_id>/projects/',                     UserProjectsListView.as_view()),
    # Analysis sessions
    path('analysis/sessions/',                           SessionCreateView.as_view()),
    path('analysis/sessions/<uuid:session_id>/state/',   SessionStateView.as_view()),
    path('analysis/sessions/<uuid:session_id>/swipes/',  SwipeView.as_view()),
    path('analysis/sessions/<uuid:session_id>/result/',  SessionResultView.as_view()),
    # Images
    path('images/diverse-random/',                       DiverseRandomView.as_view()),
    path('images/batch/',                                BuildingBatchView.as_view()),
    # LLM query parsing
    path('parse-query/',                                 ParseQueryView.as_view()),
    # Telemetry
    path('telemetry/image-load/',                        ImageLoadTelemetryView.as_view(), name='telemetry_image_load'),
]
