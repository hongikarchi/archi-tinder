from django.urls import path

from .views import NotificationListView, UnreadCountView, MarkReadView

urlpatterns = [
    path('notifications/', NotificationListView.as_view(), name='notification-list'),
    path('notifications/unread-count/', UnreadCountView.as_view(), name='notification-unread-count'),
    path('notifications/mark-read/', MarkReadView.as_view(), name='notification-mark-read'),
]
