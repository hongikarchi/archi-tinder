from django.urls import path, re_path
from .views import (
    OfficeDetailView,
    OfficeClaimView,
    OfficeAdminQueueView,
    OfficeAdminVerifyView,
    OfficeSaveView,
    SavedOfficeListView,
)

app_name = 'profiles'
urlpatterns = [
    path('offices/saved/', SavedOfficeListView.as_view(), name='office-saved-list'),
    re_path(r'^offices/(?P<canonical_id>arch_[0-9]{6})/save/$', OfficeSaveView.as_view(), name='office-save'),
    path('offices/<uuid:office_id>/', OfficeDetailView.as_view(), name='office-detail'),
    path('offices/<uuid:office_id>/claim/', OfficeClaimView.as_view(), name='office-claim'),
    path('admin/office_claims/', OfficeAdminQueueView.as_view(), name='admin-claim-queue'),
    path('admin/office_claims/<uuid:office_id>/', OfficeAdminVerifyView.as_view(), name='admin-claim-verify'),
]
