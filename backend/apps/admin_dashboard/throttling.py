"""Throttle for admitted admin-dashboard calls (runs AFTER IsAdminOperator)."""
from rest_framework.throttling import UserRateThrottle


class AdminThrottle(UserRateThrottle):
    scope = 'admin'
    rate = '120/min'
