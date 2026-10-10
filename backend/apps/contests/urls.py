from django.urls import path

from .views import (
    ContestDetailView, ContestInterestView, ContestListView, ContestPosterReportView,
)

urlpatterns = [
    path('contests/', ContestListView.as_view(), name='contest-list'),
    path('contests/<int:pk>/', ContestDetailView.as_view(), name='contest-detail'),
    path(
        'contests/<int:pk>/interest/',
        ContestInterestView.as_view(), name='contest-interest',
    ),
    path(
        'contests/<int:pk>/poster-report/',
        ContestPosterReportView.as_view(), name='contest-poster-report',
    ),
]
