import sys
from django.apps import AppConfig

class JobseekersConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.jobseekers'
    label = 'jobseekers'

    def ready(self):
        # Warm the sentence-transformers model in a background thread on
        # server start instead of letting the first matching-related page
        # view (job detail, candidates, Jobs For You...) eat that cost —
        # loading it cold can take 30+ seconds. Only during runserver; a
        # one-off management command (migrate, makemigrations, etc.) has no
        # reason to pay for it.
        if 'runserver' not in sys.argv:
            return
        import threading
        def _warm():
            from apps.jobseekers.nlp_service import get_model
            get_model()
        threading.Thread(target=_warm, daemon=True).start()