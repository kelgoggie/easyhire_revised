from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('admin_panel', '0004_adminannouncement'),
    ]

    operations = [
        migrations.AddField(
            model_name='sitesettings',
            name='office_address',
            field=models.CharField(blank=True, default='', help_text='PESO Iloilo City office address (street, city, ZIP).', max_length=255),
        ),
        migrations.AddField(
            model_name='sitesettings',
            name='contact_email',
            field=models.EmailField(blank=True, default='', help_text='Public-facing contact email shown in the footer.', max_length=254),
        ),
        migrations.AddField(
            model_name='sitesettings',
            name='hotline',
            field=models.CharField(blank=True, default='', help_text='Public-facing hotline / landline number.', max_length=40),
        ),
    ]
