"""Code-pinned throttles for the follow API (convention: apps/messaging/throttling.py).

Effective rate = the `rate` class attr; DEFAULT_THROTTLE_RATES entry is registry only.
"""
from rest_framework.throttling import UserRateThrottle


class FollowWriteThrottle(UserRateThrottle):
    scope = 'follow'
    rate = '200/day'


class FollowStatusReadThrottle(UserRateThrottle):
    """Per-user cap on GET users/<id>/follow/ (#506): 200 vs 404 is a cheap
    user-id enumeration oracle (same class as #391).

    60/min stays well above legitimate load: one or two reads per profile open
    (FollowCta + the "..." menu) plus a refetch after each follow/block write.
    Own scope, so reads never eat the follow-write budget.
    """
    scope = 'follow_status'
    rate = '60/min'
