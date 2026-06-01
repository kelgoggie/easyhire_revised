from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('jobseekers', '0005_jobseekerprofile_bio'),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            # Tell Django's ORM that this field exists (model state update only)
            state_operations=[
                migrations.AddField(
                    model_name='jobseekerprofile',
                    name='profile_visibility',
                    field=models.CharField(default='public', max_length=20),
                ),
            ],
            # Column already exists in the DB — just backfill nulls and set a default
            database_operations=[
                migrations.RunSQL(
                    sql="""
                        UPDATE jobseeker_profiles
                           SET profile_visibility = 'public'
                         WHERE profile_visibility IS NULL;
                        ALTER TABLE jobseeker_profiles
                            ALTER COLUMN profile_visibility SET DEFAULT 'public';
                    """,
                    reverse_sql=migrations.RunSQL.noop,
                ),
            ],
        ),
    ]
