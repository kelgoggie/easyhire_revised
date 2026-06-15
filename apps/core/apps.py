from django.apps import AppConfig

class CoreConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.core'
    label = 'core'

    def ready(self):
        # Register HEIC/HEIF as a Pillow-supported format so iPhone photos
        # upload through any ImageField. No-op if pillow-heif is missing.
        try:
            from pillow_heif import register_heif_opener
            register_heif_opener()
        except ImportError:
            pass