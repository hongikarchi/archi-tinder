from django.urls import path
from django.conf import settings
from .views import (
    GoogleLoginView, KakaoLoginView, NaverLoginView,
    TokenRefreshView, MeView, LogoutView, DevLoginView,
    UserProfileDetailView, UserProfileSelfUpdateView,
)

urlpatterns = [
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
]

if settings.DEBUG:
    urlpatterns += [
        path('auth/dev-login/',      DevLoginView.as_view()),
    ]
