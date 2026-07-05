from django.core.management.base import BaseCommand

from apps.jobseekers.models import Sector


SECTORS = [
    ('lgbtqia',         'LGBTQIA++'),
    ('solo_parent',     'Solo Parent'),
    ('pwd',             'Persons with Disabilities (PWD)'),
    ('osy',             'Out-of-School Youth (OSY)'),
    ('fresh_graduate',  'Fresh Graduate'),
    ('tesda_graduate',  'TESDA Graduate'),
    ('senior_citizen',  'Senior Citizen'),
]


class Command(BaseCommand):
    help = 'Idempotently re-seed the Sector table. Safe to run on any environment.'

    def handle(self, *args, **options):
        created = 0
        updated = 0
        for code, label in SECTORS:
            _, was_created = Sector.objects.update_or_create(
                code=code, defaults={'label': label}
            )
            if was_created:
                created += 1
            else:
                updated += 1
        self.stdout.write(self.style.SUCCESS(
            f'Sectors re-seeded — {created} created, {updated} updated.'
        ))
