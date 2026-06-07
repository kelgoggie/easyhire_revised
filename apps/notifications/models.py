from django.db import models

from django.db import models
from apps.accounts.models import User


class Notification(models.Model):
    COMPANY_LIKED_YOU = 'company_liked_you'
    JOBSEEKERS_LIKED_JOB = 'jobseekers_liked_job'
    MATCH = 'match'
    JOB_DELETED_BY_ADMIN = 'job_deleted_by_admin'

    TYPE_CHOICES = [
        (COMPANY_LIKED_YOU,    'Company Liked You'),
        (JOBSEEKERS_LIKED_JOB, 'Jobseekers Liked Job'),
        (MATCH,                'Match'),
        (JOB_DELETED_BY_ADMIN, 'Job Deleted by Admin'),
    ]

    recipient = models.ForeignKey(User, on_delete=models.CASCADE, related_name='activity_notifications')
    notif_type = models.CharField(max_length=30, choices=TYPE_CHOICES)
    company = models.ForeignKey('employers.Company', on_delete=models.CASCADE, null=True, blank=True)
    jobseeker = models.ForeignKey('jobseekers.JobseekerProfile', on_delete=models.CASCADE, null=True, blank=True)
    # Job FK is SET_NULL: when an admin deletes a job, the notification about that
    # deletion should survive (with the job title snapshotted in liker_preview).
    job = models.ForeignKey('jobs.JobPosting', on_delete=models.SET_NULL, null=True, blank=True)
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    # For grouped employer notifications — stores count of likers,
    # OR (for JOB_DELETED_BY_ADMIN) a snapshot of the deleted job's title.
    liker_count = models.PositiveIntegerField(default=1)
    liker_preview = models.CharField(max_length=200, blank=True,
        help_text="e.g. 'Juan, Maria and 9+ others', or a deleted job's title snapshot.")
    # Free-form admin-supplied message (currently used for job-deletion reasons).
    admin_message = models.TextField(blank=True, default='')

    class Meta:
        db_table = 'activity_notifications'
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.get_notif_type_display()} → {self.recipient.email}"