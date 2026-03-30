from django.urls import path
from django.conf import settings
from .views import (
    GoogleLoginView, KakaoLoginView, NaverLoginView,
    TokenRefreshView, MeView, LogoutView, DevLoginView,
)

urlpatterns = [
    path('auth/social/google/',      GoogleLoginView.as_view()),
    path('auth/social/kakao/',       KakaoLoginView.as_view()),
    path('auth/social/naver/',       NaverLoginView.as_view()),
    path('auth/token/refresh/',      TokenRefreshView.as_view()),
    path('auth/me/',                 MeView.as_view()),
    path('auth/logout/',             LogoutView.as_view()),
]

if settings.DEBUG:
    urlpatterns += [
        path('auth/dev-login/',      DevLoginView.as_view()),
    ]
