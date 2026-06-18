from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('jobs', '0011_application_hire_pending'),
    ]

    operations = [
        migrations.AddField(
            model_name='jobposting',
            name='admin_disabled',
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name='jobposting',
            name='admin_disabled_reason',
            field=models.TextField(blank=True, default=''),
        ),
    ]
