from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path('api/v1/', include('apps.accounts.urls')),
    path('api/v1/', include('apps.recommendation.urls')),
    path('api/v1/', include('apps.profiles.urls')),
    path('api/v1/', include('apps.social.urls')),
    path('api/v1/', include('apps.notifications.urls')),
    path('api/v1/works/', include('apps.works.urls')),
]

if settings.DEBUG:
    urlpatterns += [
        path('admin/', admin.site.urls),
    ]
    # Serve locally uploaded media (avatars) in development only.
    # Prod serves from R2's public domain — Django never serves media in prod.
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
