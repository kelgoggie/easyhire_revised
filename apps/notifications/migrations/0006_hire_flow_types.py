from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('notifications', '0005_alter_notification_notif_type'),
    ]

    operations = [
        migrations.AlterField(
            model_name='notification',
            name='notif_type',
            field=models.CharField(
                choices=[
                    ('company_liked_you',       'Company Liked You'),
                    ('jobseekers_liked_job',    'Jobseekers Liked Job'),
                    ('match',                   'Match'),
                    ('job_deleted_by_admin',    'Job Deleted by Admin'),
                    ('personal_info_approved',  'Personal Info Change Approved'),
                    ('personal_info_rejected',  'Personal Info Change Rejected'),
                    ('new_application',         'New Job Application'),
                    ('application_accepted',    'Application Accepted'),
                    ('application_rejected',    'Application Rejected'),
                    ('application_hired',       'Application Hired'),
                    ('employer_contacted',      'Employer Sent Contact'),
                    ('hire_offered',            'Hire Offered'),
                    ('hire_accepted',           'Hire Accepted'),
                    ('hire_declined',           'Hire Declined'),
                ],
                max_length=30,
            ),
        ),
    ]
