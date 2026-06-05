from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('jobs', '0007_jobposting_contact_fields'),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.AddField(
                    model_name='application',
                    name='message',
                    field=models.TextField(blank=True, default='', db_column='application_message'),
                ),
            ],
            database_operations=[
                migrations.RunSQL(
                    sql="""
                        UPDATE applications SET application_message = '' WHERE application_message IS NULL;
                        ALTER TABLE applications ALTER COLUMN application_message SET DEFAULT '';
                    """,
                    reverse_sql=migrations.RunSQL.noop,
                ),
            ],
        ),
    ]
