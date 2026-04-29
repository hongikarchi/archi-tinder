from rest_framework.throttling import UserRateThrottle


class OfficeClaimThrottle(UserRateThrottle):
    """Rate-limit Office claim submissions to prevent admin queue flood.

    5 claims per hour per authenticated user. Mirrors DevLoginThrottle pattern
    (apps/accounts/views.py) using inline rate attribute rather than settings lookup.
    """
    rate = '5/hour'
