"""accounts.views facade — re-exports every public name from the sub-modules.

IMPORT COMPATIBILITY: `from apps.accounts.views import X` and urls.py imports
resolve here for every view class + helper re-exported below.

MOCK-PATCH CONTRACT (facade re-export is a NAME COPY — read before patching):
  - `requests` is a MODULE → patch('apps.accounts.views.requests.post') works:
    the attribute is set on the shared module object that auth.py resolves at
    call time. (test_auth.py relies on this.)
  - `_exchange_google_code` (function) / `_dj_connections` (connections object)
    are NOT interceptable at the facade path. The re-export below is a separate
    binding, so patching `apps.accounts.views._exchange_google_code` does NOT
    rebind the global that auth.py / profile.py actually call. Patch the
    SUBMODULE path instead:
        apps.accounts.views.auth._exchange_google_code      (test_guest_auth.py)
        apps.accounts.views.profile._dj_connections         (test_liked_buildings.py)
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
    # AUTH-LOGIN-1: handle+password + email-link
    RegisterView,
    PasswordLoginView,
    SetPasswordView,
    LinkEmailView,
)

# -- profile sub-module names ----------------------------------------------
# Re-exported for `from apps.accounts.views import _dj_connections` compatibility.
# To mock.patch it, patch apps.accounts.views.profile._dj_connections — this
# facade name is a copy and does NOT intercept profile.py's own binding.
from .profile import _dj_connections  # noqa: F401  (import compat; patch via .profile)

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
