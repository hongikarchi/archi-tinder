from django.urls import path

from .views import FinalizeView, PresignView, WorkDetailView

urlpatterns = [
    path('presign/', PresignView.as_view()),
    path('<str:upload_id>/', WorkDetailView.as_view(), name='work-detail'),
    path('', FinalizeView.as_view()),
]
