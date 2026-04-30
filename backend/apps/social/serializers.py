"""
serializers.py -- apps/social

Minimal serializers for the SOC1 follow endpoints.
UserMiniSerializer is imported from apps.accounts to avoid duplication.
"""
from apps.accounts.serializers import UserMiniSerializer  # noqa: F401 -- re-exported for views
