from django.urls import path

from .views import (
    BlockView,
    ConversationListView,
    ConversationMessagesView,
    ConversationReadView,
    ReportView,
    UnreadCountView,
)

urlpatterns = [
    path('conversations/', ConversationListView.as_view(), name='conversation-list'),
    path('conversations/<int:conversation_id>/messages/', ConversationMessagesView.as_view(), name='conversation-messages'),
    path('conversations/<int:conversation_id>/read/', ConversationReadView.as_view(), name='conversation-read'),
    path('messages/unread-count/', UnreadCountView.as_view(), name='messages-unread-count'),
    path('users/<int:user_id>/block/', BlockView.as_view(), name='user-block'),
    path('reports/', ReportView.as_view(), name='report-create'),
]
