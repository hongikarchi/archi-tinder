from django.contrib import admin
from django.urls import path, include
from django.conf import settings

urlpatterns = [
    path('api/v1/', include('apps.accounts.urls')),
    path('api/v1/', include('apps.recommendation.urls')),
    path('api/v1/', include('apps.profiles.urls')),
]

if settings.DEBUG:
    urlpatterns += [
        path('admin/', admin.site.urls),
    ]
