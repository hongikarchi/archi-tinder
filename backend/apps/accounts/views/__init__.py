"""accounts.views facade — re-exports every public name from the sub-modules.

IMPORT COMPATIBILITY: `from apps.accounts.views import X` and urls.py imports
resolve here for every view class + helper re-exported below.

MOCK-PATCH CONTRACT (facade re-export is a NAME COPY — read before patching):
  - `requests` is a MODULE → patch('apps.accounts.views.requests.post') works:
    the attribute is set on the shared module object that auth.py resolves at
    call time. (test_auth.py relies on this.)
  - `_exchange_google_code` (function) is NOT interceptable at the facade path. The re-export below is a separate
    binding, so patching `apps.accounts.views._exchange_google_code` does NOT
    rebind the global that auth.py / profile.py actually call. Patch the
    SUBMODULE path instead:
        apps.accounts.views.auth._exchange_google_code      (test_guest_auth.py)
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
    OnboardingView,
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
    # LOGIN-ONBOARD-1: unified ID availability check
    CheckHandleView,
)

# -- profile sub-module names ----------------------------------------------
from .profile import (  # noqa: F401
    # module-level helpers / constants
    _build_boards_field,

    # view classes routed by urls.py
    UserProfileDetailView,
    UserProfileSelfUpdateView,
    AvatarUploadView,
)

# -- meta sub-module names --------------------------------------------------
from .meta import RolesView  # noqa: F401

# -- personality sub-module names -------------------------------------------
from .personality import (  # noqa: F401
    PersonalityAssessmentView,
    PersonalityMeView,
)
