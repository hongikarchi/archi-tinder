from django.urls import path
from .views import (
    GoogleLoginView, KakaoLoginView, NaverLoginView,
    TokenRefreshView, MeView, LogoutView,
)

urlpatterns = [
    path('auth/social/google',       GoogleLoginView.as_view()),
    path('auth/social/kakao',        KakaoLoginView.as_view()),
    path('auth/social/naver',        NaverLoginView.as_view()),
    path('auth/token/refresh',       TokenRefreshView.as_view()),
    path('auth/me',                  MeView.as_view()),
    path('auth/logout',              LogoutView.as_view()),
]
