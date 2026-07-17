from django.urls import path

from .views import FinalizeView, PresignView

urlpatterns = [
    path('presign/', PresignView.as_view()),
    path('', FinalizeView.as_view()),
]
