"""Pre-load the sentence-transformer model and warm static embedding caches.

Run this once after server start (or in a deploy hook) so the first real user
request doesn't eat the model-load latency.

    python manage.py warm_nlp
"""

import time
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = 'Pre-load NLP model and warm up static embedding caches.'

    def handle(self, *args, **options):
        from apps.jobseekers.nlp_service import (
            get_model, _get_or_compute_embeddings, CANONICAL_INDUSTRIES,
        )
        from apps.jobseekers.views import (
            STATIC_SKILLS, STATIC_POSITIONS, STATIC_DEGREES, STATIC_CERTS,
            STATIC_INSTITUTIONS, STATIC_COMPANIES,
        )

        self.stdout.write('Loading sentence-transformer model...')
        t0 = time.time()
        model = get_model()
        if model is None:
            self.stdout.write(self.style.ERROR(
                'Model failed to load. Semantic features will degrade gracefully.'
            ))
            return
        self.stdout.write(self.style.SUCCESS(
            f'Model loaded in {time.time() - t0:.1f}s'
        ))

        self.stdout.write('Pre-computing embeddings for static vocabularies...')
        for name, vocab, key in [
            ('skills',       STATIC_SKILLS,        'skills'),
            ('positions',    STATIC_POSITIONS,     'positions'),
            ('degrees',      STATIC_DEGREES,       'degrees'),
            ('certs',        STATIC_CERTS,         'certs'),
            ('institutions', STATIC_INSTITUTIONS,  'institutions'),
            ('companies',    STATIC_COMPANIES,     'companies'),
            ('industries',   CANONICAL_INDUSTRIES, 'canonical_industries'),
        ]:
            t0 = time.time()
            _get_or_compute_embeddings(vocab, key)
            self.stdout.write(f'  {name:12s} ({len(vocab):3d} items) in {time.time() - t0:.2f}s')

        self.stdout.write(self.style.SUCCESS('NLP service warmed up.'))
