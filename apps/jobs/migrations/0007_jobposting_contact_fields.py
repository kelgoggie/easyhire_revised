from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('jobs', '0006_alter_jobeducationrequirement_job'),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            # The columns already exist in the database from a prior schema —
            # we just need to register them in Django's model state.
            state_operations=[
                migrations.AddField(
                    model_name='jobposting',
                    name='contact_email',
                    field=models.EmailField(blank=True, default='', max_length=254),
                ),
                migrations.AddField(
                    model_name='jobposting',
                    name='contact_phone',
                    field=models.CharField(blank=True, default='', max_length=20),
                ),
                migrations.AddField(
                    model_name='jobposting',
                    name='search_keywords',
                    field=models.CharField(blank=True, default='', max_length=500),
                ),
            ],
            # Backfill nulls and set defaults so subsequent inserts succeed
            database_operations=[
                migrations.RunSQL(
                    sql="""
                        ALTER TABLE job_postings ADD COLUMN IF NOT EXISTS contact_email   VARCHAR(254) DEFAULT '';
                        ALTER TABLE job_postings ADD COLUMN IF NOT EXISTS contact_phone   VARCHAR(20)  DEFAULT '';
                        ALTER TABLE job_postings ADD COLUMN IF NOT EXISTS search_keywords VARCHAR(500) DEFAULT '';
                        UPDATE job_postings SET contact_email   = '' WHERE contact_email   IS NULL;
                        UPDATE job_postings SET contact_phone   = '' WHERE contact_phone   IS NULL;
                        UPDATE job_postings SET search_keywords = '' WHERE search_keywords IS NULL;
                        ALTER TABLE job_postings ALTER COLUMN contact_email   SET DEFAULT '';
                        ALTER TABLE job_postings ALTER COLUMN contact_phone   SET DEFAULT '';
                        ALTER TABLE job_postings ALTER COLUMN search_keywords SET DEFAULT '';
                    """,
                    reverse_sql=migrations.RunSQL.noop,
                ),
            ],
        ),
    ]
