from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('jobseekers', '0006_jobseekerprofile_profile_visibility'),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.AddField(
                    model_name='jobseekerprofile',
                    name='sector_badge_visibility',
                    field=models.CharField(default='public', max_length=20),
                ),
            ],
            database_operations=[
                migrations.RunSQL(
                    sql="""
                        UPDATE jobseeker_profiles
                           SET sector_badge_visibility = 'public'
                         WHERE sector_badge_visibility IS NULL;
                        ALTER TABLE jobseeker_profiles
                            ALTER COLUMN sector_badge_visibility SET DEFAULT 'public';
                    """,
                    reverse_sql=migrations.RunSQL.noop,
                ),
            ],
        ),
    ]
