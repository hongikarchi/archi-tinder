from django.apps import AppConfig


class SocialConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.social'

    def ready(self):
        from . import models  # noqa — import triggers signal receiver registration
