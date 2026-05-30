from django.urls import path
from django.conf import settings
from .views import (
    GoogleLoginView, KakaoLoginView, NaverLoginView,
    TokenRefreshView, MeView, LogoutView, DevLoginView,
    UserProfileDetailView, UserProfileSelfUpdateView,
    GuestLoginView, GuestPromoteView,
    LikedBuildingsView,
)

urlpatterns = [
    # -- Guest-first onboarding (FULL-LOGIN-REDESIGN-1) --
    path('auth/guest/',              GuestLoginView.as_view()),
    path('auth/promote/',            GuestPromoteView.as_view()),
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
    path('users/<int:user_id>/', UserProfileDetailView.as_view(), name='user-profile-detail'),
    # SNS-LIKED-PROJECTS — Discovery right-swipe liked buildings
    path('liked-buildings/', LikedBuildingsView.as_view(), name='liked-buildings'),
]

if settings.DEBUG:
    urlpatterns += [
        path('auth/dev-login/',      DevLoginView.as_view()),
    ]
