from django.urls import path
from django.conf import settings
from .views import (
    GoogleLoginView, KakaoLoginView, NaverLoginView,
    TokenRefreshView, MeView, LogoutView, DevLoginView,
    UserProfileDetailView, UserProfileSelfUpdateView, AvatarUploadView,
    GuestLoginView, GuestPromoteView,
    LikedBuildingsView,
    # AUTH-LOGIN-1: handle+password + email-link
    RegisterView, PasswordLoginView, SetPasswordView, LinkEmailView,
    # LOGIN-ONBOARD-1: unified ID check
    CheckHandleView,
    # SETTINGS-POLISH-1: public role-list metadata
    RolesView,
    # Personality assessment + discovery opt-in
    PersonalityAssessmentView, PersonalityMeView,
)

urlpatterns = [
    # -- Guest-first onboarding (FULL-LOGIN-REDESIGN-1) --
    path('auth/guest/',              GuestLoginView.as_view()),
    path('auth/promote/',            GuestPromoteView.as_view()),
    # -- Handle + Password Auth (AUTH-LOGIN-1) --
    path('auth/register/',           RegisterView.as_view(),      name='auth-register'),
    path('auth/login/',              PasswordLoginView.as_view(), name='auth-login'),
    path('auth/set-password/',       SetPasswordView.as_view(),   name='auth-set-password'),
    path('auth/link-email/',         LinkEmailView.as_view(),     name='auth-link-email'),
    # LOGIN-ONBOARD-1: unified ID availability check
    path('auth/check-handle/',       CheckHandleView.as_view(),   name='auth-check-handle'),
    # -- Social OAuth --
    path('auth/social/google/',      GoogleLoginView.as_view()),
    path('auth/social/kakao/',       KakaoLoginView.as_view()),
    path('auth/social/naver/',       NaverLoginView.as_view()),
    path('auth/token/refresh/',      TokenRefreshView.as_view()),
    path('auth/me/',                 MeView.as_view()),
    path('auth/logout/',             LogoutView.as_view()),
    # Phase 13 PROF2 — UserProfile endpoints
    # users/me/ (string) must come before users/<int:user_id>/ for clarity,
    # though Django's int converter auto-disambiguates them.
    path('users/me/', UserProfileSelfUpdateView.as_view(), name='user-profile-self-update'),
    path('users/me/avatar/', AvatarUploadView.as_view(), name='user-avatar-upload'),
    path('users/<int:user_id>/', UserProfileDetailView.as_view(), name='user-profile-detail'),
    # SNS-LIKED-PROJECTS — Discovery right-swipe liked buildings
    path('liked-buildings/', LikedBuildingsView.as_view(), name='liked-buildings'),
    # SETTINGS-POLISH-1: public metadata (AllowAny — login page needs it pre-auth)
    path('meta/roles/', RolesView.as_view(), name='meta-roles'),
    # Personality assessment + discovery
    path('personality/assessment/', PersonalityAssessmentView.as_view(), name='personality-assessment'),
    path('personality/me/', PersonalityMeView.as_view(), name='personality-me'),
]

if settings.DEBUG:
    urlpatterns += [
        path('auth/dev-login/',      DevLoginView.as_view()),
    ]
