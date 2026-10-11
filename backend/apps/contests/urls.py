from django.urls import path

from .views import ContestDetailView, ContestListView

urlpatterns = [
    path('contests/', ContestListView.as_view(), name='contest-list'),
    path('contests/<int:pk>/', ContestDetailView.as_view(), name='contest-detail'),
]
