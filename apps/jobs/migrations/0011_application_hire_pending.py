from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('jobs', '0010_application_hire_dates'),
    ]

    operations = [
        migrations.AlterField(
            model_name='application',
            name='status',
            field=models.CharField(
                choices=[
                    ('pending',      'Pending'),
                    ('viewed',       'Viewed'),
                    ('accepted',     'Accepted'),
                    ('rejected',     'Rejected'),
                    ('hire_pending', 'Hire Offered'),
                    ('hired',        'Hired'),
                ],
                default='pending',
                max_length=15,
            ),
        ),
    ]
