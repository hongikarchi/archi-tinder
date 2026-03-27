from django.urls import path
from .views import (
    ProjectListCreateView, ProjectDetailView,
    SessionCreateView, SwipeView, SessionResultView,
    DiverseRandomView, ParseQueryView,
    ProjectReportView, ProjectReportGenerateView,
)

urlpatterns = [
    # Projects
    path('projects',                                ProjectListCreateView.as_view()),
    path('projects/<uuid:pk>',                      ProjectDetailView.as_view()),
    path('projects/<uuid:pk>/report',               ProjectReportView.as_view()),
    path('projects/<uuid:pk>/report/generate',      ProjectReportGenerateView.as_view()),
    # Analysis sessions
    path('analysis/sessions',                       SessionCreateView.as_view()),
    path('analysis/sessions/<uuid:session_id>/swipes',  SwipeView.as_view()),
    path('analysis/sessions/<uuid:session_id>/result',  SessionResultView.as_view()),
    # Images
    path('images/diverse-random',                   DiverseRandomView.as_view()),
    # LLM
    path('api/parse-query',                         ParseQueryView.as_view()),
]
