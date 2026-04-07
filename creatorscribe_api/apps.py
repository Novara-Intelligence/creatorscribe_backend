from django.apps import AppConfig


class CreatorscribeApiConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'creatorscribe_api'

    def ready(self):
        import creatorscribe_api.signals  # noqa: F401
