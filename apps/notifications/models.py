from django.db import models

from django.db import models
from apps.accounts.models import User


class Notification(models.Model):
    COMPANY_LIKED_YOU = 'company_liked_you'
    JOBSEEKERS_LIKED_JOB = 'jobseekers_liked_job'
    MATCH = 'match'

    TYPE_CHOICES = [
        (COMPANY_LIKED_YOU, 'Company Liked You'),
        (JOBSEEKERS_LIKED_JOB, 'Jobseekers Liked Job'),
        (MATCH, 'Match'),
    ]

    recipient = models.ForeignKey(User, on_delete=models.CASCADE, related_name='activity_notifications')
    notif_type = models.CharField(max_length=30, choices=TYPE_CHOICES)
    company = models.ForeignKey('employers.Company', on_delete=models.CASCADE, null=True, blank=True)
    jobseeker = models.ForeignKey('jobseekers.JobseekerProfile', on_delete=models.CASCADE, null=True, blank=True)
    job = models.ForeignKey('jobs.JobPosting', on_delete=models.CASCADE, null=True, blank=True)
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    # For grouped employer notifications — stores count of likers
    liker_count = models.PositiveIntegerField(default=1)
    liker_preview = models.CharField(max_length=200, blank=True,
        help_text="e.g. 'Juan, Maria and 9+ others'")

    class Meta:
        db_table = 'activity_notifications'
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.get_notif_type_display()} → {self.recipient.email}"