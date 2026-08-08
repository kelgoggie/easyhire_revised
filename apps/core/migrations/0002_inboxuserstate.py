from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0001_initial'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='InboxUserState',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('source_type', models.CharField(choices=[('application', 'Application'), ('contact', 'Employer Contact'), ('announcement', 'Admin Announcement'), ('verification', 'Verification Update')], max_length=20)),
                ('source_id', models.PositiveIntegerField()),
                ('is_dismissed', models.BooleanField(default=False)),
                ('is_pinned', models.BooleanField(default=False)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='inbox_states', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'db_table': 'inbox_user_state',
                'unique_together': {('user', 'source_type', 'source_id')},
                'indexes': [
                    models.Index(fields=['user', 'is_dismissed'], name='inbox_user__user_id_dismis_idx'),
                    models.Index(fields=['user', 'is_pinned'],    name='inbox_user__user_id_pinned_idx'),
                ],
            },
        ),
    ]
