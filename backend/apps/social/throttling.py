"""Code-pinned throttles for the follow API (convention: apps/messaging/throttling.py).

Effective rate = the `rate` class attr; DEFAULT_THROTTLE_RATES entry is registry only.
"""
from rest_framework.throttling import UserRateThrottle


class FollowWriteThrottle(UserRateThrottle):
    scope = 'follow'
    rate = '200/day'
