from rest_framework.throttling import UserRateThrottle


class FeedbackThrottle(UserRateThrottle):
    """30 feedback writes per minute per user (class `rate` is the effective value)."""
    scope = 'feedback'
    rate = '30/min'
