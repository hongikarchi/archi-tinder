"""Code-pinned throttles for messaging (convention: apps/social ReactionWriteThrottle).

Effective rate = the `rate` class attr; DEFAULT_THROTTLE_RATES entries are registry only.
"""
from rest_framework.throttling import UserRateThrottle


class ContactRequestThrottle(UserRateThrottle):
    scope = 'contact_request'
    rate = '20/day'


class MessageSendThrottle(UserRateThrottle):
    scope = 'message_send'
    rate = '30/min'


class ReportThrottle(UserRateThrottle):
    scope = 'report'
    rate = '10/hour'


class MessageReadThrottle(UserRateThrottle):
    """Per-user cap on messaging GETs (inbox, conversation poll, unread count,
    received requests, request status). One shared scope across those endpoints.

    120/min stays well above legitimate load: the in-conversation poll is every
    4s (15/min) plus unread-count polling and inbox / sheet loads.
    """
    scope = 'message_read'
    rate = '120/min'
