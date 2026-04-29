from django.urls import path
from .views import OfficeDetailView, OfficeClaimView, OfficeAdminQueueView, OfficeAdminVerifyView

app_name = 'profiles'
urlpatterns = [
    path('offices/<uuid:office_id>/', OfficeDetailView.as_view(), name='office-detail'),
    path('offices/<uuid:office_id>/claim/', OfficeClaimView.as_view(), name='office-claim'),
    path('admin/office_claims/', OfficeAdminQueueView.as_view(), name='admin-claim-queue'),
    path('admin/office_claims/<uuid:office_id>/', OfficeAdminVerifyView.as_view(), name='admin-claim-verify'),
]
