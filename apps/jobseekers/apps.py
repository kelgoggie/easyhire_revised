import os
import sys
from django.apps import AppConfig

# One-off management commands that never touch matching — no reason to pay
# for the model load. Everything else warms, including bare `manage.py
# runserver` (local dev) AND gunicorn/uwsgi in production, which don't go
# through manage.py at all (sys.argv there is just the gunicorn invocation,
# e.g. `gunicorn config.wsgi:application` — it NEVER contains 'runserver').
# The previous allowlist-on-'runserver' check meant this warm-up only ever
# fired locally and silently never ran in production — every live gunicorn
# worker was paying the full cold-start cost (~20-40s) on its first
# matching-related request instead of at startup.
_SKIP_COMMANDS = {
    'migrate', 'makemigrations', 'shell', 'seed', 'seed_demo', 'seed_more',
    'seed_algorithm_demo', 'seed_sectors', 'seed_faqs', 'seed_boost',
    'collectstatic', 'createsuperuser', 'test', 'flush', 'load_psgc',
    'dbshell', 'check', 'load_data',
}


class JobseekersConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.jobseekers'
    label = 'jobseekers'

    def ready(self):
        is_manage_py = len(sys.argv) >= 1 and os.path.basename(sys.argv[0]) == 'manage.py'
        if is_manage_py and len(sys.argv) >= 2 and sys.argv[1] in _SKIP_COMMANDS:
            return
        import threading
        def _warm():
            from apps.jobseekers.nlp_service import get_model
            get_model()
        threading.Thread(target=_warm, daemon=True).start()