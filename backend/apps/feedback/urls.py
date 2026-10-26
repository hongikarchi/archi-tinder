from django.urls import path

from .views import (CardReportCancelView, CardReportView,
                    QueryReportCancelView, QueryReportView)

urlpatterns = [
    path('feedback/card-reports/', CardReportView.as_view()),
    path('feedback/card-reports/cancel/', CardReportCancelView.as_view()),
    path('feedback/query-reports/', QueryReportView.as_view()),
    path('feedback/query-reports/cancel/', QueryReportCancelView.as_view()),
]
