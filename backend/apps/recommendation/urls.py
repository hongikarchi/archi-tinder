from django.urls import path, re_path
from .views import (
    ProjectListCreateView, ProjectDetailView, UserProjectsListView,
    SessionCreateView, SessionStateView, SwipeView, SessionResultView,
    DiscoveryFeedView, DiscoveryFeedbackView, DiscoveryPromoteView,
    DiverseRandomView, BuildingBatchView,
    ParseQueryView,
    ProjectReportGenerateView, ProjectReportImageView,
    ProjectReportImageFetchView,
    ProjectBookmarkView, ImageLoadTelemetryView, BoardSurpriseView,
    QuestionResponseView,
    RecommendedArchitectsView, ArchitectDetailView, ArchitectFollowView,
    InspectBuildingsListView, InspectBuildingDetailView, InspectSearchView,
)

urlpatterns = [
    # Projects (owner list + create)
    path('projects/',                                         ProjectListCreateView.as_view()),
    # Project detail — GET (public/visibility-gated) + PATCH + DELETE
    path('projects/<uuid:pk>/',                               ProjectDetailView.as_view()),
    path('projects/<uuid:pk>/report/generate-image/',         ProjectReportImageView.as_view()),
    path('projects/<uuid:pk>/report-image/',                  ProjectReportImageFetchView.as_view(), name='project-report-image'),
    path('projects/<uuid:pk>/report/generate/',               ProjectReportGenerateView.as_view()),
    path('projects/<uuid:project_id>/bookmark/',              ProjectBookmarkView.as_view()),
    # User-scoped project list — BOARD1 Phase 13
    path('users/<int:user_id>/projects/',                     UserProjectsListView.as_view()),
    # Analysis sessions
    path('analysis/sessions/',                           SessionCreateView.as_view()),
    path('analysis/sessions/<uuid:session_id>/state/',   SessionStateView.as_view()),
    path('analysis/sessions/<uuid:session_id>/swipes/',  SwipeView.as_view()),
    path('analysis/sessions/<uuid:session_id>/result/',  SessionResultView.as_view()),
    path('analysis/sessions/<uuid:session_id>/question-responses/', QuestionResponseView.as_view()),
    # Images
    path('discovery/',                                   DiscoveryFeedView.as_view()),
    path('discovery/feedback/',                          DiscoveryFeedbackView.as_view()),
    path('discovery/promote-to-taste/',                  DiscoveryPromoteView.as_view()),
    path('images/diverse-random/',                       DiverseRandomView.as_view()),
    path('images/batch/',                                BuildingBatchView.as_view()),
    # Surprise board
    path('recommendations/board-surprise/',              BoardSurpriseView.as_view()),
    # LLM query parsing
    path('parse-query/',                                 ParseQueryView.as_view()),
    # Telemetry
    path('telemetry/image-load/',                        ImageLoadTelemetryView.as_view(), name='telemetry_image_load'),
    # Architect recommendation
    path('projects/<uuid:pk>/recommended_architects/',   RecommendedArchitectsView.as_view()),
    # Follow URL must come before the detail URL (more specific path first).
    re_path(r'^architects/(?P<architect_id>arch_[0-9]{6})/follow/$', ArchitectFollowView.as_view()),
    re_path(r'^architects/(?P<architect_id>arch_[0-9]{6})/$', ArchitectDetailView.as_view()),
    # ADMIN-DBCHECK-1: internal DB-quality inspection API (list must come before detail).
    path('inspect/buildings/',                                InspectBuildingsListView.as_view()),
    re_path(r'^inspect/buildings/(?P<canonical_bld_id>bld_[0-9]{6})/$', InspectBuildingDetailView.as_view()),
    path('inspect/search/',                                   InspectSearchView.as_view()),
]
