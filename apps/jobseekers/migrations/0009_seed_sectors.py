from django.db import migrations


SECTORS = [
    ('lgbtqia',         'LGBTQIA++'),
    ('solo_parent',     'Solo Parent'),
    ('pwd',             'Persons with Disabilities (PWD)'),
    ('osy',             'Out-of-School Youth (OSY)'),
    ('fresh_graduate',  'Fresh Graduate'),
    ('tesda_graduate',  'TESDA Graduate'),
    ('senior_citizen',  'Senior Citizen'),
]


def seed_sectors(apps, schema_editor):
    Sector = apps.get_model('jobseekers', 'Sector')
    for code, label in SECTORS:
        Sector.objects.update_or_create(code=code, defaults={'label': label})


def unseed_sectors(apps, schema_editor):
    Sector = apps.get_model('jobseekers', 'Sector')
    Sector.objects.filter(code__in=[c for c, _ in SECTORS]).delete()


class Migration(migrations.Migration):
    dependencies = [
        ('jobseekers', '0008_jobseekerprofile_profile_picture'),
    ]

    operations = [
        migrations.RunPython(seed_sectors, unseed_sectors),
    ]
