"""Code-pinned throttles for messaging writes (convention: apps/social ReactionWriteThrottle).

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
