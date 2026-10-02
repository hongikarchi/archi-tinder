from django.urls import path

from .views import (
    BlockView,
    ContactRequestAcceptView,
    ContactRequestCreateView,
    ContactRequestIgnoreView,
    ContactRequestReceivedView,
    ContactRequestStatusView,
    ConversationListView,
    ConversationMessagesView,
    ConversationReadView,
    ReportView,
    UnreadCountView,
)

urlpatterns = [
    path('contact-requests/', ContactRequestCreateView.as_view(), name='contact-request-create'),
    path('contact-requests/received/', ContactRequestReceivedView.as_view(), name='contact-request-received'),
    path('contact-requests/status/', ContactRequestStatusView.as_view(), name='contact-request-status'),
    path('contact-requests/<int:request_id>/accept/', ContactRequestAcceptView.as_view(), name='contact-request-accept'),
    path('contact-requests/<int:request_id>/ignore/', ContactRequestIgnoreView.as_view(), name='contact-request-ignore'),
    path('conversations/', ConversationListView.as_view(), name='conversation-list'),
    path('conversations/<int:conversation_id>/messages/', ConversationMessagesView.as_view(), name='conversation-messages'),
    path('conversations/<int:conversation_id>/read/', ConversationReadView.as_view(), name='conversation-read'),
    path('messages/unread-count/', UnreadCountView.as_view(), name='messages-unread-count'),
    path('users/<int:user_id>/block/', BlockView.as_view(), name='user-block'),
    path('reports/', ReportView.as_view(), name='report-create'),
]
