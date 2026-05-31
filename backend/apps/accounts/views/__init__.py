"""accounts.views facade — re-exports every public name from the sub-modules.

PATCH-PATH CONTRACT (do not remove without updating tests):
  apps.accounts.views._dj_connections  → from .profile (used by LikedBuildingsView)
  apps.accounts.views.requests         → from .auth (used by GoogleLoginView / KakaoLoginView / NaverLoginView)
  apps.accounts.views._exchange_google_code → from .auth (patched in test_guest_auth.py)

All view classes imported by urls.py are also re-exported here so that
  from apps.accounts.views import X
and the patch path  apps.accounts.views.X  keep working unchanged.
"""

# -- auth sub-module names -------------------------------------------------
# Import `requests` into this namespace so patch('apps.accounts.views.requests.post')
# and patch('apps.accounts.views.requests.get') intercept the right binding.
from .auth import requests  # noqa: F401  (patch target)

from .auth import (  # noqa: F401
    # module-level helpers / constants (patch targets + internal use)
    VALID_ONBOARDING_ROLES,
    _clean_guest_display_name,
    _exchange_google_code,
    _get_or_create_user,
    _make_token_response,
    DevLoginThrottle,

    # view classes routed by urls.py
    GuestLoginView,
    GuestPromoteView,
    GoogleLoginView,
    KakaoLoginView,
    NaverLoginView,
    DevLoginView,
    TokenRefreshView,
    MeView,
    LogoutView,
)

# -- profile sub-module names ----------------------------------------------
# Import `_dj_connections` into this namespace so
# patch('apps.accounts.views._dj_connections', ...) intercepts the right binding.
from .profile import _dj_connections  # noqa: F401  (patch target)

from .profile import (  # noqa: F401
    # module-level helpers / constants
    _build_boards_field,
    _LIKED_BUILDINGS_CAP,
    _BLD_ID_MAX_LEN,
    _BLD_ID_RE,

    # view classes routed by urls.py
    UserProfileDetailView,
    UserProfileSelfUpdateView,
    LikedBuildingsView,
)
